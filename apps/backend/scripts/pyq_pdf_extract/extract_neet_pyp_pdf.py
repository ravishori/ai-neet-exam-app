"""Deterministic extractor for "neet_pyp.pdf" ("NEET 2025 Chapterwise
Index" / running header "NEET Solved Paper - 2025"), confirmed by direct
inspection (2026-10-18):

  - 34 PDF pages, text-native (PyMuPDF `page.get_text()` returns real
    content on every content page). AES-256 (Standard V5 R6) encrypted
    at the PDF-container level, but with NO *open* password, so PyMuPDF
    reads it transparently -- this is a publisher copy-protection flag,
    not evidence reuse was authorized (see `common.py`'s module
    docstring for the mandatory rights_status statement).
  - Page 1: a three-subject (Physics/Chemistry/Biology) chapterwise
    index -- "Unit Name" / "Question No." (comma-separated list,
    sometimes wrapped across lines) / "Total" -- covering question
    numbers 1-180 with zero overlap and zero gaps (verified: every one
    of the 180 question numbers appears in exactly one unit's list, and
    every unit's listed-count matches its own printed Total). This is
    used as the authoritative subject+topic source for every question,
    in preference to guessing a subject from a hardcoded 1-45/46-90/
    91-180 range split.
  - PDF pages 2-17 (with two blank/divider pages, 6 and 18, each a
    single decorative image and no text): the 180 questions themselves,
    globally numbered 1-180 across all three subjects with NO reset --
    "<n>.\\t\\n<stem...>\\n(a)\\t...(d)\\t...".
  - PDF pages 19-25ish: a compact "quick answer" run, SAME 1..180
    numbering restarting from 1: "<n>.\\t\\n(<letter>)" with no
    explanation.
  - A single literal "ANSWER KEY" header (found exactly once), followed
    by the detailed run, SAME 1..180 numbering restarting a third time:
    "<n>.\\t(<letter>)\\t:\\t<explanation...>".
  - This is a single NEET (UG) 2025 paper -- exam_name/exam_year are
    constant for every record, not parsed per-question (unlike the
    33-years book, which spans many different exam sittings).

Reuses `common.py`'s shared option/answer-entry classification and
run-segmentation primitives (same QUESTION -> compact-ANSWER ->
"ANSWER KEY"-marked detailed-ANSWER triple-run shape as the 33-years
book, just with exactly one "chapter" covering the whole paper instead
of 38). No AI/LLM calls. No database writes. No network calls.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import fitz  # PyMuPDF

from scripts.pyq_pdf_extract import common
from scripts.pyq_pdf_extract.common import (
    ExtractedRecord,
    RIGHTS_STATUS_NEET_PYP,
    classify_block,
    identity_key,
    now_iso,
    option_integrity_flags,
    options_list,
    segment_into_runs,
    sha256_file,
    write_json,
)

SOURCE_BOOK_TITLE = "NEET 2025 Chapterwise Index (NEET Solved Paper - 2025)"
SOURCE_PUBLISHER = None  # not stated anywhere in the PDF's own text/metadata -- left null, not guessed
SOURCE_EDITION = None
EXAM_NAME = "NEET (UG) 2025"
EXAM_YEAR = 2025

NUMBER_RE = re.compile(r"(?m)^(\d{1,3})\.[\t ]+")
ANSWER_KEY_HEADER_RE = re.compile(r"\bANSWER KEY\b")
# Running page header/footer boilerplate that can leak onto the end of a
# question's last-option text at a page boundary (confirmed by direct
# inspection, e.g. a printed page number + "NEET Solved Paper - 2025" or
# a bare "PHYSICS"/"CHEMISTRY"/"BIOLOGY" subject-section divider word
# sitting between this question's options and the next numbered match).
BOILERPLATE_LEAK_RE = re.compile(
    r"\n(?:\d{1,2}\n\s*NEET (?:Solved Paper|2025)|NEET Solved Paper - 2025|PHYSICS\n|CHEMISTRY\n|BIOLOGY\n)"
)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

SKIP_EXACT = {"Unit Name", "Question No.", "Total", "NEET 2025", "CHAPTERWISE INDEX",
              "Physics", "Chemistry", "Biology", ""}
SUBJECT_HEADERS = {"PHYSICS", "CHEMISTRY", "BIOLOGY"}
INDEX_NUM_RE = re.compile(r"^[\d,\s]+$")


def _strip_control_chars(text: str) -> tuple[str, bool]:
    if not text:
        return text, False
    cleaned = _CONTROL_CHAR_RE.sub("", text)
    return cleaned, cleaned != text


def _trim_trailing_boilerplate(text: str) -> str:
    m = BOILERPLATE_LEAK_RE.search(text)
    return text[: m.start()] if m else text


def parse_chapterwise_index(doc: fitz.Document) -> tuple[dict[int, tuple[str, str]], list[dict]]:
    """Parses page 1's three subject tables into {question_number:
    (subject, unit_name)}. Returns (mapping, per_unit_entries_for_
    manifest). Validated by direct inspection: every unit's own listed
    count matches its printed Total, and the 180 recovered numbers are
    gap-free and overlap-free across all three subjects -- any future
    mismatch (e.g. if this logic is reused on a different edition of
    the PDF) is surfaced via the returned entries' own `ok` flag rather
    than asserted away."""
    lines = [l.strip() for l in doc[0].get_text().split("\n")]
    current_subject: str | None = None
    name_buf: list[str] = []
    numbers_buf: list[str] = []
    mode: str | None = None
    entries: list[dict] = []

    def commit() -> None:
        nonlocal name_buf, numbers_buf
        if not name_buf or not numbers_buf:
            name_buf, numbers_buf = [], []
            return
        unit_name = re.sub(r"\s+", " ", " ".join(name_buf)).strip()
        total_line = numbers_buf[-1]
        nums_text = " ".join(numbers_buf[:-1])
        nums = [] if (total_line == "–" or not nums_text.strip() or nums_text.strip() == "–") else [
            int(x) for x in re.findall(r"\d+", nums_text)
        ]
        total_val = 0 if total_line == "–" else int(total_line)
        entries.append({
            "subject": current_subject, "unit": unit_name, "numbers": nums,
            "total": total_val, "ok": len(nums) == total_val,
        })
        name_buf, numbers_buf = [], []

    for line in lines:
        if line in SKIP_EXACT:
            continue
        if line.startswith("Use the index") or "questions when you are practising" in line:
            continue
        if line in SUBJECT_HEADERS:
            commit()
            current_subject = line.capitalize()
            mode = None
            continue
        if INDEX_NUM_RE.fullmatch(line) or line == "–":
            numbers_buf.append(line)
            mode = "NUMBERS"
        else:
            if mode == "NUMBERS":
                commit()
            name_buf.append(line)
            mode = "NAME"
    commit()

    mapping: dict[int, tuple[str, str]] = {}
    for e in entries:
        for n in e["numbers"]:
            mapping[n] = (e["subject"], e["unit"])
    return mapping, entries


def page_of(page_breaks: list[tuple[int, int]], pos: int) -> int:
    pg = 1
    for offset, pnum in page_breaks:
        if offset <= pos:
            pg = pnum
        else:
            break
    return pg


def parse_answer_run(matches, full_text: str, block_end_fn) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for i, nm in enumerate(matches):
        start = nm.match.end()
        end = block_end_fn(nm.match)
        block = full_text[start:end]
        m = common.ANSWER_ENTRY_RE.match(block)
        if not m:
            continue
        letter = m.group(1).replace(" ", "")
        explanation = block[m.end():].strip()
        out[nm.number] = {"letter": letter, "explanation": explanation or None}
    return out


def build_question_record(
    *, seq: int, nm, block: str, opt_bounds, page_breaks, source_file: str, source_sha: str,
    index_map: dict[int, tuple[str, str]], answers_by_number: dict[int, dict],
) -> ExtractedRecord:
    flags: list[str] = []
    status = "COMPLETE"
    confidence = 0.9

    stem, stem_ctrl = _strip_control_chars(block[: opt_bounds[0].start()].strip())
    any_ctrl = stem_ctrl

    opts: dict[str, str] = {}
    for j in range(4):
        ostart = opt_bounds[j].end()
        oend = opt_bounds[j + 1].start() if j + 1 < len(opt_bounds) else len(block)
        text = _trim_trailing_boilerplate(block[ostart:oend])
        text, ctrl = _strip_control_chars(text)
        any_ctrl = any_ctrl or ctrl
        opts[chr(ord("a") + j)] = text.strip()
    if any_ctrl:
        flags.append("control_char_removed")

    opt_list = options_list(opts)
    flags.extend(option_integrity_flags(opt_list))
    if any(f.startswith("option_") for f in flags):
        status = "NEEDS_REVIEW"
        confidence -= 0.2

    ans = answers_by_number.get(nm.number)
    answer_raw = ans["letter"] if ans else None
    explanation = ans.get("explanation") if ans else None
    if explanation:
        explanation, ectrl = _strip_control_chars(explanation)
        if ectrl and "control_char_removed" not in flags:
            flags.append("control_char_removed")
    if not answer_raw:
        flags.append("missing_answer")
        status = "NEEDS_REVIEW"
        confidence -= 0.3
    if not explanation:
        flags.append("missing_explanation")
        confidence -= 0.05 if answer_raw else 0

    if len(stem) < 5:
        flags.append("uncertain_question_boundary")
        status = "NEEDS_REVIEW"
        confidence -= 0.2

    subj_topic = index_map.get(nm.number)
    subject = subj_topic[0] if subj_topic else None
    topic = subj_topic[1] if subj_topic else None
    if subj_topic is None:
        flags.append("subject_unresolved_from_index")
        confidence -= 0.05

    page_num = page_of(page_breaks, nm.match.start())
    confidence = max(0.1, min(1.0, confidence))
    ikey = identity_key(source_file, str(page_num), nm.raw, "Q")
    return ExtractedRecord(
        id="", identity_key=ikey, source_file=source_file, source_file_sha256=source_sha,
        source_book_title=SOURCE_BOOK_TITLE, source_publisher=SOURCE_PUBLISHER, source_edition=SOURCE_EDITION,
        pdf_page_number=page_num, printed_page_number=None, question_number_raw=nm.raw,
        global_sequence_in_file=seq, subject=subject, class_level=None, chapter=None, topic=topic,
        stem_text=stem, options=opt_list, answer_raw=answer_raw, explanation_text=explanation,
        exam_name=EXAM_NAME, exam_year=EXAM_YEAR, extraction_method="text_native",
        extraction_status=status, extraction_confidence=confidence, rights_status=RIGHTS_STATUS_NEET_PYP,
        review_flags=flags, raw_block_text=block[:4000],
    )


def run(pdf_path: Path, out_dir: Path, *, page_limit: int | None = None, label: str = "full") -> dict:
    source_file = str(pdf_path)
    source_sha = sha256_file(pdf_path)
    doc = fitz.open(pdf_path)
    pages_in_file = doc.page_count
    total_pages = pages_in_file if page_limit is None else min(page_limit, pages_in_file)

    index_map, index_entries = parse_chapterwise_index(doc)

    page_breaks: list[tuple[int, int]] = []
    full_parts = []
    offset = 0
    page_statuses: list[dict] = []
    for i in range(total_pages):
        # page 1 (the chapterwise index) is parsed separately via plain
        # line order above (it is not 2-column); every other page uses
        # the column-aware reconstruction since the question pages are
        # confirmed 2-column (see common.extract_page_text_column_aware).
        t = doc[i].get_text() if i == 0 else common.extract_page_text_column_aware(doc[i])
        page_breaks.append((offset, i + 1))
        full_parts.append(t)
        offset += len(t)
        char_count = len(t.strip())
        if i == 0:
            page_statuses.append({"page": 1, "status": "CHAPTERWISE_INDEX_PAGE_NOT_QUESTIONS", "char_count": char_count})
        elif char_count == 0:
            n_images = len(doc[i].get_images(full=True))
            page_statuses.append({
                "page": i + 1, "status": "SKIPPED_NO_EXTRACTABLE_CONTENT", "char_count": 0,
                "images_on_page": n_images,
                "note": "zero-char page; confirmed decorative divider (single embedded "
                        "image, e.g. a subject-divider graphic between Physics/Chemistry "
                        "and Chemistry/Biology) -- not a scan of missing question content "
                        "(the file is text-native elsewhere), so NOT routed to OCR",
            })
        else:
            page_statuses.append({"page": i + 1, "status": "TEXT_NATIVE_OK", "char_count": char_count})
    full_text = "".join(full_parts)

    # page-1 text is index content, not question numbering -- excluded
    # from the numbered-match search entirely.
    page1_end = page_breaks[1][0] if len(page_breaks) > 1 else len(full_text)
    raw_matches = list(NUMBER_RE.finditer(full_text))
    matches = [m for m in raw_matches if m.start() >= page1_end]

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
    other_blocks: list[dict] = []
    question_runs_found = 0
    seq = 0
    i = 0
    while i < len(runs):
        run_matches = runs[i]
        votes = {"QUESTION": 0, "ANSWER_ENTRY": 0, "OTHER": 0}
        per_match_class = []
        for nm in run_matches:
            block = full_text[nm.match.end():block_end(nm.match)]
            cls, opt_bounds = classify_block(block)
            votes[cls] += 1
            per_match_class.append((nm, block, cls, opt_bounds))
        run_type = max(votes, key=votes.get)

        if run_type == "QUESTION":
            question_runs_found += 1
            MAX_LOOKAHEAD_SKIP = 2
            compact_answers: dict[int, dict] = {}
            detailed_answers: dict[int, dict] = {}
            j = i + 1
            skips = 0
            while j < len(runs) and skips <= MAX_LOOKAHEAD_SKIP:
                next_cls = run_first_block_class(runs[j])
                if next_cls == "ANSWER_ENTRY":
                    compact_answers = parse_answer_run(runs[j], full_text, block_end)
                    j += 1
                    break
                if next_cls == "QUESTION":
                    break
                for nm_skip in runs[j]:
                    other_blocks.append({
                        "page": page_of(page_breaks, nm_skip.match.start()), "number_raw": nm_skip.raw,
                        "classified_as": "SKIPPED_DURING_ANSWER_LOOKAHEAD", "sample": "",
                        "note": f"run of {len(runs[j])} non-answer-entry matches skipped while "
                                "searching for the compact answer key",
                    })
                j += 1
                skips += 1
            skips = 0
            while j < len(runs) and skips <= MAX_LOOKAHEAD_SKIP:
                next_run2 = runs[j]
                next_cls2 = run_first_block_class(next_run2)
                if next_cls2 == "QUESTION":
                    break
                if next_cls2 == "ANSWER_ENTRY":
                    prev_end = run_matches[-1].match.end()
                    nm1_start = next_run2[0].match.start()
                    has_header = any(prev_end <= p <= nm1_start for p in answer_key_header_positions)
                    if has_header:
                        detailed_answers = parse_answer_run(next_run2, full_text, block_end)
                        j += 1
                    break
                for nm_skip in next_run2:
                    other_blocks.append({
                        "page": page_of(page_breaks, nm_skip.match.start()), "number_raw": nm_skip.raw,
                        "classified_as": "SKIPPED_DURING_ANSWER_LOOKAHEAD", "sample": "",
                        "note": f"run of {len(next_run2)} non-answer-entry matches skipped while "
                                "searching for the detailed answer key",
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

            for nm, block, cls, opt_bounds in per_match_class:
                if cls != "QUESTION":
                    other_blocks.append({
                        "page": page_of(page_breaks, nm.match.start()), "number_raw": nm.raw,
                        "classified_as": cls, "sample": block[:150],
                        "note": "matched numbering inside a QUESTION-majority run but lacked "
                                "4 options -- left unextracted, not guessed",
                    })
                    continue
                seq += 1
                rec = build_question_record(
                    seq=seq, nm=nm, block=block, opt_bounds=opt_bounds, page_breaks=page_breaks,
                    source_file=source_file, source_sha=source_sha, index_map=index_map,
                    answers_by_number=answers_by_number,
                )
                records.append(rec)
            i = j
            continue

        for nm, block, cls, opt_bounds in per_match_class:
            other_blocks.append({
                "page": page_of(page_breaks, nm.match.start()), "number_raw": nm.raw,
                "classified_as": cls, "sample": block[:150],
                "note": "orphan run (not attached to a preceding question run as its "
                        "compact/detailed answer key)",
            })
        i += 1

    doc.close()

    for nm_orph in orphaned_matches:
        other_blocks.append({
            "page": page_of(page_breaks, nm_orph.match.start()), "number_raw": nm_orph.raw,
            "classified_as": "ORPHANED_UNCONFIRMED_RESET", "sample": "",
            "note": "a tentative reset-to-1 run that never reached the confirmation "
                    "threshold (e.g. a numbered sub-list embedded inside one "
                    "question's own stem) -- dropped, not merged into any run",
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / f"questions_{label}.json", [common.record_to_dict(r) for r in records])

    manifest = {
        "generated_at": now_iso(),
        "pipeline_version": common.PIPELINE_VERSION,
        "source_file": source_file,
        "source_file_sha256": source_sha,
        "pages_in_file": pages_in_file,
        "pages_processed_this_run": total_pages,
        "label": label,
        "question_runs_found": question_runs_found,
        "chapterwise_index_entries": index_entries,
        "chapterwise_index_total_units": len(index_entries),
        "chapterwise_index_question_numbers_mapped": len(index_map),
        "chapterwise_index_internal_mismatches": sum(1 for e in index_entries if not e["ok"]),
        "total_numbered_matches_raw": len(raw_matches),
        "page1_index_matches_excluded": len(raw_matches) - len(matches),
        "runs_found": len(runs),
        "orphaned_unconfirmed_resets": len(orphaned_matches),
        "questions_extracted": len(records),
        "answer_known": sum(1 for r in records if r.answer_raw),
        "answer_pending": sum(1 for r in records if not r.answer_raw),
        "explanation_present": sum(1 for r in records if r.explanation_text),
        "needs_review": sum(1 for r in records if r.extraction_status == "NEEDS_REVIEW"),
        "complete": sum(1 for r in records if r.extraction_status == "COMPLETE"),
        "other_blocks_unextracted": len(other_blocks),
        "ocr_pages_used": 0,
        "page_statuses": page_statuses,
        "other_blocks_sample": other_blocks[:50],
        "rights_status": RIGHTS_STATUS_NEET_PYP,
        "rights_restatement": common.RIGHTS_RESTATEMENT,
        "safety_attestation": {"ai_provider_calls": 0, "database_writes": 0, "external_uploads": 0, "network_calls": 0},
    }
    write_json(out_dir / f"manifest_{label}.json", manifest)
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=r"D:\ravishori\AI Neet Exam App\Latest Study material\neet_pyp.pdf")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "data" / "extracted_mcqs" / "neet_pyp_2025"))
    ap.add_argument("--page-limit", type=int, default=None)
    ap.add_argument("--label", default="full")
    args = ap.parse_args()
    manifest = run(Path(args.pdf), Path(args.out), page_limit=args.page_limit, label=args.label)
    print(f"questions_extracted={manifest['questions_extracted']} "
          f"needs_review={manifest['needs_review']} "
          f"answer_known={manifest['answer_known']} "
          f"index_mismatches={manifest['chapterwise_index_internal_mismatches']}")


if __name__ == "__main__":
    main()
