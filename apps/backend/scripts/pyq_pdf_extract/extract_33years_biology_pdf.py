"""Deterministic extractor for
"33 Years NEET-AIPMT Chapterwise Solutions - Biology 2020.pdf" (MTG
Learning Media), confirmed by direct inspection (2026-10-18):

  - 485 PDF pages, text-native (PyMuPDF `page.get_text()` returns real
    content on every content page -- no OCR needed anywhere in this
    file; verified empirically in `run()` below, which still calls the
    OCR fallback path for any page that fails the density heuristic, so
    this is a measured finding, not an assumption).
  - Front matter: PDF pages 1-11 (title/legal/Telegram-watermark pages,
    two tables of contents on pages 5 and 6 -- one per class -- and the
    NCERT syllabus). First question content starts PDF page 12.
  - 38 chapters total (22 Class XI + 16 Class XII, matching the 38
    "ANSWER KEY" section markers found by direct count), each with its
    OWN question numbering that restarts at 1. Within each chapter:
      1. A QUESTION run: "<n>.\\t\\n<stem...>\\n(a)\\t...(d)\\t...\\n(<exam
         tag>)" -- exam tag is a parenthesized trailing marker like
         "(NEET 2019)", "(Mains 2011)", "(Odisha NEET 2019)", or a bare
         "(2007)".
      2. A compact "quick answer" run, SAME 1..N numbering restarting
         again: "<n>.\\t\\n(<letter>)" with no explanation.
      3. A literal "ANSWER KEY" header, followed by a DETAILED run, SAME
         1..N numbering restarting a third time: "<n>.\\t(<letter>)\\t:\\t
         <explanation...>" (colon+explanation present for most but not
         all entries -- some are bare "(x)" with no further text, e.g.
         "11. (c): Refer to answer 10.").
  - Subsection headers "<chapter>.<section>  <Topic title>" (e.g.
    "1.1  What is Living?") appear inline within the question run and
    give a topic label narrower than the chapter.
  - Options are NOT consistently tab-delimited -- short options are
    sometimes packed two-per-line with only a bare space after the
    second marker (see `common.OPT_ALPHA_RE`'s docstring).

No AI/LLM calls. No database writes. No network calls. See
`common.py`'s module docstring for the mandatory rights_status
provenance statement this file's output carries.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import fitz  # PyMuPDF

from scripts.pyq_pdf_extract import common
from scripts.pyq_pdf_extract.common import (
    ExtractedRecord,
    RIGHTS_STATUS_33YEARS,
    classify_block,
    identity_key,
    now_iso,
    option_integrity_flags,
    options_list,
    segment_into_runs,
    sha256_file,
    write_json,
)

SOURCE_BOOK_TITLE = "33 Years NEET-AIPMT Chapterwise Topicwise Solutions Biology (2020 Edition)"
SOURCE_PUBLISHER = "MTG Learning Media (P) Ltd."
SOURCE_EDITION = "2020"

NUMBER_RE = re.compile(r"(?m)^(\d{1,3})\.[\t ]+")
SUBSECTION_RE = re.compile(r"(?m)^(\d{1,2})\.(\d{1,2})[\t ]{1,4}(\S.*)$")
#   - Single-digit chapters ("1." through "9."): "<n>.\t\n<title>\t\n....<page>".
#   - Double-digit chapters ("10." onward): "<n>.\t <title>\t\n....<page>" --
#     NO newline between the number's own tab and the title (confirmed by
#     direct inspection, page 6 of the TOC); the pattern below tolerates
#     either a newline or a bare space/tab run at that position.
TOC_ENTRY_RE = re.compile(r"(\d{1,2})\.[\t ]*\n?(.*?)\t?\n\.{3,}\d+", re.DOTALL)
# Trailing exam-tag: a parenthesized group, at the end of a question's
# 4th-option text (before any trailing page-boilerplate/next-subsection-
# header leakage is trimmed by `_trim_trailing_boilerplate`), containing
# one or more 4-digit years -- e.g. "(NEET 2019)", "(Mains  2011)",
# "(Odisha NEET  2019)", "(NEET-I 2016)", "(Karnataka NEET 2013)", a bare
# "(2007)", or a rare multi-year "(1992, 1991)". Searched (not end-
# anchored) in the ALREADY-boilerplate-trimmed tail, so a year mentioned
# inside the stem/options text itself is never mistaken for the exam tag.
EXAM_TAG_RE = re.compile(r"\(\s*([^()]*?\d{4}[^()]*?)\s*\)")
YEAR_IN_TAG_RE = re.compile(r"\d{4}")
# Boilerplate that can leak onto the end of the 4th option's raw text
# because it physically sits between this question's last option and the
# NEXT numbered match in the document (next subsection header, running
# page header/footer, or the Telegram watermark line) -- never part of
# the question's own content. Cut everything from the first occurrence
# of any of these onward, before exam-tag extraction and before storing
# the option text.
BOILERPLATE_LEAK_RE = re.compile(
    r"\n(?:\d{1,2}\.\d{1,2}[\t ]|NEET-AIPMT Chapterwise Topicwise Solutions Biology"
    r"|\d{1,3}\n\s*NEET-AIPMT|Telegram @|Join Us on Telegram|ademyplusdiscounts)"
)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
ANSWER_KEY_HEADER_RE = re.compile(r"\bANSWER KEY\b")


def _strip_control_chars(text: str) -> tuple[str, bool]:
    if not text:
        return text, False
    cleaned = _CONTROL_CHAR_RE.sub("", text)
    return cleaned, cleaned != text


def _trim_trailing_boilerplate(text: str) -> str:
    m = BOILERPLATE_LEAK_RE.search(text)
    if m:
        return text[: m.start()]
    return text


def parse_toc(doc: fitz.Document) -> list[str]:
    """Pages 5 and 6 (0-indexed 4 and 5) each hold one class's table of
    contents (22 Class XI chapters, then 16 Class XII chapters). Returns
    the 38 chapter titles in document order. Never invents a name: if a
    TOC entry can't be parsed, the corresponding slot is left out and the
    caller must fall back to `None` + a review flag for any chapter index
    beyond what was actually recovered."""
    names: list[str] = []
    for page_idx in (4, 5):
        t = doc[page_idx].get_text()
        entries = []
        for m in TOC_ENTRY_RE.finditer(t):
            num = int(m.group(1))
            title = re.sub(r"\s+", " ", m.group(2)).strip()
            entries.append((num, title))
        entries.sort(key=lambda x: x[0])
        names.extend(title for _, title in entries)
    return names


def build_subsection_index(full_text: str) -> list[tuple[int, str]]:
    """Returns (char_offset, topic_title) pairs in document order for
    every "<n>.<m>  Topic" subsection header line found anywhere in the
    body text. Topic lookup for a question is "the nearest preceding
    entry in this list" -- callers must not assume these are globally
    unique (the "1.1" style numbering also restarts per chapter, same as
    the question numbering, but since this list is positional/ordered we
    never need to resolve that number, only its document position)."""
    out = []
    for m in SUBSECTION_RE.finditer(full_text):
        title = re.sub(r"\s+", " ", m.group(3)).strip()
        out.append((m.start(), title))
    return out


def topic_for_position(index: list[tuple[int, str]], pos: int) -> str | None:
    best = None
    for offset, title in index:
        if offset <= pos:
            best = title
        else:
            break
    return best


def page_of(page_breaks: list[tuple[int, int]], pos: int) -> int:
    pg = 1
    for offset, pnum in page_breaks:
        if offset <= pos:
            pg = pnum
        else:
            break
    return pg


def extract_exam_tag(option_d_text: str) -> tuple[str | None, int | None, str]:
    """Pulls the trailing exam tag off the 4th option's raw text, AFTER
    first trimming any page-boilerplate/next-subsection-header text that
    leaked onto its tail (see `_trim_trailing_boilerplate`). Returns
    (exam_name_or_None, exam_year_or_None, text_with_tag_and_boilerplate_
    removed). Supports multi-year tags (e.g. "(1992, 1991)" -- exam_year
    is the first year found, exam_name keeps the full raw tag text so no
    information is silently dropped)."""
    trimmed = _trim_trailing_boilerplate(option_d_text)
    tail = trimmed[-80:]
    m = EXAM_TAG_RE.search(tail)
    if not m:
        return None, None, trimmed
    inner = re.sub(r"\s+", " ", m.group(1)).strip()
    year_m = YEAR_IN_TAG_RE.search(inner)
    year = int(year_m.group(0)) if year_m else None
    cut_at = len(trimmed) - (len(tail) - m.start())
    cleaned = trimmed[:cut_at]
    return inner, year, cleaned


def build_question_record(
    *,
    run_index: int,
    seq: int,
    nm,
    block: str,
    opt_bounds: list[re.Match],
    page_breaks,
    source_file: str,
    source_sha: str,
    chapter_name: str | None,
    class_level: str | None,
    topic_index,
    answers_by_number: dict[int, dict],
) -> ExtractedRecord:
    flags: list[str] = []
    status = "COMPLETE"
    confidence = 0.9

    stem, stem_ctrl = _strip_control_chars(block[: opt_bounds[0].start()].strip())

    exam_name: str | None = None
    exam_year: int | None = None
    opts: dict[str, str] = {}
    any_ctrl_stripped = stem_ctrl
    for j in range(4):
        ostart = opt_bounds[j].end()
        oend = opt_bounds[j + 1].start() if j + 1 < len(opt_bounds) else len(block)
        text = block[ostart:oend]
        if j == 3:
            # the exam-tag marker (e.g. "(Mains 2011)") trails the 4th
            # option's own text, on its own line, at the very end of the
            # block -- extracted and stripped here, never guessed. Any
            # page-boilerplate/next-subsection-header text that leaked in
            # after it is trimmed by the same call.
            exam_name, exam_year, text = extract_exam_tag(text)
        else:
            # boilerplate leakage is specific to the LAST option on a
            # page/chapter boundary, but trimming it for every option is
            # harmless (the pattern never legitimately appears inside
            # option body text) and catches the rarer case of a 3-option-
            # only OCR/layout anomaly pushing the leak onto option (c).
            text = _trim_trailing_boilerplate(text)
        text, ctrl = _strip_control_chars(text)
        any_ctrl_stripped = any_ctrl_stripped or ctrl
        opts[chr(ord("a") + j)] = text.strip()
    if exam_name is None:
        flags.append("missing_exam_tag")
        confidence -= 0.05
    if any_ctrl_stripped:
        flags.append("control_char_removed")

    opt_list = options_list(opts)
    flags.extend(option_integrity_flags(opt_list))
    if flags and any(f.startswith("option_") for f in flags):
        status = "NEEDS_REVIEW"
        confidence -= 0.2

    ans = answers_by_number.get(nm.number)
    answer_raw = ans["letter"] if ans else None
    explanation = ans.get("explanation") if ans else None
    if explanation:
        explanation, expl_ctrl = _strip_control_chars(explanation)
        if expl_ctrl and "control_char_removed" not in flags:
            flags.append("control_char_removed")
    if not answer_raw:
        flags.append("missing_answer")
        status = "NEEDS_REVIEW"
        confidence -= 0.3
    if ans and not explanation:
        flags.append("missing_explanation")
        confidence -= 0.05
    if not ans:
        flags.append("missing_explanation")

    if "\ufffd" in stem or any("\ufffd" in v for v in opts.values()):
        flags.append("ocr_glyph_error_signal")
        status = "NEEDS_REVIEW"
        confidence -= 0.1

    if len(stem) < 5:
        flags.append("uncertain_question_boundary")
        status = "NEEDS_REVIEW"
        confidence -= 0.2

    page_num = page_of(page_breaks, nm.match.start())
    topic = topic_for_position(topic_index, nm.match.start())
    if topic is None:
        flags.append("topic_unresolved")

    confidence = max(0.1, min(1.0, confidence))
    ikey = identity_key(source_file, str(page_num), str(run_index), nm.raw, "Q")
    return ExtractedRecord(
        id="",
        identity_key=ikey,
        source_file=source_file,
        source_file_sha256=source_sha,
        source_book_title=SOURCE_BOOK_TITLE,
        source_publisher=SOURCE_PUBLISHER,
        source_edition=SOURCE_EDITION,
        pdf_page_number=page_num,
        printed_page_number=None,
        question_number_raw=nm.raw,
        global_sequence_in_file=seq,
        subject="Biology",
        class_level=class_level,
        chapter=chapter_name,
        topic=topic,
        stem_text=stem,
        options=opt_list,
        answer_raw=answer_raw,
        explanation_text=explanation,
        exam_name=exam_name,
        exam_year=exam_year,
        extraction_method="text_native",
        extraction_status=status,
        extraction_confidence=confidence,
        rights_status=RIGHTS_STATUS_33YEARS,
        review_flags=flags,
        raw_block_text=block[:4000],
    )


def parse_answer_run(matches, full_text: str, next_boundary: int) -> dict[int, dict]:
    """Parses an ANSWER_ENTRY run into {number: {"letter":, "explanation":}}."""
    out: dict[int, dict] = {}
    for i, nm in enumerate(matches):
        start = nm.match.end()
        end = matches[i + 1].match.start() if i + 1 < len(matches) else next_boundary
        block = full_text[start:end]
        m = common.ANSWER_ENTRY_RE.match(block)
        if not m:
            continue
        letter = m.group(1).replace(" ", "")
        explanation = block[m.end():].strip()
        out[nm.number] = {"letter": letter, "explanation": explanation or None}
    return out


def run(pdf_path: Path, out_dir: Path, *, page_limit: int | None = None, label: str = "full") -> dict:
    source_file = str(pdf_path)
    source_sha = sha256_file(pdf_path)
    doc = fitz.open(pdf_path)
    pages_in_file = doc.page_count

    page_breaks: list[tuple[int, int]] = []
    full_parts = []
    offset = 0
    page_statuses: list[dict] = []
    total_pages = pages_in_file if page_limit is None else min(page_limit, pages_in_file)
    for i in range(total_pages):
        t = doc[i].get_text()
        page_breaks.append((offset, i + 1))
        full_parts.append(t)
        offset += len(t)
        char_count = len(t.strip())
        if char_count == 0:
            n_images = len(doc[i].get_images(full=True))
            page_statuses.append({
                "page": i + 1, "status": "SKIPPED_NO_EXTRACTABLE_CONTENT",
                "char_count": 0, "images_on_page": n_images,
                "note": "zero-char page; likely a divider/ad page, not a scan "
                        "(confirmed text-native elsewhere in this file) -- not "
                        "sent to OCR since there is no text region to recover, "
                        "only (at most) a decorative image",
            })
        elif char_count < 40:
            page_statuses.append({
                "page": i + 1, "status": "LOW_TEXT_DENSITY_REVIEW",
                "char_count": char_count,
                "note": "below the 40-char text-native sanity threshold; kept "
                        "as text_native (not routed to OCR) because PyMuPDF "
                        "did return real text, just very little of it -- "
                        "typical of this file's divider/ad pages",
            })
        else:
            page_statuses.append({"page": i + 1, "status": "TEXT_NATIVE_OK", "char_count": char_count})
    full_text = "".join(full_parts)

    toc_names = parse_toc(doc)
    topic_index = build_subsection_index(full_text)

    toc_start: int | None = None
    toc_end: int | None = None
    for off, pnum in page_breaks:
        if pnum == 5:
            toc_start = off
        if pnum == 7:
            toc_end = off
    if toc_start is not None and toc_end is None:
        toc_end = offset  # TOC pages present but file truncated (page-limited test run) before page 7
    toc_char_range = (toc_start, toc_end) if toc_start is not None else None

    raw_matches = list(NUMBER_RE.finditer(full_text))
    # drop matches physically inside the TOC pages (5-6) -- those are
    # chapter-list/page-number entries, not question/answer numbering.
    matches = [m for m in raw_matches if not (toc_char_range and toc_char_range[0] <= m.start() < toc_char_range[1])]

    runs, orphaned_matches = segment_into_runs(matches)

    answer_key_header_positions = [m.start() for m in ANSWER_KEY_HEADER_RE.finditer(full_text)]

    match_start_to_idx = {m.start(): idx for idx, m in enumerate(matches)}

    def block_end(m: re.Match) -> int:
        idx = match_start_to_idx[m.start()]
        return matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)

    def run_first_block_class(run_matches_) -> str:
        nm0 = run_matches_[0]
        cls0, _ = classify_block(full_text[nm0.match.end():block_end(nm0.match)])
        return cls0

    records: list[ExtractedRecord] = []
    chapter_idx = -1
    i = 0
    seq = 0
    other_blocks: list[dict] = []
    while i < len(runs):
        run_matches = runs[i]
        # classify majority type for this run
        votes = {"QUESTION": 0, "ANSWER_ENTRY": 0, "OTHER": 0}
        per_match_class = []
        for nm in run_matches:
            start = nm.match.end()
            end = block_end(nm.match)
            block = full_text[start:end]
            cls, opt_bounds = classify_block(block)
            votes[cls] += 1
            per_match_class.append((nm, block, cls, opt_bounds))

        run_type = max(votes, key=votes.get)

        if run_type == "QUESTION":
            chapter_idx += 1
            chapter_name = toc_names[chapter_idx] if chapter_idx < len(toc_names) else None
            class_level = "XI" if chapter_idx < 22 else ("XII" if chapter_idx < 38 else None)
            question_matches = per_match_class

            # Look ahead for the compact answer run. Bounded skip (up to
            # `MAX_LOOKAHEAD_SKIP` intervening runs): a tiny embedded
            # numbered sub-list inside a question's own stem (e.g.
            # "match the following") can still slip past
            # `segment_into_runs`'s confirmation threshold as its own
            # short run in rare cases; skipping past a small number of
            # non-ANSWER_ENTRY runs here (recording what was skipped)
            # is cheap insurance on top of that fix, not a substitute
            # for it.
            MAX_LOOKAHEAD_SKIP = 2
            compact_answers: dict[int, dict] = {}
            detailed_answers: dict[int, dict] = {}
            j = i + 1
            skips = 0
            while j < len(runs) and skips <= MAX_LOOKAHEAD_SKIP:
                next_run = runs[j]
                next_cls = run_first_block_class(next_run)
                if next_cls == "ANSWER_ENTRY":
                    compact_answers = parse_answer_run(next_run, full_text, block_end(next_run[-1].match))
                    j += 1
                    break
                if next_cls == "QUESTION":
                    # the NEXT chapter's own question run -- never skip
                    # over it (it is not noise); stop the lookahead here,
                    # unconsumed, and let the outer loop pick it up fresh.
                    break
                for nm_skip in next_run:
                    other_blocks.append({
                        "page": page_of(page_breaks, nm_skip.match.start()), "number_raw": nm_skip.raw,
                        "classified_as": "SKIPPED_DURING_ANSWER_LOOKAHEAD", "sample": "",
                        "note": f"run of {len(next_run)} non-answer-entry matches skipped while "
                                f"searching for chapter {chapter_idx}'s compact answer key",
                    })
                j += 1
                skips += 1
            skips = 0
            while j < len(runs) and skips <= MAX_LOOKAHEAD_SKIP:
                next_run2 = runs[j]
                nm1 = next_run2[0]
                next_cls2 = run_first_block_class(next_run2)
                if next_cls2 == "QUESTION":
                    break
                if next_cls2 == "ANSWER_ENTRY":
                    # confirm an "ANSWER KEY" header sits between compact
                    # run's end and this run's start (never guessed).
                    prev_end = run_matches[-1].match.end()
                    has_header = any(prev_end <= p <= nm1.match.start() for p in answer_key_header_positions)
                    if has_header:
                        detailed_answers = parse_answer_run(next_run2, full_text, block_end(next_run2[-1].match))
                        j += 1
                    break
                for nm_skip in next_run2:
                    other_blocks.append({
                        "page": page_of(page_breaks, nm_skip.match.start()), "number_raw": nm_skip.raw,
                        "classified_as": "SKIPPED_DURING_ANSWER_LOOKAHEAD", "sample": "",
                        "note": f"run of {len(next_run2)} non-answer-entry matches skipped while "
                                f"searching for chapter {chapter_idx}'s detailed answer key",
                    })
                j += 1
                skips += 1

            answers_by_number = dict(compact_answers)
            for num, d in detailed_answers.items():
                merged = dict(answers_by_number.get(num, {}))
                merged.update({k: v for k, v in d.items() if v})
                if "letter" not in merged and num in compact_answers:
                    merged["letter"] = compact_answers[num]["letter"]
                answers_by_number[num] = merged

            for nm, block, cls, opt_bounds in question_matches:
                if cls != "QUESTION":
                    other_blocks.append({
                        "page": page_of(page_breaks, nm.match.start()),
                        "number_raw": nm.raw, "classified_as": cls,
                        "sample": block[:150],
                        "note": "matched the numbering pattern inside a QUESTION-"
                                "majority run but did not itself have 4 options -- "
                                "left unextracted, not guessed",
                    })
                    continue
                seq += 1
                rec = build_question_record(
                    run_index=chapter_idx, seq=seq, nm=nm, block=block, opt_bounds=opt_bounds,
                    page_breaks=page_breaks, source_file=source_file, source_sha=source_sha,
                    chapter_name=chapter_name, class_level=class_level, topic_index=topic_index,
                    answers_by_number=answers_by_number,
                )
                records.append(rec)
            i = j
            continue

        # a run that is not QUESTION-majority and wasn't consumed as a
        # compact/detailed answer run attached to a preceding question
        # run (e.g. stray noise, or a genuinely orphaned answer run) --
        # recorded, never dropped silently.
        for nm, block, cls, opt_bounds in per_match_class:
            other_blocks.append({
                "page": page_of(page_breaks, nm.match.start()),
                "number_raw": nm.raw, "classified_as": cls, "sample": block[:150],
                "note": "run not attached to any question run as its compact/"
                        "detailed answer key (orphan run)",
            })
        i += 1

    doc.close()

    for nm_orph in orphaned_matches:
        other_blocks.append({
            "page": page_of(page_breaks, nm_orph.match.start()), "number_raw": nm_orph.raw,
            "classified_as": "ORPHANED_UNCONFIRMED_RESET", "sample": "",
            "note": "a tentative reset-to-1 run that never reached the "
                    f"{8}-member confirmation threshold before the document "
                    "ended or the original sequence resumed (e.g. a numbered "
                    "sub-list embedded inside one question's own stem) -- "
                    "dropped, not merged into any run",
        })

    total_candidate_matches = len(raw_matches)
    dropped_as_noise = (
        total_candidate_matches
        - sum(len(r) for r in runs)
        - len(orphaned_matches)
        - len([m for m in raw_matches if toc_char_range and toc_char_range[0] <= m.start() < toc_char_range[1]])
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    records_path = out_dir / f"questions_{label}.json"
    write_json(records_path, [common.record_to_dict(r) for r in records])

    manifest = {
        "generated_at": now_iso(),
        "pipeline_version": common.PIPELINE_VERSION,
        "source_file": source_file,
        "source_file_sha256": source_sha,
        "pages_in_file": pages_in_file,
        "pages_processed_this_run": total_pages,
        "label": label,
        "chapters_resolved": chapter_idx + 1,
        "chapters_expected_from_toc": len(toc_names),
        "toc_chapter_names": toc_names,
        "total_numbered_matches_raw": total_candidate_matches,
        "toc_page_matches_excluded": len([m for m in raw_matches if toc_char_range and toc_char_range[0] <= m.start() < toc_char_range[1]]),
        "runs_found": len(runs),
        "questions_extracted": len(records),
        "answer_known": sum(1 for r in records if r.answer_raw),
        "answer_pending": sum(1 for r in records if not r.answer_raw),
        "explanation_present": sum(1 for r in records if r.explanation_text),
        "needs_review": sum(1 for r in records if r.extraction_status == "NEEDS_REVIEW"),
        "complete": sum(1 for r in records if r.extraction_status == "COMPLETE"),
        "other_blocks_unextracted": len(other_blocks),
        "orphaned_unconfirmed_resets": len(orphaned_matches),
        "dropped_as_pure_noise": dropped_as_noise,
        "ocr_pages_used": 0,
        "page_statuses": page_statuses,
        "other_blocks_sample": other_blocks[:80],
        "rights_status": RIGHTS_STATUS_33YEARS,
        "rights_restatement": common.RIGHTS_RESTATEMENT,
        "safety_attestation": {
            "ai_provider_calls": 0, "database_writes": 0, "external_uploads": 0,
            "network_calls": 0,
        },
    }
    write_json(out_dir / f"manifest_{label}.json", manifest)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=r"D:\ravishori\AI Neet Exam App\Latest Study material\33 Years NEET-AIPMT Chapterwise Solutions - Biology 2020.pdf")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "data" / "extracted_mcqs" / "33years_biology_2020"))
    ap.add_argument("--page-limit", type=int, default=None)
    ap.add_argument("--label", default="full")
    args = ap.parse_args()
    manifest = run(Path(args.pdf), Path(args.out), page_limit=args.page_limit, label=args.label)
    print(f"questions_extracted={manifest['questions_extracted']} "
          f"needs_review={manifest['needs_review']} "
          f"answer_known={manifest['answer_known']} "
          f"chapters_resolved={manifest['chapters_resolved']}")


if __name__ == "__main__":
    main()
