"""Local Tesseract-OCR extraction stage for scanned-image NEET PDFs
(NEET Past Papers_V3 batch: NEET 2020 English Sets E1-E6, F1, F3-F6, G1).

These 12 PDFs have NO extractable text layer (confirmed via pypdf and
PyMuPDF `page.get_text()` -- both return empty strings on every page).
This module renders each page to a raster image with PyMuPDF, runs local
Tesseract OCR (no cloud/AI APIs), and produces per-page text plus
per-token bounding boxes. Parsing of the resulting (noisier) text reuses
the question-number / option-letter segmentation conventions already
established in `extractor.py` (digit-style "(1)".."(4)" options, "<n>. "
stems), adapted for OCR noise and for this paper's strict two-column
page layout.

No AI/LLM calls. No network calls. Read-only with respect to the source
PDFs. Nothing here guesses or invents question content -- every
uncertainty is surfaced via `review_flags` / `extraction_status`, never
silently resolved.

Paper layout, confirmed by direct visual inspection of rendered pages
(2026-10-10), Set G1 (representative of the batch -- all 12 are the same
NTA "Accessible Version" scan template):
  - 24 pages per booklet, 180 questions, strict two-column layout with a
    vertical rule roughly at the horizontal midline.
  - Question stems: "<n>.  <stem...>" (n = 1..180), options inline below
    as "(1)", "(2)", "(3)", "(4)" (digit-style, NOT a/b/c/d).
  - No answer key is present anywhere in the booklet -- page 24 ("Space
    For Rough Work") is the last page. This is a pure question-paper
    scan, not an answer-key document. Every extracted question will
    therefore always be missing an answer (flagged `missing_answer`,
    never fabricated).
  - Some questions have diagram-only stems/options (circuit diagrams,
    pulley figures, organic-structure skeletal diagrams, match-the-column
    tables) that OCR cannot usefully transcribe; these are flagged
    `possible_image_dependency` / `missing_options` rather than forced.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageOps

PIPELINE_VERSION = "pyq_image_pipeline_ocr_v1"

# Must point at a real local Tesseract install. Never downloaded here;
# reuses the install already present on this machine (v5.5.0).
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# 400 DPI chosen over 300/500/600 after an explicit A/B sweep on the
# pilot pages (see docs/audits/NEET_PAST_PAPERS_V3_PROGRESS.md Step 4-5):
# 400 DPI with psm 6 gave the best combined question-number recall
# (34/34) and option-label completeness (23/34) of the configurations
# tried; psm 4 and psm 11 both recalled fewer questions at every DPI,
# and 500/600 DPI lost question recall without a compensating option gain.
OCR_DPI = 400
# Tesseract config: psm 6 = "assume a single uniform block of text".
# Each page is split into its two physical columns before OCR (see
# `render_page_columns`), so each OCR call only ever sees one column,
# which is itself a roughly uniform single-column block of text -- this
# avoids Tesseract's own multi-column layout analysis (psm 3) silently
# interleaving the two columns in the wrong reading order.
TESSERACT_CONFIG = "--oem 3 --psm 6"

# Accepts "." (correct), but also "," and ";" -- Tesseract frequently
# misreads the period after a question number as a comma/semicolon in
# this paper's serif numeral font (confirmed on pilot page 2, Q4: "4,"
# rendered for "4."). The marker is still unambiguous (line-start digit
# immediately followed by punctuation and whitespace), so accepting the
# OCR's common punctuation substitution is a structural-noise tolerance,
# not a content guess -- it never alters what digit was read.
_Q_RE = re.compile(r"(?m)^\s*(\d{1,3})\s*[.,;)]\s+")
_OPT_RE = re.compile(r"\n\s*\(?([1-4])\)\s*")
_REPLACEMENT_CHAR = "\ufffd"
# Tesseract's own "noise" output: isolated single/double punctuation-only
# tokens, or lines that are mostly non-alphanumeric, are a strong signal
# of a garbled OCR region (diagram, table rule, stray mark).
_GARBLE_RE = re.compile(r"[^\w\s().,;:+\-=/%°²³\u2013\u2014]")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --- rendering -----------------------------------------------------------

def render_page_image(doc: fitz.Document, page_index: int, dpi: int = OCR_DPI) -> Image.Image:
    """Render one page (0-indexed) to a PIL image at `dpi`. Read-only:
    never writes back into the source PDF."""
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    mode = "RGB" if pix.alpha == 0 else "RGBA"
    img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    if mode == "RGBA":
        img = img.convert("RGB")
    return img


def preprocess_image(img: Image.Image, *, grayscale: bool = True, autocontrast: bool = True) -> Image.Image:
    """Minimal, measured preprocessing. Both steps were A/B tested on the
    pilot pages against the raw render (see
    docs/audits/NEET_PAST_PAPERS_V3_PROGRESS.md Step 1 for numbers) before
    being enabled by default -- this is not speculative over-engineering;
    binarization/deskew were tried and did NOT measurably help on these
    clean, already-high-contrast scans, so they are intentionally omitted."""
    out = img
    if grayscale:
        out = ImageOps.grayscale(out)
    if autocontrast:
        out = ImageOps.autocontrast(out, cutoff=1)
    return out


def split_columns(img: Image.Image, gutter_frac: float = 0.0) -> tuple[Image.Image, Image.Image]:
    """Split a page image into left/right column halves. `gutter_frac` can
    widen the excluded middle strip if a column rule needs to be avoided;
    0.0 is a plain half/half split, which is sufficient for this paper's
    layout (content never crosses the midline on this template)."""
    w, h = img.size
    mid = w // 2
    gutter = int(w * gutter_frac)
    left = img.crop((0, 0, mid - gutter, h))
    right = img.crop((mid + gutter, 0, w, h))
    return left, right


# --- OCR -------------------------------------------------------------------

@dataclass
class OcrToken:
    text: str
    conf: float
    left: int
    top: int
    width: int
    height: int
    block_num: int = 0
    par_num: int = 0
    line_num: int = 0


@dataclass
class OcrColumnResult:
    text: str
    tokens: list[OcrToken] = field(default_factory=list)
    mean_conf: float = 0.0
    # The exact image this OCR pass ran on (post-preprocess, pre-split-offset
    # local coordinates), kept so a later targeted crop-and-upscale pass can
    # re-read a small region at full original resolution instead of a fresh
    # re-render. offset_x/offset_y record where this column sits in the
    # full-page coordinate system the token boxes above are already
    # expressed in, so a caller can convert a page-coordinate box back to
    # this image's local coordinates for cropping.
    image: Image.Image | None = None
    offset_x: int = 0
    offset_y: int = 0


def ocr_image(img: Image.Image, *, offset_x: int = 0, offset_y: int = 0) -> OcrColumnResult:
    """Run Tesseract on a single image (one column), returning both plain
    text (for parsing) and per-token bounding boxes (for later
    diagram/option coordinate association) offset back into full-page
    coordinates."""
    data = pytesseract.image_to_data(
        img, config=TESSERACT_CONFIG, output_type=pytesseract.Output.DICT
    )
    tokens: list[OcrToken] = []
    confs: list[float] = []
    for i, txt in enumerate(data["text"]):
        if not txt or not txt.strip():
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1.0
        if conf >= 0:
            confs.append(conf)
        tokens.append(OcrToken(
            text=txt,
            conf=conf,
            left=int(data["left"][i]) + offset_x,
            top=int(data["top"][i]) + offset_y,
            width=int(data["width"][i]),
            height=int(data["height"][i]),
            block_num=int(data.get("block_num", [0] * len(data["text"]))[i]),
            par_num=int(data.get("par_num", [0] * len(data["text"]))[i]),
            line_num=int(data.get("line_num", [0] * len(data["text"]))[i]),
        ))
    text = pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    return OcrColumnResult(text=text, tokens=tokens, mean_conf=mean_conf,
                            image=img, offset_x=offset_x, offset_y=offset_y)


@dataclass
class OcrPageResult:
    source_file: str
    page_number: int  # 1-indexed
    text: str  # left column then right column, reading order
    left: OcrColumnResult
    right: OcrColumnResult


def ocr_page(doc: fitz.Document, page_index: int, source_file: str, *,
              dpi: int = OCR_DPI, preprocess: bool = True) -> OcrPageResult:
    img = render_page_image(doc, page_index, dpi=dpi)
    if preprocess:
        img = preprocess_image(img)
    left_img, right_img = split_columns(img)
    w = img.size[0]
    mid = w // 2
    left_res = ocr_image(left_img, offset_x=0, offset_y=0)
    right_res = ocr_image(right_img, offset_x=mid, offset_y=0)
    full_text = left_res.text + "\n" + right_res.text
    return OcrPageResult(
        source_file=source_file,
        page_number=page_index + 1,
        text=full_text,
        left=left_res,
        right=right_res,
    )


def ocr_pdf_pages(pdf_path: Path, page_indices: list[int], *, dpi: int = OCR_DPI,
                   preprocess: bool = True) -> list[OcrPageResult]:
    """OCR a specific subset of pages (0-indexed) of one PDF. Used for the
    pilot -- deliberately NOT run across all 288 pages of the 12-PDF
    batch in this task."""
    doc = fitz.open(pdf_path)
    try:
        results = [
            ocr_page(doc, i, str(pdf_path), dpi=dpi, preprocess=preprocess)
            for i in page_indices
        ]
    finally:
        doc.close()
    return results


# --- parsing (OCR-noise-tolerant, adapted from extractor.py's segment_2015) -

@dataclass
class OcrExtractedQuestion:
    source_file: str
    page_number: int
    question_number_raw: str | None
    stem_text: str | None
    options: dict | None
    answer_raw: str | None  # always None for this batch -- no answer key in the scan
    raw_block_text: str
    extraction_status: str  # COMPLETE | NEEDS_REVIEW
    extraction_confidence: float
    review_flags: list[str] = field(default_factory=list)
    has_image_reference: bool = False


_IMAGE_KEYWORDS = [
    "figure", "diagram", "graph", "as shown", "shown below", "shown in",
    "given figure", "following figure", "column", "match",
]


def _has_image_keyword(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in _IMAGE_KEYWORDS)


def _garble_ratio(text: str) -> float:
    if not text:
        return 0.0
    bad = len(_GARBLE_RE.findall(text))
    return bad / max(1, len(text))


def parse_ocr_page_text(full_text: str, source_file: str, page_number: int) -> list[OcrExtractedQuestion]:
    """Segment one page's OCR'd text into questions. Mirrors
    `extractor.segment_2015`'s conservative-flagging discipline, adapted
    for: (a) digit-only option markers "(1)".."(4)" without the trailing
    requirement of a following newline (OCR often drops/merges
    whitespace), (b) no answer-key marker to look for at all in this
    source (always flagged missing_answer, never guessed), (c) an
    explicit OCR-garble-ratio check in addition to the existing
    replacement-char heuristic, since Tesseract emits noisy ASCII/Latin
    punctuation soup rather than the U+FFFD replacement character pypdf
    would emit."""
    out: list[OcrExtractedQuestion] = []
    raw_matches = list(_Q_RE.finditer(full_text))

    # drop non-increasing / too-large jumps, same discipline as extractor.py
    matches = []
    last_num: int | None = None
    for m in raw_matches:
        try:
            num = int(m.group(1))
        except ValueError:
            continue
        if last_num is None or (last_num < num <= last_num + 5):
            matches.append(m)
            last_num = num

    for i, m in enumerate(matches):
        q_num = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        block = full_text[start:end]

        flags: list[str] = []
        status = "COMPLETE"
        confidence = 0.75  # lower OCR-source baseline than the 0.9 text-layer baseline

        opt_matches = list(_OPT_RE.finditer(block))
        if len(opt_matches) >= 4:
            stem = block[: opt_matches[0].start()].strip()
            opts = {}
            for j in range(4):
                ostart = opt_matches[j].end()
                oend = opt_matches[j + 1].start() if j + 1 < 4 else len(block)
                opts[str(j + 1)] = block[ostart:oend].strip()
        else:
            stem = block.strip()
            opts = None
            flags.append("missing_options")
            status = "NEEDS_REVIEW"
            confidence -= 0.3

        # No answer key exists anywhere in this source document (confirmed
        # by visual inspection of the final page). Never search for or
        # infer one -- always flag.
        answer_raw = None
        flags.append("missing_answer")
        status = "NEEDS_REVIEW"

        if _REPLACEMENT_CHAR in stem or (opts and any(_REPLACEMENT_CHAR in v for v in opts.values())):
            flags.append("ocr_glyph_error_signal")
            status = "NEEDS_REVIEW"
            confidence -= 0.1

        stem_garble = _garble_ratio(stem)
        if stem_garble > 0.08:
            flags.append("ocr_high_garble_ratio")
            status = "NEEDS_REVIEW"
            confidence -= 0.2

        has_img_ref = _has_image_keyword(stem) or (opts is not None and sum(len(v) for v in opts.values()) < 12)
        if has_img_ref:
            flags.append("possible_image_dependency")

        if len(stem) < 5:
            flags.append("uncertain_question_boundary")
            status = "NEEDS_REVIEW"
            confidence -= 0.2

        confidence = max(0.1, min(1.0, confidence))
        out.append(OcrExtractedQuestion(
            source_file=source_file,
            page_number=page_number,
            question_number_raw=q_num,
            stem_text=stem,
            options=opts,
            answer_raw=answer_raw,
            raw_block_text=block[:4000],
            extraction_status=status,
            extraction_confidence=confidence,
            review_flags=flags,
            has_image_reference=has_img_ref,
        ))
    return out



# --- Session 3: targeted label-crop recovery for missing_options cases -----
#
# Diagnosis of the 11/34 pilot failures (see
# docs/audits/NEET_PAST_PAPERS_V3_PROGRESS.md "Session 3" for the full
# breakdown) found three *distinct* failure modes, not one generic cause:
#   1. Math/fraction-heavy options (7 of 11, all page 2/Physics): the
#      option MARKER glyph ("(1)".."(4)") is misread as "@)", "9", a bare
#      digit, etc. because Tesseract's line segmentation fractures a
#      numerator/denominator pair across lines and the label sits at an
#      unexpected line start. The label glyph itself is recoverable with a
#      tightly cropped, upscaled, whitelist-constrained re-OCR pass; this
#      is what the functions below target.
#   2. Match-table options (2 of 11, Q60/Q122, both Biology "Column I /
#      Column II" layouts): these are not linear "(n) text" options at
#      all -- forcing them through the label-crop path would be a
#      structural misfit, not a fix. Detected and flagged separately
#      (`match_table_structure`), never force-parsed.
#   3. Diagram-only options (2 of 11, Q166/Q170, Chemistry skeletal
#      structures): the options are images, not text -- there is no label
#      text to recover. Detected and flagged separately
#      (`options_are_images`), consistent with the existing
#      image-association confidence-tier discipline; never force-OCR'd.

_MATCH_TABLE_RE = re.compile(
    r"column\s*[-:]?\s*i\b.*column\s*[-:]?\s*ii|match\s+the\s+following",
    re.IGNORECASE | re.DOTALL,
)

# Loose candidate for a possibly-garbled option-label glyph: a short token
# (<=3 chars) built only from characters Tesseract is observed to confuse
# with "(1)".."(4)" in this font (parens, the digits themselves, and the
# specific letter/number look-alikes confirmed from the pilot's raw OCR
# output: "@)" for garbled "(1)", "Q)" for garbled "(1)"/"(2)", "9" for
# garbled "(2)"). This candidate filter is intentionally permissive -- it
# only decides *where* to crop and re-OCR with a constrained whitelist; it
# never by itself decides what digit the option actually is.
_LABEL_CANDIDATE_RE = re.compile(r"^[\(\)@Qq0-9OoSsGglI]{1,3}[\)\.]?$")
# The constrained second pass is only trusted to output exactly one of
# these digits; whitelist-constrained Tesseract still occasionally emits
# nothing recognizable, which must be treated as "could not recover", not
# an incorrect digit.
_LABEL_WHITELIST_RE = re.compile(r"[1-4]")


def _group_tokens_into_lines(tokens: list) -> list[dict]:
    """Group a column's tokens into visual lines using Tesseract's own
    block/par/line numbering, each with the line's bounding box and
    concatenated text, sorted top-to-bottom. This is what makes the
    label-crop recovery pass position-aware instead of relying on the
    (sometimes-misordered) flattened text string."""
    by_key: dict = {}
    for t in tokens:
        key = (t.block_num, t.par_num, t.line_num)
        by_key.setdefault(key, []).append(t)
    lines = []
    for key, toks in by_key.items():
        toks_sorted = sorted(toks, key=lambda t: t.left)
        left = min(t.left for t in toks_sorted)
        top = min(t.top for t in toks_sorted)
        right = max(t.left + t.width for t in toks_sorted)
        bottom = max(t.top + t.height for t in toks_sorted)
        text = " ".join(t.text for t in toks_sorted)
        lines.append({
            "left": left, "top": top, "right": right, "bottom": bottom,
            "text": text, "tokens": toks_sorted,
        })
    lines.sort(key=lambda l: l["top"])
    return lines


def _crop_and_reread_label(column_img, token, *,
                            column_offset_x: int, column_offset_y: int,
                            upscale: int = 3, pad: int = 6):
    """Crop a single candidate label token out of the ORIGINAL rendered
    column image (same 400 DPI source, no re-render), upscale it, and run
    a focused second Tesseract pass with a character whitelist restricted
    to the option-marker alphabet only (never applied to option body
    text, which needs full alphanumeric+symbol recognition). Returns a
    single confirmed digit "1".."4", or None if the constrained pass still
    can't resolve one -- callers must treat None as "not recovered", never
    guess a digit."""
    local_left = token.left - column_offset_x
    local_top = token.top - column_offset_y
    box = (
        max(0, local_left - pad),
        max(0, local_top - pad),
        min(column_img.size[0], local_left + token.width + pad),
        min(column_img.size[1], local_top + token.height + pad),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return None
    crop = column_img.crop(box)
    crop = crop.resize((crop.size[0] * upscale, crop.size[1] * upscale), Image.LANCZOS)
    config = "--oem 3 --psm 7 -c tessedit_char_whitelist=1234()"
    text = pytesseract.image_to_string(crop, config=config)
    digits = _LABEL_WHITELIST_RE.findall(text)
    if len(digits) == 1:
        return digits[0]
    return None


def classify_unrecovered_question(question) -> None:
    """Mutates `question.review_flags` in place to distinguish the
    match-table and diagram-only failure modes from an ordinary
    recoverable-but-unrecovered `missing_options` case. Called only on
    questions that still have `options is None` after the label-crop
    recovery pass (or where recovery was never attempted, e.g. unit
    tests exercising pure text parsing)."""
    if question.options is not None:
        return
    block = question.raw_block_text or ""
    if _MATCH_TABLE_RE.search(block):
        if "match_table_structure" not in question.review_flags:
            question.review_flags.append("match_table_structure")
        if "requires_table_extraction" not in question.review_flags:
            question.review_flags.append("requires_table_extraction")
        return
    # Diagram-only heuristic: look only at the portion of the block AFTER
    # the stem (the stem itself is often long legitimate prose and must
    # not count against this check) -- if very little alphanumeric
    # content survives there, the options are most likely chemical/
    # skeletal structure images rather than text Tesseract failed to
    # read. Treated as a distinct, explicit limitation rather than
    # silently leaving it under the generic `missing_options` flag.
    stem = question.stem_text or ""
    remainder = block
    idx = block.find(stem) if stem else -1
    if idx >= 0:
        remainder = block[idx + len(stem):]
    alnum = sum(c.isalnum() for c in remainder)
    if 0 < alnum < 40:
        if "options_are_images" not in question.review_flags:
            question.review_flags.append("options_are_images")
        if "possible_image_dependency" not in question.review_flags:
            question.review_flags.append("possible_image_dependency")


def recover_options_via_label_crop(question, column, q_top: int, q_bottom: int) -> bool:
    """Second-pass recovery for a question flagged `missing_options` by
    `parse_ocr_page_text`. Operates on the same column's captured tokens
    and original rendered image -- no re-render, no new OCR of the whole
    page. Finds up to 4 label-candidate lines within this question's
    vertical span [q_top, q_bottom) in PAGE coordinates, crops+upscales
    each candidate's label glyph and re-reads it with a digit-only
    whitelist, and if exactly 4 distinct digits 1-4 are recovered in
    increasing order, rebuilds `question.options` from each label line's
    trailing text plus any continuation lines before the next label.
    Returns True if recovery succeeded (question mutated in place);
    False otherwise (question left untouched, still `options is None`,
    for the caller to classify via `classify_unrecovered_question`)."""
    if question.options is not None or column.image is None:
        return False
    block = question.raw_block_text or ""
    if _MATCH_TABLE_RE.search(block):
        return False  # not a linear-option question at all; don't force it

    lines = _group_tokens_into_lines(column.tokens)
    in_span = [l for l in lines if q_top <= l["top"] < q_bottom]
    if not in_span:
        return False

    # No positional (x-offset) filter here: this paper's stem-continuation
    # lines share the same left indent as the option labels (hanging
    # indent), so x-position alone cannot distinguish them. The glyph
    # charset regex is the discriminator instead -- ordinary word tokens
    # ("from", "ends", "due") never match it, so false positives from
    # continuation text are not expected; any that do slip through are
    # caught downstream when the constrained re-OCR fails to resolve a
    # valid, non-duplicate digit for all four candidates.
    # The question's own opening line (containing the question-number
    # marker, e.g. "1. A wire...") sits at in_span[0] and can itself look
    # like a label candidate (a bare leading digit) -- exclude it
    # explicitly so the question number is never mistaken for option "1".
    candidate_pool = in_span[1:] if len(in_span) > 1 else []
    candidates = []
    for l in candidate_pool:
        first_tok = l["tokens"][0]
        if _LABEL_CANDIDATE_RE.match(first_tok.text.strip()):
            candidates.append((l, first_tok))

    if len(candidates) < 4:
        return False

    recovered: dict = {}
    recovered_lines = []
    for l, tok in candidates:
        digit = _crop_and_reread_label(
            column.image, tok,
            column_offset_x=column.offset_x, column_offset_y=column.offset_y,
        )
        if digit is None:
            continue
        if digit in recovered:
            continue  # ambiguous duplicate -- do not overwrite a prior read
        recovered[digit] = ""
        recovered_lines.append((int(digit), l))

    if sorted(recovered.keys()) != ["1", "2", "3", "4"]:
        return False  # could not confidently recover all four -- no guessing

    recovered_lines.sort(key=lambda x: x[0])
    # Honesty check: content strictly ABOVE the first recovered label (e.g.
    # a fraction's numerator line, rendered on its own row above the
    # "(n) denominator" row) belongs to option 1 but sits outside every
    # band computed below (bands only run forward from each label's own
    # top). This is a real, separate content-completeness gap from the
    # label-recovery itself -- flagged explicitly rather than silently
    # delivering a truncated option body under a "recovered" label.
    first_label_top = recovered_lines[0][1]["top"]
    recovered_line_objs = [l for _, l in recovered_lines]
    pre_label_candidates = [l for l, _ in candidates if l["top"] < first_label_top and l not in recovered_line_objs]

    # Session 4 fix (narrow, targeted at the 3 math_fraction_partial_capture
    # cases from Session 3 -- Q4, Q6, Q8 of the pilot): a short token that
    # matches the permissive label-candidate charset is not automatically a
    # dropped fraction fragment. Two distinct false-positive sources were
    # confirmed by direct inspection of the real OCR line output (see
    # docs/audits/NEET_PAST_PAPERS_V3_PROGRESS.md Session 4):
    #   - Q4: the line "6 kg" (a pulley-diagram mass label, not a formula)
    #     tokenizes with a bare leading "6", which matches the permissive
    #     charset regex purely by coincidence.
    #   - Q6: the line "80" is a fragment of the stem sentence "...with a
    #     velocity of 80 m/s..." that Tesseract split onto its own OCR
    #     "line", not a dropped option fragment.
    # The discriminator confirmed by direct inspection: a genuine dropped
    # fraction/superscript fragment (Q8's "91", "101", "103", "144") is
    # always an ISOLATED single OCR token on its own line -- nothing else
    # shares that line. "6 kg" (Q4) and "80 m/s. The height of the tower
    # is..." (Q6) are ordinary multi-token prose lines whose first token
    # merely happens to match the permissive label-candidate charset; the
    # rest of the line (" kg", " m/s. The height...") immediately shows
    # it's stem continuation, not a split-off option fragment. Using
    # `question.stem_text` to distinguish these was tried first and
    # rejected: for a question whose initial marker-regex parse already
    # failed (exactly the questions reaching this recovery path),
    # `stem_text` is set to the ENTIRE raw block, so it trivially contains
    # every line's text including genuine orphans like "91" -- that check
    # produced a false negative on Q8. Token-count is the correct,
    # narrower signal.
    def _is_isolated_single_token_line(line: dict) -> bool:
        return len(line["tokens"]) == 1

    pre_label_candidates = [l for l in pre_label_candidates if _is_isolated_single_token_line(l)]
    math_layout_truncated = bool(pre_label_candidates)

    # Session 4 fix, part 2 (Q8): a short numeric "candidate" line sitting
    # BETWEEN two already-recovered labels (e.g. an isotope mass-number
    # superscript like "101" rendered on its own row) is -- per the same
    # direct inspection -- always the FOLLOWING option's own split-off
    # fragment, not a continuation of the option whose label happens to sit
    # just above it. The original band computation attributed it to the
    # wrong (preceding) option. Shift each band's start forward to that
    # fragment's position so it attaches to the option it actually belongs
    # to; this does not change which digit any label resolved to (that was
    # already independently confirmed via the whitelist crop re-OCR), it
    # only corrects which recovered option body a non-label OCR line of
    # already-recovered text gets appended to.
    all_candidate_tops = sorted({
        l["top"] for l, _ in candidates if _is_isolated_single_token_line(l)
    })
    recovered_tops = {l["top"] for _, l in recovered_lines}
    band_starts = []
    for idx, (digit, l) in enumerate(recovered_lines):
        start = l["top"]
        if idx > 0:
            prev_top = recovered_lines[idx - 1][1]["top"]
            orphan_tops = [
                t for t in all_candidate_tops
                if prev_top < t < start and t not in recovered_tops
            ]
            if orphan_tops:
                start = min(orphan_tops)
        band_starts.append(start)
    band_ends = band_starts[1:] + [q_bottom]

    for idx, (digit, l) in enumerate(recovered_lines):
        band_top = band_starts[idx]
        band_bottom = band_ends[idx]
        band_lines = [x for x in in_span if band_top <= x["top"] < band_bottom]
        pieces = []
        for bl in band_lines:
            txt = bl["text"]
            if bl is l:
                rest_tokens = bl["tokens"][1:]
                txt = " ".join(t.text for t in rest_tokens)
            pieces.append(txt.strip())
        recovered[str(digit)] = " ".join(p for p in pieces if p).strip()

    if any(not v for v in recovered.values()):
        return False  # a "recovered" option with empty body is not usable

    question.options = {k: recovered[k] for k in ["1", "2", "3", "4"]}
    if "missing_options" in question.review_flags:
        question.review_flags.remove("missing_options")
    question.review_flags.append("options_recovered_via_label_crop")
    if math_layout_truncated:
        # Option 1's body is missing content that sat above its label line
        # (a split fraction numerator, most often) -- the LABEL recovery
        # succeeded (we know this is genuinely option 1, not a guess) but
        # the option TEXT is known-incomplete. Never silently mark this
        # COMPLETE.
        question.review_flags.append("math_fraction_partial_capture")
        question.extraction_confidence = max(0.1, question.extraction_confidence - 0.05)
    elif question.extraction_status == "NEEDS_REVIEW" and "missing_answer" not in question.review_flags:
        question.extraction_status = "COMPLETE"
    question.extraction_confidence = min(1.0, question.extraction_confidence + 0.1)
    return True


def parse_and_recover_page(page_result):
    """Full page pipeline used by the (re-run) pilot: parse each column's
    OCR text, then run the targeted label-crop recovery pass on anything
    flagged `missing_options`, then classify whatever is still
    unrecovered into the match-table / diagram-only / generic buckets.
    Kept separate from `parse_ocr_page_text` (which stays pure-text, no
    image/OCR dependency) so the original 10 pure-parsing unit tests are
    unaffected."""
    left_qs = parse_ocr_page_text(page_result.left.text, page_result.source_file, page_result.page_number)
    right_qs = parse_ocr_page_text(page_result.right.text, page_result.source_file, page_result.page_number)

    def _recover_all(qs, column):
        lines = _group_tokens_into_lines(column.tokens)
        q_tops = []
        for q in qs:
            q_top = None
            for l in lines:
                if re.match(rf"^\s*{re.escape(q.question_number_raw)}\s*[.,;)]", l["text"]):
                    q_top = l["top"]
                    break
            q_tops.append(q_top if q_top is not None else 0)
        col_bottom = max((l["bottom"] for l in lines), default=0) + 1
        for i, q in enumerate(qs):
            if q.options is not None:
                continue
            top = q_tops[i]
            bottom = q_tops[i + 1] if i + 1 < len(qs) and q_tops[i + 1] else col_bottom
            if not recover_options_via_label_crop(q, column, top, bottom):
                classify_unrecovered_question(q)

    _recover_all(left_qs, page_result.left)
    _recover_all(right_qs, page_result.right)
    return left_qs + right_qs
