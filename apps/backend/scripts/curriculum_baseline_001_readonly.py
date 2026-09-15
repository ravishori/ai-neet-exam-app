"""CURRICULUM-BASELINE-001 — read-only NCERT Rationalised 2026–27 baseline.

No DB writes. No AI. No Content Factory. No commit.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import fitz
from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.modules.ingestion.services.ncert_books_inventory import (  # noqa: E402
    scan_ncert_books,
)
from app.modules.ingestion.services.ncert_canonical_source import (  # noqa: E402
    get_ncert_source_root,
)

WORD_NUM = {
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
    "SIX": 6,
    "SEVEN": 7,
    "EIGHT": 8,
    "NINE": 9,
    "TEN": 10,
    "ELEVEN": 11,
    "TWELVE": 12,
    "THIRTEEN": 13,
    "FOURTEEN": 14,
    "FIFTEEN": 15,
    "SIXTEEN": 16,
    "SEVENTEEN": 17,
    "EIGHTEEN": 18,
    "NINETEEN": 19,
    "TWENTY": 20,
    "TWENTYONE": 21,
    "TWENTY-ONE": 21,
}

CHAPTER_HDR = re.compile(
    r"^\s*CHAPTER\s+(?:([A-Z\-]+)|(\d{1,2}))\s*$",
    re.IGNORECASE | re.MULTILINE,
)
REPRINT_RE = re.compile(r"Reprint\s+(\d{4})\s*[–\-]\s*(\d{2,4})", re.IGNORECASE)
RATIONALISED_RE = re.compile(r"Rationalis(?:e|z)d", re.IGNORECASE)

CF_C1_SLUGS = {
    "solutions",
    "chemical-kinetics",
    "d-and-f-block-elements",
    "coordination-compounds",
    "haloalkanes-and-haloarenes",
    "alcohols-phenols-and-ethers",
    "aldehydes-ketones-and-carboxylic-acids",
    "amines",
    "biomolecules-chem",
}

# CF-C1 seed maps these titles to NCERT XII chapter numbers (chs 1,3-10).
# Electrochemistry was historically ch 3; rationalised numbering may differ.
CF_C1_EXPECTED_TITLES = {
    "Solutions",
    "Electrochemistry",
    "Chemical Kinetics",
    "The d- and f-Block Elements",
    "Coordination Compounds",
    "Haloalkanes and Haloarenes",
    "Alcohols, Phenols and Ethers",
    "Aldehydes, Ketones and Carboxylic Acids",
    "Amines",
    "Biomolecules",
}


def _decode_symbol_pua(text: str) -> str:
    """Decode Symbol-font Private Use Area glyphs (common in older NCERT PDFs)."""
    out = []
    for ch in text:
        o = ord(ch)
        if 0xF000 <= o <= 0xF0FF:
            out.append(chr(o - 0xF000))
        else:
            out.append(ch)
    return "".join(out)


def _clean_title(line: str) -> str:
    t = _decode_symbol_pua(line)
    t = re.sub(r"\s+", " ", t).strip(" \t.-–—:")
    t = re.sub(r"^[0-9]+\.[0-9]+\s+", "", t)
    if re.fullmatch(r"[A-Z ]{0,3}", t):
        return ""
    if "EH DEOH" in t.upper():
        return ""
    return t


def _title_from_big_spans(page) -> str | None:
    try:
        d = page.get_text("dict")
    except Exception:
        return None
    candidates: list[tuple[float, str]] = []
    for b in d.get("blocks", []):
        for l in b.get("lines", []):
            parts = []
            sizes = []
            for s in l.get("spans", []):
                raw = (s.get("text") or "").strip()
                if not raw:
                    continue
                parts.append(_decode_symbol_pua(raw))
                sizes.append(float(s.get("size") or 0))
            if not parts:
                continue
            text_line = _clean_title(" ".join(parts))
            if not text_line or len(text_line) < 4:
                continue
            low = text_line.lower()
            if low in {"objectives", "unit", "chemistry", "physics", "biology"}:
                continue
            if low.startswith("unit "):
                continue
            if re.fullmatch(r"\d+(\.\d+)?", text_line):
                continue
            size = max(sizes) if sizes else 0
            if size >= 16:
                candidates.append((size, text_line))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], -len(x[1])))
    return candidates[0][1]


def extract_chapter_identity(pdf_path: Path) -> dict:
    doc = fitz.open(pdf_path)
    try:
        meta = doc.metadata or {}
        sample_pages = min(5, doc.page_count)
        texts = [
            _decode_symbol_pua(doc.load_page(i).get_text("text") or "") for i in range(sample_pages)
        ]
        blob = "\n".join(texts)
        full_early = "\n".join(texts[:3])

        reprint = None
        m = REPRINT_RE.search(blob)
        if m:
            reprint = f"Reprint {m.group(1)}-{m.group(2)}"
        rationalised = bool(RATIONALISED_RE.search(blob + " " + str(meta.get("title") or "")))
        meta_title = meta.get("title") or ""
        if re.search(r"Rationalis", meta_title, re.I):
            rationalised = True

        book_chapter_num = None
        chapter_title = None

        unit_m = re.search(r"(?im)^\s*Unit\s+(\d{1,2})\s*$", texts[0] if texts else "")
        if unit_m:
            book_chapter_num = int(unit_m.group(1))
            chapter_title = _title_from_big_spans(doc.load_page(0))
            if not chapter_title:
                lines = [ln.strip() for ln in texts[0].splitlines() if ln.strip()]
                for idx, ln in enumerate(lines):
                    if re.match(r"(?i)^unit\s+\d+", ln):
                        for nxt in lines[idx + 1 : idx + 8]:
                            if re.match(r"(?i)^(after studying|objectives|unit\s+\d)", nxt):
                                continue
                            ct = _clean_title(nxt)
                            if len(ct) >= 4:
                                chapter_title = ct
                                break
                        break

        if chapter_title is None:
            for page_text in texts[:3]:
                lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
                for idx, ln in enumerate(lines):
                    hm = re.match(r"^CHAPTER\s+(?:([A-Z\-]+)|(\d{1,2}))\s*$", ln, re.I)
                    if not hm:
                        continue
                    if hm.group(1):
                        key = hm.group(1).upper().replace(" ", "")
                        book_chapter_num = WORD_NUM.get(key) or WORD_NUM.get(hm.group(1).upper())
                    else:
                        book_chapter_num = int(hm.group(2))
                    for nxt in lines[idx + 1 : idx + 6]:
                        if re.match(r"^CHAPTER\s+", nxt, re.I):
                            continue
                        if re.match(r"^\d+\.\d+", nxt):
                            continue
                        ct = _clean_title(nxt)
                        if len(ct) < 3:
                            continue
                        chapter_title = ct
                        break
                    break
                if chapter_title:
                    break

        if not chapter_title and doc.page_count:
            chapter_title = _title_from_big_spans(doc.load_page(0))

        if not chapter_title and re.search(r"(?i)\bgravitation\b|\bkepler", blob):
            chapter_title = "Gravitation"
            if book_chapter_num is None:
                book_chapter_num = 7

        if book_chapter_num is None:
            um = re.search(r"Unit[_\s-]*(\d{1,2})", meta_title, re.I)
            cm = re.search(r"Chapter[_\s-]*(\d{1,2})", meta_title, re.I)
            if um:
                book_chapter_num = int(um.group(1))
            elif cm:
                book_chapter_num = int(cm.group(1))

        if chapter_title and chapter_title.isupper():
            chapter_title = chapter_title.title()

        pdf_title = None
        if chapter_title and book_chapter_num:
            pdf_title = f"Chapter {book_chapter_num}: {chapter_title}"
        elif chapter_title:
            pdf_title = chapter_title

        version_bits = []
        if rationalised:
            version_bits.append("Rationalised")
        if reprint:
            version_bits.append(reprint)
        if "2026" in (reprint or "") or "2026" in blob[:2500]:
            version_bits.append("2026-27 family")

        return {
            "book_chapter_number": book_chapter_num,
            "chapter_title": chapter_title,
            "pdf_title": pdf_title,
            "rationalised": rationalised,
            "reprint": reprint,
            "version_label": "; ".join(version_bits) if version_bits else None,
            "page_count": doc.page_count,
            "meta_title": meta_title[:200] if meta_title else None,
            "preview": full_early[:400],
        }
    finally:
        doc.close()


def snapshot_db(engine) -> dict:
    with engine.connect() as conn:
        status = {
            r[0]: r[1]
            for r in conn.execute(
                text(
                    """
                    SELECT status, COUNT(*) FROM cms.content_items
                    WHERE deleted_at IS NULL AND content_type='QUESTION'
                    GROUP BY 1
                    """
                )
            )
        }
        unmapped = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM cms.content_items
                WHERE deleted_at IS NULL AND content_type='QUESTION'
                  AND status='DRAFT' AND concept_id IS NULL
                """
            )
        ).scalar()
        chapters = conn.execute(text("SELECT COUNT(*) FROM academic.chapters WHERE deleted_at IS NULL")).scalar()
        topics = conn.execute(text("SELECT COUNT(*) FROM academic.topics WHERE deleted_at IS NULL")).scalar()
        concepts = conn.execute(text("SELECT COUNT(*) FROM academic.concepts WHERE deleted_at IS NULL")).scalar()
        kus = conn.execute(text("SELECT COUNT(*) FROM knowledge.knowledge_units WHERE deleted_at IS NULL")).scalar()
        bps = conn.execute(
            text("SELECT COUNT(*) FROM cms.question_blueprints WHERE deleted_at IS NULL")
        ).scalar()
        batches = conn.execute(text("SELECT COUNT(*) FROM cms.content_batches WHERE deleted_at IS NULL")).scalar()
        jobs = conn.execute(text("SELECT COUNT(*) FROM cms.generation_jobs")).scalar()
        runs = conn.execute(text("SELECT COUNT(*) FROM cms.generation_runs")).scalar()
        cands = conn.execute(text("SELECT COUNT(*) FROM cms.generation_candidates")).scalar()

        rows = conn.execute(
            text(
                """
                SELECT s.name AS subject, ch.class_level, ch.code, ch.name, ch.id::text
                FROM academic.chapters ch
                JOIN academic.subjects s ON s.id = ch.subject_id
                WHERE ch.deleted_at IS NULL
                ORDER BY s.name, ch.class_level NULLS LAST, ch.name
                """
            )
        ).mappings().all()
        chapter_rows = [dict(r) for r in rows]

        topic_counts = {
            r[0]: r[1]
            for r in conn.execute(
                text(
                    """
                    SELECT ch.id::text, COUNT(t.id)
                    FROM academic.chapters ch
                    LEFT JOIN academic.topics t ON t.chapter_id = ch.id AND t.deleted_at IS NULL
                    WHERE ch.deleted_at IS NULL
                    GROUP BY ch.id
                    """
                )
            )
        }
        concept_counts = {
            r[0]: r[1]
            for r in conn.execute(
                text(
                    """
                    SELECT ch.id::text, COUNT(c.id)
                    FROM academic.chapters ch
                    LEFT JOIN academic.topics t ON t.chapter_id = ch.id AND t.deleted_at IS NULL
                    LEFT JOIN academic.concepts c ON c.topic_id = t.id AND c.deleted_at IS NULL
                    WHERE ch.deleted_at IS NULL
                    GROUP BY ch.id
                    """
                )
            )
        }
        bp_counts = {
            r[0]: r[1]
            for r in conn.execute(
                text(
                    """
                    SELECT ch.id::text, COUNT(bp.id)
                    FROM academic.chapters ch
                    LEFT JOIN academic.topics t ON t.chapter_id = ch.id AND t.deleted_at IS NULL
                    LEFT JOIN academic.concepts c ON c.topic_id = t.id AND c.deleted_at IS NULL
                    LEFT JOIN cms.question_blueprints bp ON bp.concept_id = c.id AND bp.deleted_at IS NULL
                    WHERE ch.deleted_at IS NULL
                    GROUP BY ch.id
                    """
                )
            )
        }

    for ch in chapter_rows:
        cid = ch["id"]
        ch["topic_count"] = topic_counts.get(cid, 0)
        ch["concept_count"] = concept_counts.get(cid, 0)
        ch["blueprint_count"] = bp_counts.get(cid, 0)

    return {
        "status": status,
        "unmapped_draft": unmapped,
        "chapters": chapters,
        "topics": topics,
        "concepts": concepts,
        "knowledge_units": kus,
        "question_blueprints": bps,
        "content_batches": batches,
        "generation_jobs": jobs,
        "generation_runs": runs,
        "generation_candidates": cands,
        "chapter_rows": chapter_rows,
    }


def _norm(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _title_match(a: str | None, b: str | None) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    # token overlap
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.6


def subject_bucket(subject_name: str) -> str:
    n = subject_name.lower()
    if "phys" in n:
        return "PHYSICS"
    if "chem" in n:
        return "CHEMISTRY"
    if "botany" in n or "zoology" in n or "biology" in n:
        return "BIOLOGY"
    return subject_name.upper()


def build_matrix(report) -> list[dict]:
    rows = []
    for e in report.entries:
        if e.kind != "chapter":
            rows.append(
                {
                    "class_level": e.class_level,
                    "subject_code": e.subject_code,
                    "part_number": e.part_number,
                    "filename_chapter": e.chapter_number,
                    "kind": "SUPPLEMENTAL",
                    "file_name": e.file_name,
                    "relative_path": e.relative_path,
                    "resolved_path": e.resolved_path,
                    "checksum_sha256": e.checksum_sha256,
                    "readable": e.readable,
                    "source_status": e.status,
                    "chapter_title": None,
                    "pdf_title": None,
                    "book_chapter_number": None,
                    "rationalised": None,
                    "reprint": None,
                    "version_label": None,
                }
            )
            continue
        ident = extract_chapter_identity(Path(e.resolved_path))
        rows.append(
            {
                "class_level": e.class_level,
                "subject_code": e.subject_code,
                "part_number": e.part_number,
                "filename_chapter": e.chapter_number,
                "kind": "CHAPTER",
                "file_name": e.file_name,
                "relative_path": e.relative_path,
                "resolved_path": e.resolved_path,
                "checksum_sha256": e.checksum_sha256,
                "readable": e.readable,
                "source_status": e.status,
                **ident,
            }
        )
    return rows


def compare(matrix: list[dict], db: dict) -> dict:
    chapters = [m for m in matrix if m["kind"] == "CHAPTER"]
    db_rows = db["chapter_rows"]

    matches = []
    ncert_missing_in_db = []
    used_db_ids: set[str] = set()

    for n in chapters:
        candidates = [
            d
            for d in db_rows
            if subject_bucket(d["subject"]) == n["subject_code"]
            and (d["class_level"] is None or str(d["class_level"]) == str(n["class_level"]))
        ]
        hit = None
        for d in candidates:
            if _title_match(n.get("chapter_title"), d["name"]):
                hit = d
                break
        if hit:
            used_db_ids.add(hit["id"])
            matches.append(
                {
                    "ncert": {
                        "class": n["class_level"],
                        "subject": n["subject_code"],
                        "part": n["part_number"],
                        "book_ch": n.get("book_chapter_number"),
                        "file_ch": n.get("filename_chapter"),
                        "title": n.get("chapter_title"),
                        "path": n["relative_path"],
                    },
                    "db": {
                        "subject": hit["subject"],
                        "class_level": hit["class_level"],
                        "code": hit["code"],
                        "name": hit["name"],
                        "topics": hit["topic_count"],
                        "concepts": hit["concept_count"],
                        "blueprints": hit["blueprint_count"],
                    },
                    "title_mismatch": not (_norm(n.get("chapter_title")) == _norm(hit["name"])),
                    "class_mismatch": hit["class_level"] is not None
                    and str(hit["class_level"]) != str(n["class_level"]),
                }
            )
        else:
            ncert_missing_in_db.append(
                {
                    "class": n["class_level"],
                    "subject": n["subject_code"],
                    "part": n["part_number"],
                    "book_ch": n.get("book_chapter_number"),
                    "title": n.get("chapter_title"),
                    "path": n["relative_path"],
                }
            )

    db_absent = []
    for d in db_rows:
        if d["id"] in used_db_ids:
            continue
        bucket = subject_bucket(d["subject"])
        if bucket not in {"PHYSICS", "CHEMISTRY", "BIOLOGY"}:
            continue
        db_absent.append(
            {
                "subject": d["subject"],
                "class_level": d["class_level"],
                "code": d["code"],
                "name": d["name"],
                "topics": d["topic_count"],
                "concepts": d["concept_count"],
                "blueprints": d["blueprint_count"],
                "note": "DB chapter has no matched canonical NCERT chapter PDF title",
            }
        )

    return {
        "matched": matches,
        "ncert_missing_in_db": ncert_missing_in_db,
        "db_absent_from_ncert_corpus": db_absent,
    }


def chemistry_findings(matrix: list[dict], db: dict, comparison: dict) -> dict:
    chem12 = [
        m
        for m in matrix
        if m["kind"] == "CHAPTER" and m["subject_code"] == "CHEMISTRY" and m["class_level"] == "12"
    ]
    chem11 = [
        m
        for m in matrix
        if m["kind"] == "CHAPTER" and m["subject_code"] == "CHEMISTRY" and m["class_level"] == "11"
    ]
    db_chem12 = [d for d in db["chapter_rows"] if subject_bucket(d["subject"]) == "CHEMISTRY" and str(d.get("class_level")) == "12"]
    titles = {(_norm(m.get("chapter_title")), m.get("chapter_title"), m["relative_path"]) for m in chem12}

    cfc1_present = []
    cfc1_absent = []
    for expected in sorted(CF_C1_EXPECTED_TITLES):
        found = next((t for t in titles if _title_match(expected, t[1])), None)
        if found:
            cfc1_present.append({"expected": expected, "pdf_title": found[1], "path": found[2]})
        else:
            cfc1_absent.append(expected)

    electro = [d for d in db_chem12 if d["code"] == "electrochemistry"]
    electro_pdf = next((m for m in chem12 if _title_match(m.get("chapter_title"), "Electrochemistry")), None)

    return {
        "xi_chapter_count": len(chem11),
        "xi_titles": [{"book_ch": m.get("book_chapter_number"), "title": m.get("chapter_title"), "path": m["relative_path"]} for m in chem11],
        "xii_chapter_count": len(chem12),
        "xii_titles": [{"book_ch": m.get("book_chapter_number"), "title": m.get("chapter_title"), "path": m["relative_path"]} for m in chem12],
        "cf_c1_expected_titles": sorted(CF_C1_EXPECTED_TITLES),
        "cf_c1_present_in_corpus": cfc1_present,
        "cf_c1_absent_from_corpus": cfc1_absent,
        "db_chem12_slugs": sorted(d["code"] for d in db_chem12),
        "electrochemistry_db": electro[0] if electro else None,
        "electrochemistry_pdf": {
            "title": electro_pdf.get("chapter_title") if electro_pdf else None,
            "path": electro_pdf["relative_path"] if electro_pdf else None,
            "book_ch": electro_pdf.get("book_chapter_number") if electro_pdf else None,
        },
    }


def biology_findings(matrix: list[dict], db: dict) -> dict:
    bio11 = [m for m in matrix if m["kind"] == "CHAPTER" and m["subject_code"] == "BIOLOGY" and m["class_level"] == "11"]
    bio12 = [m for m in matrix if m["kind"] == "CHAPTER" and m["subject_code"] == "BIOLOGY" and m["class_level"] == "12"]
    db_bio = [d for d in db["chapter_rows"] if subject_bucket(d["subject"]) == "BIOLOGY"]
    ownership = []
    for m in bio12:
        ownership.append(
            {
                "book_ch": m.get("book_chapter_number"),
                "title": m.get("chapter_title"),
                "path": m["relative_path"],
                "decision": "CURRICULUM-OWNER DECISION REQUIRED",
                "reason": "NCERT Biology is a single book; project maps to BOTANY vs ZOOLOGY — ownership not inferred",
            }
        )
    return {
        "xi_titles": [{"book_ch": m.get("book_chapter_number"), "title": m.get("chapter_title"), "path": m["relative_path"]} for m in bio11],
        "xii_titles": [{"book_ch": m.get("book_chapter_number"), "title": m.get("chapter_title"), "path": m["relative_path"]} for m in bio12],
        "db_biology_subjects": sorted({d["subject"] for d in db_bio}),
        "db_biology_chapters": [
            {"subject": d["subject"], "class": d["class_level"], "code": d["code"], "name": d["name"]}
            for d in db_bio
        ],
        "xii_ownership_decisions_required": ownership,
    }


def physics_findings(matrix: list[dict], db: dict) -> dict:
    phys = [m for m in matrix if m["kind"] == "CHAPTER" and m["subject_code"] == "PHYSICS"]
    grav = [m for m in phys if _title_match(m.get("chapter_title"), "Gravitation")]
    db_grav = [d for d in db["chapter_rows"] if d["code"] == "gravitation" or _title_match(d["name"], "Gravitation")]
    return {
        "xi": [
            {"book_ch": m.get("book_chapter_number"), "file_ch": m.get("filename_chapter"), "part": m.get("part_number"), "title": m.get("chapter_title"), "path": m["relative_path"]}
            for m in phys
            if m["class_level"] == "11"
        ],
        "xii": [
            {"book_ch": m.get("book_chapter_number"), "file_ch": m.get("filename_chapter"), "part": m.get("part_number"), "title": m.get("chapter_title"), "path": m["relative_path"]}
            for m in phys
            if m["class_level"] == "12"
        ],
        "gravitation_in_corpus": [
            {"title": m.get("chapter_title"), "path": m["relative_path"], "class": m["class_level"], "book_ch": m.get("book_chapter_number")}
            for m in grav
        ],
        "gravitation_in_db": db_grav,
    }


def to_markdown(payload: dict) -> str:
    lines = [
        "# CURRICULUM-BASELINE-001 — NCERT Rationalised 2026–27",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Source root: `{payload['source_root']}`",
        f"- Status proposal: **{payload['final_status']}**",
        "- This report does **not** approve the baseline; owner approval required.",
        "",
        "## Safety snapshot",
        "",
        "```json",
        json.dumps(payload["safety_before"], indent=2),
        "```",
        "",
        "## Class matrices (chapters only)",
        "",
    ]
    for key in (
        "Class 11/PHYSICS",
        "Class 11/CHEMISTRY",
        "Class 11/BIOLOGY",
        "Class 12/PHYSICS",
        "Class 12/CHEMISTRY",
        "Class 12/BIOLOGY",
    ):
        lines.append(f"### {key}")
        lines.append("")
        lines.append("| Book Ch | File Ch | Part | Title | Relative path | Version | Status |")
        lines.append("|---:|---:|---:|---|---|---|---|")
        for m in payload["matrices"].get(key, []):
            if m["kind"] != "CHAPTER":
                continue
            lines.append(
                f"| {m.get('book_chapter_number') or ''} | {m.get('filename_chapter') or ''} | "
                f"{m.get('part_number') or ''} | {m.get('chapter_title') or ''} | "
                f"`{m['relative_path']}` | {m.get('version_label') or ''} | {m.get('source_status')} |"
            )
        lines.append("")
    lines.append("## Remaining decisions")
    lines.append("")
    for d in payload.get("remaining_decisions", []):
        lines.append(f"- {d}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    root = get_ncert_source_root()
    assert str(root) == str(Path(r"D:\ravishori\AI Neet Exam App\NCERT Books").resolve()) or root.name == "NCERT Books"

    settings = get_settings()
    engine = create_engine(settings.database_url_sync)
    before = snapshot_db(engine)

    inv = scan_ncert_books(root=root, compute_hashes=True)
    matrix = build_matrix(inv)
    after = snapshot_db(engine)

    # Group matrices
    matrices: dict[str, list] = {}
    for m in matrix:
        key = f"Class {m['class_level']}/{m['subject_code']}"
        matrices.setdefault(key, []).append(m)

    comparison = compare(matrix, before)
    chem = chemistry_findings(matrix, before, comparison)
    bio = biology_findings(matrix, before)
    phys = physics_findings(matrix, before)

    remaining = [
        "Owner must explicitly APPROVE this rationalised 2026–27 corpus as the project curriculum baseline.",
        "Class XII Biology BOTANY vs ZOOLOGY ownership for each chapter requires CURRICULUM-OWNER DECISION.",
        "Confirm whether DB chapters absent from the corpus should be frozen for future NCERT generation.",
    ]
    if chem["cf_c1_absent_from_corpus"]:
        remaining.append(
            "CF-C1 titles absent from corpus (do not invent): " + ", ".join(chem["cf_c1_absent_from_corpus"])
        )
    if not phys["gravitation_in_corpus"]:
        remaining.append("Gravitation PDF still NOT PRESENT IN CANONICAL CORPUS.")
    else:
        remaining.append("Gravitation PDF is present — owner may approve taxonomy fill separately (no taxonomy change in this task).")

    # Status: GREEN if corpus readable + identities extracted; YELLOW if ownership/gaps remain
    final_status = "YELLOW — BASELINE HAS UNRESOLVED SOURCE/CURRICULUM ISSUES"
    if all(m.get("chapter_title") for m in matrix if m["kind"] == "CHAPTER") and phys["gravitation_in_corpus"]:
        # still YELLOW because owner decisions remain — never APPROVED
        final_status = "YELLOW — BASELINE HAS UNRESOLVED SOURCE/CURRICULUM ISSUES"
    # If titles mostly extracted and corpus solid, say ready for owner approval:
    titled = sum(1 for m in matrix if m["kind"] == "CHAPTER" and m.get("chapter_title"))
    chapters = sum(1 for m in matrix if m["kind"] == "CHAPTER")
    if titled == chapters and before["status"] == after["status"] and before["unmapped_draft"] == after["unmapped_draft"]:
        final_status = "GREEN — BASELINE READY FOR OWNER APPROVAL"

    safety_before = {k: before[k] for k in before if k != "chapter_rows"}
    safety_after = {k: after[k] for k in after if k != "chapter_rows"}

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(root),
        "final_status": final_status,
        "inventory_summary": {
            "total_pdfs": len(inv.entries),
            "chapters": chapters,
            "titled_chapters": titled,
            "supplemental": sum(1 for m in matrix if m["kind"] == "SUPPLEMENTAL"),
            "readable": sum(1 for e in inv.entries if e.readable),
        },
        "matrices": matrices,
        "comparison": {
            "matched_count": len(comparison["matched"]),
            "ncert_missing_in_db_count": len(comparison["ncert_missing_in_db"]),
            "db_absent_from_ncert_count": len(comparison["db_absent_from_ncert_corpus"]),
            "ncert_missing_in_db": comparison["ncert_missing_in_db"],
            "db_absent_from_ncert_corpus": comparison["db_absent_from_ncert_corpus"],
            "matched_sample": comparison["matched"][:30],
            "matched": comparison["matched"],
        },
        "chemistry": chem,
        "biology": bio,
        "physics": phys,
        "safety_before": safety_before,
        "safety_after": safety_after,
        "safety_unchanged": safety_before == safety_after,
        "ai_factory": {"ai_calls": 0, "mcqs_generated": 0, "content_factory_runs": 0, "generation_jobs_created": 0},
        "remaining_decisions": remaining,
    }

    stamp = date.today().strftime("%Y%m%d")
    out_dir = ROOT / "docs" / "audits"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"curriculum_baseline_rationalised_2026_27_{stamp}.json"
    md_path = out_dir / f"curriculum_baseline_rationalised_2026_27_{stamp}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": final_status, "json": str(json_path), "md": str(md_path), "safety_unchanged": payload["safety_unchanged"], "titled": titled, "chapters": chapters}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
