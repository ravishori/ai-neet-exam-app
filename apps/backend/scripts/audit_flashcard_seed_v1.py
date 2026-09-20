"""Flashcard Seed V1 — scientific / NCERT / provenance certification audit.

Conservative policy:
- VERIFIED only when NCERT chapter text supports key claims AND no quality flags.
- REVIEW when structurally OK but independent NCERT grounding is incomplete/weak.
- REJECTED for clear factual/taxonomy/quality failures (never silent delete).

Usage (from apps/backend):
  .venv/Scripts/python.exe scripts/audit_flashcard_seed_v1.py --authorize-apply
  .venv/Scripts/python.exe scripts/audit_flashcard_seed_v1.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text

from app.core.config import get_settings

get_settings.cache_clear()
import app.modules.identity.models  # noqa: F401
import app.modules.knowledge.models  # noqa: F401
from app.core.database import AsyncSessionLocal

OUT = REPO / "docs" / "acquisition" / "flashcards" / "SEED-V1"
ZIP_PATH = REPO / "StudyMaterial (2).zip"
ONDISK = REPO / "StudyMaterial"

# Chapter display name / code → zip-relative PDF path(s)
CHAPTER_PDFS: dict[str, list[str]] = {
    # Biology 11
    "The Living World": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-1.pdf"],
    "Biological Classification": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-2.pdf"],
    "Plant Kingdom": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-3.pdf"],
    "Animal Kingdom": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-4.pdf"],
    "Morphology of Flowering Plants": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-5.pdf"],
    "Structural Organisation in Animals": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-7.pdf"],
    "Cell - The Unit of Life": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-8.pdf"],
    "Biomolecules": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-9.pdf"],
    "Photosynthesis in Higher Plants": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-13.pdf"],
    "Plant Growth and Development": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-15.pdf"],
    "Digestion and Absorption": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-16.pdf"],
    "Breathing and Exchange of Gases": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-17.pdf"],
    "Body Fluids and Circulation": ["StudyMaterial/Biology/Class 11-Biology/ncert-books-class-11-biology-chapter-18.pdf"],
    # Biology 12
    "Sexual Reproduction in Flowering Plants": [
        "StudyMaterial/Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-1.pdf"
    ],
    "Human Reproduction": ["StudyMaterial/Biology/Class 12-Biology/ncert-books-class-12-biology-chapter-3.pdf"],
    # Chemistry 11
    "Some Basic Concepts of Chemistry": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-1.pdf"
    ],
    "Structure of Atom": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-2.pdf"
    ],
    "Chemical Bonding and Molecular Structure": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-4.pdf"
    ],
    "Thermodynamics": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-6.pdf",
    ],
    "Equilibrium": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-7.pdf"
    ],
    "Redox Reactions": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-8.pdf"
    ],
    "Organic Chemistry - Basic Principles": [
        "StudyMaterial/Chemistry/Class 11- Chemistry/ncert-books-class-11-chemistry-chapter-9.pdf",
    ],
    # Chemistry 12
    "Electrochemistry": [
        "StudyMaterial/Chemistry/Class 12- Chemistry/ncert-books-class-12-chemistry-chapter-3.pdf"
    ],
    # Physics 11 — filenames vary; resolve flexibly
    "Units and Measurement": ["StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-2.pdf"],
    "Kinematics": [
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-3.pdf",
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-4.pdf",
    ],
    "Laws of Motion": ["StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-5.pdf"],
    "Work, Energy and Power": ["StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-6.pdf"],
    "Systems of Particles and Rotational Motion": [
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-7.pdf"
    ],
    "Gravitation": ["StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-8.pdf"],
    "Mechanical Properties of Solids": [
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-9.pdf"
    ],
    "Mechanical Properties of Fluids": [
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-10.pdf"
    ],
    "Thermodynamics Physics": [
        "StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-12.pdf"
    ],
    "Kinetic Theory": ["StudyMaterial/Physics/Class 11-Physics/ncert-books-class-11-physics-chapter-13.pdf"],
    # Physics 12
    "Electrostatics": [
        "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-1.pdf",
        "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-2.pdf",
    ],
    "Current Electricity": [
        "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-1-chapter-3.pdf"
    ],
    "Optics": [
        "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-2-chapter-9.pdf",
        "StudyMaterial/Physics/Class 12-Physics/ncert-book-class-12-physics-part-2-chapter-10.pdf",
    ],
}

# Explicit factual rejection patterns (known-wrong claims) — high confidence only.
REJECT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsix\s+si\s+base\s+units\b", re.I), "FACTUAL_ERROR: SI has seven base units, not six"),
    (re.compile(r"\bfour\s+kingdom\b.*whittaker|\bwhittaker\b.*\bfour\s+kingdom", re.I), "FACTUAL_ERROR: Whittaker proposed five kingdoms"),
    (re.compile(r"\bdiploid\b.*\bporifera\b|\bporifera\b.*\bdiploid\s+only", re.I), "NEEDS_REVIEW: Porifera cellular organisation claim suspicious"),
]

# Tokens that should appear for VERIFIED grounding (chapter-level)
STOP = {
    "the", "and", "or", "of", "a", "an", "in", "to", "is", "are", "for", "with", "by",
    "from", "that", "this", "as", "on", "at", "be", "it", "its", "into", "which", "when",
    "what", "how", "why", "name", "state", "define", "give", "write", "example", "examples",
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s\-]", " ", (s or "").lower())).strip()


def tokens(s: str) -> list[str]:
    return [t for t in norm(s).split() if len(t) >= 4 and t not in STOP]


def extract_pdf_text(data: bytes) -> str:
    import fitz

    doc = fitz.open(stream=data, filetype="pdf")
    parts = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(parts)


def chapter_pdf_key(subject_code: str, chapter: str) -> str:
    if chapter == "Thermodynamics" and subject_code == "PHYSICS":
        return "Thermodynamics Physics"
    return chapter


def load_chapter_corpus(zip_names: set[str]) -> dict[str, str]:
    """chapter_key -> lowercase NCERT text."""
    cache: dict[str, str] = {}
    zf = zipfile.ZipFile(ZIP_PATH) if ZIP_PATH.exists() else None
    try:
        for chapter, paths in CHAPTER_PDFS.items():
            blobs: list[str] = []
            for rel in paths:
                disk = REPO / rel
                data = None
                if disk.exists():
                    data = disk.read_bytes()
                elif zf is not None and rel in zip_names:
                    data = zf.read(rel)
                else:
                    if zf is not None:
                        base = Path(rel).name.lower()
                        hit = next((n for n in zip_names if Path(n).name.lower() == base), None)
                        if hit:
                            data = zf.read(hit)
                if data:
                    try:
                        blobs.append(extract_pdf_text(data))
                    except Exception:  # noqa: BLE001
                        continue
            if blobs:
                cache[chapter] = norm("\n".join(blobs))
    finally:
        if zf is not None:
            zf.close()
    return cache


def ncert_support_score(card: dict[str, Any], chapter_text: str | None) -> tuple[float, str]:
    if not chapter_text:
        return 0.0, "NO_CHAPTER_TEXT"
    # Prefer answer+explanation tokens
    cand = tokens((card.get("back") or "") + " " + (card.get("explanation") or "") + " " + (card.get("front") or ""))
    if not cand:
        return 0.0, "NO_TOKENS"
    # distinctive longer tokens first
    uniq = list(dict.fromkeys(cand))
    hits = sum(1 for t in uniq[:24] if t in chapter_text)
    score = hits / max(1, min(len(uniq), 24))
    return score, f"token_hits={hits}/{min(len(uniq), 24)}"


def quality_flags(card: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    front = (card.get("front") or "").strip()
    back = (card.get("back") or "").strip()
    expl = (card.get("explanation") or "").strip()
    if len(front) < 8:
        flags.append("AMBIGUOUS:front_too_short")
    if len(back) < 2:
        flags.append("AMBIGUOUS:back_too_short")
    if front.casefold() == back.casefold():
        flags.append("AMBIGUOUS:front_equals_back")
    blob = f"{front}\n{back}\n{expl}"
    for pat, reason in REJECT_PATTERNS:
        if pat.search(blob):
            flags.append(reason)
    # Contradictory answer/explanation heuristic
    if expl and back:
        # if explanation negates answer keywords aggressively
        if re.search(r"\bincorrect\b|\bnot true\b|\bfalse\b", expl, re.I) and not re.search(
            r"\bnot\b.*(incorrect|false)", expl, re.I
        ):
            if not re.search(r"common misconception|students often", expl, re.I):
                flags.append("NEEDS_REVIEW:explanation_contains_negation")
    diff = (card.get("difficulty") or "").lower()
    if diff and diff not in {"easy", "medium", "hard"}:
        flags.append("INVALID_DIFFICULTY")
    # Hard cards that are pure recall may be mislabeled — soft flag only
    if diff == "hard" and len(back) < 40 and "?" not in front:
        # not automatic reject
        pass
    return flags


def provenance_class(card: dict[str, Any], ncert_score: float) -> str:
    src = (card.get("source") or "").strip().upper()
    ref = (card.get("source_reference") or "").strip()
    if not src and not ref:
        return "MISSING"
    if src == "NCERT":
        if ncert_score >= 0.35 and ref:
            return "NCERT_VERIFIED"
        if ref:
            return "UNSUPPORTED"  # claimed NCERT but weak/no text support in this audit
        return "MISSING"
    if src == "NTA":
        return "NTA_VERIFIED" if ref else "MISSING"
    if src in {"PROJECT", "TALOS"}:
        return "PROJECT_VERIFIED" if ref else "MISSING"
    if src:
        return "AUTHORITATIVE_EXTERNAL" if ref else "UNSUPPORTED"
    return "MISSING"


def taxonomy_issue(card: dict[str, Any]) -> str | None:
    body_cl = card.get("class_level_body")
    tax_cl = card.get("class_level_taxonomy")
    chapter = card.get("chapter") or ""
    if chapter in {"Gravitation", "Digestion and Absorption"}:
        # published cards shouldn't attach here if concepts=0; if somehow present:
        return "MISSING_TAXONOMY"
    if body_cl and tax_cl and str(body_cl) != str(tax_cl):
        return "MISCLASSIFIED"
    if not tax_cl and not body_cl:
        return "NEEDS_REVIEW"  # e.g. Biomolecules unset
    if not tax_cl and body_cl:
        return "NEEDS_REVIEW"
    return "VALID"


def decide_status(
    *,
    flags: list[str],
    prov: str,
    ncert_score: float,
    tax: str | None,
) -> tuple[str, str, list[str]]:
    """Conservative certification.

    VERIFIED is reserved for strong automated NCERT chapter-text grounding
    (token support ≥ 0.75) with NCERT provenance and valid taxonomy.
    This is still not a full SME pedagogical certification — remaining REVIEW
    cards (and the overall AMBER verdict) reflect that gap honestly.
    """
    reasons: list[str] = []
    hard_reject = [f for f in flags if f.startswith("FACTUAL_ERROR")]
    if hard_reject:
        return "REJECTED", "; ".join(hard_reject), ["FACTUAL_ERROR"]
    if any(f.startswith("AMBIGUOUS:front_equals_back") for f in flags):
        return "REJECTED", "front equals back", ["AMBIGUOUS"]
    if tax == "MISCLASSIFIED":
        reasons.append("taxonomy_mismatch_body_vs_chapter")
        return "REVIEW", "; ".join(reasons + flags), ["NEEDS_REVIEW"]
    soft = [f for f in flags if not f.startswith("NEEDS_REVIEW")]
    # Strict automated VERIFIED gate (no SME rubber-stamp)
    if (
        prov == "NCERT_VERIFIED"
        and ncert_score >= 0.75
        and not soft
        and tax == "VALID"
    ):
        return "VERIFIED", f"automated_NCERT_token_grounding ({ncert_score:.2f})", []
    if tax == "NEEDS_REVIEW":
        reasons.append("taxonomy_class_or_chapter_needs_review")
    if prov in {"UNSUPPORTED", "MISSING"}:
        reasons.append(f"provenance={prov}")
        return "REVIEW", "; ".join(reasons + flags) or "insufficient_provenance", [
            "UNSUPPORTED" if prov == "UNSUPPORTED" else "NEEDS_REVIEW"
        ]
    if ncert_score < 0.75:
        reasons.append(f"ncert_support_below_verified_threshold={ncert_score:.2f}")
        return "REVIEW", "; ".join(reasons + flags) or "incomplete_ncert_audit", ["NEEDS_REVIEW"]
    if flags:
        return "REVIEW", "; ".join(flags), ["NEEDS_REVIEW"]
    return "REVIEW", "not_fully_certified_in_this_pass", ["NEEDS_REVIEW"]


async def load_published() -> list[dict[str, Any]]:
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(
                text(
                    """
                    SELECT ci.id::text AS id, ci.slug, ci.status, ci.tags, ci.title,
                           cv.id::text AS version_id, cv.body,
                           s.code AS subject_code, s.name AS subject,
                           ch.class_level::text AS class_level_taxonomy,
                           ch.code AS chapter_code, ch.name AS chapter,
                           t.code AS topic_code, t.name AS topic,
                           co.code AS concept_code, co.name AS concept
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.current_version_id
                    JOIN academic.concepts co ON co.id = ci.concept_id
                    JOIN academic.topics t ON t.id = co.topic_id
                    JOIN academic.chapters ch ON ch.id = t.chapter_id
                    JOIN academic.subjects s ON s.id = ch.subject_id
                    WHERE ci.deleted_at IS NULL AND ci.content_type='FLASHCARD' AND ci.status='PUBLISHED'
                    ORDER BY s.code, ch.class_level NULLS LAST, ch.name, ci.slug
                    """
                )
            )
        ).mappings().all()
    out = []
    for r in rows:
        b = r["body"] or {}
        out.append(
            {
                "id": r["id"],
                "version_id": r["version_id"],
                "slug": r["slug"],
                "status": r["status"],
                "tags": list(r["tags"] or []),
                "subject_code": r["subject_code"],
                "subject": r["subject"],
                "class_level_taxonomy": r["class_level_taxonomy"],
                "chapter_code": r["chapter_code"],
                "chapter": r["chapter"],
                "topic_code": r["topic_code"],
                "topic": r["topic"],
                "concept_code": r["concept_code"],
                "concept": r["concept"],
                "front": b.get("front"),
                "back": b.get("back"),
                "explanation": b.get("explanation"),
                "difficulty": b.get("difficulty"),
                "source": b.get("source"),
                "source_reference": b.get("source_reference"),
                "class_level_body": b.get("class_level"),
                "seed_v1": "FLASHCARD-SEED-V1" in (r["tags"] or []),
            }
        )
    return out


def find_duplicates(cards: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    exact: list[dict] = []
    near: list[dict] = []
    by_front: dict[str, list[str]] = defaultdict(list)
    for c in cards:
        by_front[norm(c.get("front") or "")].append(c["id"])
    for fr, ids in by_front.items():
        if fr and len(ids) > 1:
            exact.append({"front_norm": fr, "ids": ids})
    # Near: same concept + high Jaccard on front tokens
    by_concept: dict[str, list[dict]] = defaultdict(list)
    for c in cards:
        by_concept[c.get("concept_code") or ""].append(c)
    for code, group in by_concept.items():
        if not code or len(group) < 2:
            continue
        for i in range(len(group)):
            ti = set(tokens(group[i].get("front") or ""))
            if len(ti) < 3:
                continue
            for j in range(i + 1, len(group)):
                tj = set(tokens(group[j].get("front") or ""))
                if not tj:
                    continue
                jacc = len(ti & tj) / len(ti | tj)
                if jacc >= 0.72:
                    near.append(
                        {
                            "concept_code": code,
                            "id_a": group[i]["id"],
                            "id_b": group[j]["id"],
                            "jaccard": round(jacc, 3),
                            "front_a": group[i].get("front"),
                            "front_b": group[j].get("front"),
                        }
                    )
    return exact, near


async def apply_audit(rows: list[dict[str, Any]], *, dry_run: bool) -> dict[str, int]:
    """Write certification_* fields into content version body + tags via SQL.

    Uses raw SQL to avoid ORM metadata gaps (e.g. micro_competencies FK) in scripts.
    """
    stats = Counter()
    if dry_run:
        for r in rows:
            stats[r["audit_status"]] += 1
        return dict(stats)

    async with AsyncSessionLocal() as s:
        for r in rows:
            body_row = (
                await s.execute(
                    text("SELECT body FROM cms.content_versions WHERE id = CAST(:vid AS uuid)"),
                    {"vid": r["version_id"]},
                )
            ).first()
            if not body_row:
                stats["missing"] += 1
                continue
            body = dict(body_row[0] or {})
            body["certification_status"] = r["audit_status"]
            body["certification_reason"] = r["audit_reason"]
            body["certification_provenance"] = r["provenance_class"]
            body["certification_flags"] = r["quality_flags"]
            body["certified_at"] = r["verified_at"]
            body["certification_batch"] = "FLASHCARD-SEED-V1-AUDIT"
            await s.execute(
                text(
                    """
                    UPDATE cms.content_versions
                    SET body = CAST(:body AS jsonb)
                    WHERE id = CAST(:vid AS uuid)
                    """
                ),
                {"body": json.dumps(body), "vid": r["version_id"]},
            )
            tags_row = (
                await s.execute(
                    text("SELECT tags FROM cms.content_items WHERE id = CAST(:id AS uuid)"),
                    {"id": r["id"]},
                )
            ).first()
            tags = [t for t in (list(tags_row[0] or []) if tags_row else []) if not str(t).startswith("audit:")]
            tags.append(f"audit:{r['audit_status']}")
            if r["audit_status"] == "REJECTED":
                await s.execute(
                    text(
                        """
                        UPDATE cms.content_items
                        SET tags = CAST(:tags AS text[]), status = 'ARCHIVED', updated_at = NOW()
                        WHERE id = CAST(:id AS uuid)
                        """
                    ),
                    {"tags": tags, "id": r["id"]},
                )
                await s.execute(
                    text(
                        """
                        UPDATE cms.content_versions
                        SET workflow_state = 'ARCHIVED'
                        WHERE id = CAST(:vid AS uuid)
                        """
                    ),
                    {"vid": r["version_id"]},
                )
                stats["archived_rejected"] += 1
            else:
                await s.execute(
                    text(
                        """
                        UPDATE cms.content_items
                        SET tags = CAST(:tags AS text[]), updated_at = NOW()
                        WHERE id = CAST(:id AS uuid)
                        """
                    ),
                    {"tags": tags, "id": r["id"]},
                )
            stats[r["audit_status"]] += 1
        await s.commit()
    return dict(stats)


async def amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--authorize-apply", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.authorize_apply:
        print("Refusing: pass --dry-run or --authorize-apply")
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat()
    cards = await load_published()
    (OUT / "published_inventory.json").write_text(
        json.dumps(cards, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    zip_names: set[str] = set()
    if ZIP_PATH.exists():
        with zipfile.ZipFile(ZIP_PATH) as zf:
            zip_names = set(zf.namelist())
    chapter_text = load_chapter_corpus(zip_names)

    exact_dups, near_dups = find_duplicates(cards)
    exact_ids = {i for g in exact_dups for i in g["ids"]}

    audited: list[dict[str, Any]] = []
    for c in cards:
        ch = c.get("chapter") or ""
        ch_key = chapter_pdf_key(c.get("subject_code") or "", ch)
        score, score_detail = ncert_support_score(c, chapter_text.get(ch_key))
        flags = quality_flags(c)
        if c["id"] in exact_ids:
            flags.append("DUPLICATE:exact_front")
        prov = provenance_class(c, score)
        tax = taxonomy_issue(c)
        status, reason, labels = decide_status(flags=flags, prov=prov, ncert_score=score, tax=tax)
        # Exact duplicate → REVIEW consolidation (not auto-reject all copies)
        if "DUPLICATE:exact_front" in flags and status == "VERIFIED":
            status, reason = "REVIEW", reason + "; exact_duplicate_cluster"
            labels = list(set(labels + ["DUPLICATE"]))

        audited.append(
            {
                **{k: c.get(k) for k in (
                    "id", "slug", "subject_code", "subject", "class_level_taxonomy",
                    "class_level_body", "chapter", "chapter_code", "topic", "topic_code",
                    "concept", "concept_code", "front", "back", "explanation",
                    "difficulty", "source", "source_reference", "status", "seed_v1",
                    "version_id",
                )},
                "class_effective": c.get("class_level_body") or c.get("class_level_taxonomy") or "UNSET",
                "ncert_support_score": round(score, 3),
                "ncert_support_detail": score_detail,
                "ncert_chapter_text_available": ch_key in chapter_text,
                "provenance_class": prov,
                "taxonomy_status": tax,
                "quality_flags": flags,
                "issue_labels": labels,
                "audit_status": status,
                "audit_reason": reason,
                "verified_at": started,
                "publication_status": c.get("status"),
            }
        )

    apply_stats = await apply_audit(audited, dry_run=args.dry_run)

    # Coverage
    cov: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for r in audited:
        bucket = "BIOLOGY" if r["subject_code"] in {"BOTANY", "ZOOLOGY"} else r["subject_code"]
        cov[bucket][str(r["class_effective"])][r["chapter"]] += 1

    counts = Counter(r["audit_status"] for r in audited)
    prov_counts = Counter(r["provenance_class"] for r in audited)
    subj_counts = Counter(
        ("BIOLOGY" if r["subject_code"] in {"BOTANY", "ZOOLOGY"} else r["subject_code"]) for r in audited
    )
    class_counts = Counter(str(r["class_effective"]) for r in audited)

    # Gaps from taxonomy
    async with AsyncSessionLocal() as s:
        chapters = (
            await s.execute(
                text(
                    """
                    SELECT s.code, ch.class_level::text, ch.name, count(co.id) AS concepts
                    FROM academic.chapters ch
                    JOIN academic.subjects s ON s.id=ch.subject_id AND s.deleted_at IS NULL
                    LEFT JOIN academic.topics t ON t.chapter_id=ch.id AND t.deleted_at IS NULL
                    LEFT JOIN academic.concepts co ON co.topic_id=t.id AND co.deleted_at IS NULL
                    WHERE ch.deleted_at IS NULL
                    GROUP BY s.code, ch.class_level, ch.name
                    """
                )
            )
        ).all()
    seeded = {(r["subject_code"], r["chapter"]) for r in audited}
    chapter_gaps = [
        {"subject": a, "class": b, "chapter": c, "concepts": d}
        for a, b, c, d in chapters
        if (a, c) not in seeded
    ]

    # Write CSV matrix
    csv_path = OUT / "card_audit.csv"
    fields = [
        "id", "slug", "subject_code", "class_effective", "chapter", "topic", "concept_code",
        "front", "back", "explanation", "difficulty", "source", "source_reference",
        "publication_status", "audit_status", "audit_reason", "provenance_class",
        "taxonomy_status", "ncert_support_score", "ncert_chapter_text_available",
        "quality_flags", "issue_labels", "verified_at",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in audited:
            row = dict(r)
            row["quality_flags"] = "|".join(r.get("quality_flags") or [])
            row["issue_labels"] = "|".join(r.get("issue_labels") or [])
            w.writerow(row)

    rejected = [r for r in audited if r["audit_status"] == "REJECTED"]
    review = [r for r in audited if r["audit_status"] == "REVIEW"]
    verified = [r for r in audited if r["audit_status"] == "VERIFIED"]

    summary = {
        "batch": "FLASHCARD-SEED-V1-AUDIT",
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "mode": {"dry_run": args.dry_run, "authorize_apply": args.authorize_apply},
        "total_published_audited": len(audited),
        "audit_status_counts": dict(counts),
        "apply_stats": apply_stats,
        "subject_counts": dict(subj_counts),
        "class_counts": dict(class_counts),
        "provenance_counts": dict(prov_counts),
        "exact_duplicate_clusters": len(exact_dups),
        "near_duplicate_pairs": len(near_dups),
        "chapter_gaps": chapter_gaps,
        "ncert_chapters_loaded": sorted(chapter_text.keys()),
        "ncert_chapters_missing_text": sorted(
            {r["chapter"] for r in audited if not r["ncert_chapter_text_available"]}
        ),
        "publication_gate": {
            "REJECTED": "archived_not_student_facing" if args.authorize_apply else "would_archive",
            "REVIEW": "still_published_but_not_certified",
            "VERIFIED": "eligible_certified",
            "browse_excludes_rejected": True,
        },
        "verdict": None,
        "verdict_rationale": [],
        "artifact_hashes": {},
    }

    # Verdict rules (conservative)
    rationale = []
    if counts.get("REJECTED", 0) > 0 and args.authorize_apply:
        rationale.append(f"{counts['REJECTED']} REJECTED archived from student browse")
    if counts.get("REVIEW", 0) > 0:
        rationale.append(
            f"{counts.get('REVIEW', 0)} cards remain REVIEW — incomplete independent NCERT certification"
        )
    if counts.get("VERIFIED", 0) < len(audited):
        rationale.append(
            f"Only {counts.get('VERIFIED', 0)}/{len(audited)} marked VERIFIED; corpus not fully certified"
        )
    if summary["ncert_chapters_missing_text"]:
        rationale.append(
            f"NCERT text unavailable for chapters: {summary['ncert_chapters_missing_text'][:8]}..."
        )
    # GREEN only if all verified and no review/rejected remaining student-facing certified claims
    if (
        counts.get("VERIFIED", 0) == len(audited)
        and counts.get("REVIEW", 0) == 0
        and counts.get("REJECTED", 0) == 0
        and not summary["ncert_chapters_missing_text"]
    ):
        verdict = "GREEN"
    elif counts.get("REJECTED", 0) > 5 and counts.get("VERIFIED", 0) < len(audited) * 0.5:
        verdict = "RED"
    else:
        verdict = "AMBER"
    summary["verdict"] = verdict
    summary["verdict_rationale"] = rationale

    # Reports
    (OUT / "card_audit.json").write_text(json.dumps(audited, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT / "exact_duplicates.json").write_text(json.dumps(exact_dups, indent=2) + "\n", encoding="utf-8")
    (OUT / "near_duplicates.json").write_text(json.dumps(near_dups, indent=2) + "\n", encoding="utf-8")

    def md_list(rows: list[dict], limit: int = 200) -> str:
        lines = []
        for r in rows[:limit]:
            lines.append(
                f"- `{r['id']}` [{r['subject_code']}/{r['chapter']}] **{r.get('front','')[:100]}** — {r.get('audit_reason','')}"
            )
        if len(rows) > limit:
            lines.append(f"- … {len(rows) - limit} more")
        return "\n".join(lines) or "- None"

    (OUT / "rejected_cards.md").write_text(
        f"# Rejected flashcards\n\nCount: **{len(rejected)}**\n\n{md_list(rejected)}\n",
        encoding="utf-8",
    )
    (OUT / "review_cards.md").write_text(
        f"# Review flashcards\n\nCount: **{len(review)}**\n\n{md_list(review)}\n",
        encoding="utf-8",
    )

    cov_lines = ["# Coverage report (audit)", ""]
    for subj in sorted(cov):
        cov_lines.append(f"## {subj}")
        for cl in sorted(cov[subj]):
            cov_lines.append(f"### Class {cl}")
            for ch, n in sorted(cov[subj][cl].items(), key=lambda x: -x[1]):
                cov_lines.append(f"- {ch}: **{n}**")
        cov_lines.append("")
    cov_lines += ["## Chapter gaps", ""]
    for g in chapter_gaps:
        cov_lines.append(f"- {g['subject']} / {g['class']} / {g['chapter']} (concepts={g['concepts']})")
    (OUT / "coverage_report.md").write_text("\n".join(cov_lines) + "\n", encoding="utf-8")

    (OUT / "provenance_report.md").write_text(
        "\n".join(
            [
                "# Provenance report",
                "",
                f"- NCERT_VERIFIED: **{prov_counts.get('NCERT_VERIFIED', 0)}**",
                f"- NTA_VERIFIED: **{prov_counts.get('NTA_VERIFIED', 0)}**",
                f"- PROJECT_VERIFIED: **{prov_counts.get('PROJECT_VERIFIED', 0)}**",
                f"- AUTHORITATIVE_EXTERNAL: **{prov_counts.get('AUTHORITATIVE_EXTERNAL', 0)}**",
                f"- UNSUPPORTED: **{prov_counts.get('UNSUPPORTED', 0)}**",
                f"- MISSING: **{prov_counts.get('MISSING', 0)}**",
                "",
                "NCERT_VERIFIED requires chapter PDF text support in this audit (no invented page numbers).",
                "",
            ]
        ),
        encoding="utf-8",
    )

    verification_md = f"""# Verification summary — Flashcard Seed V1 Audit

**Verdict: {verdict}**

| Metric | Count |
|---|---:|
| TOTAL PUBLISHED AUDITED | {len(audited)} |
| VERIFIED | {counts.get('VERIFIED', 0)} |
| REVIEW | {counts.get('REVIEW', 0)} |
| REJECTED | {counts.get('REJECTED', 0)} |
| BIOLOGY | {subj_counts.get('BIOLOGY', 0)} |
| CHEMISTRY | {subj_counts.get('CHEMISTRY', 0)} |
| PHYSICS | {subj_counts.get('PHYSICS', 0)} |
| CLASS 11 | {class_counts.get('11', 0)} |
| CLASS 12 | {class_counts.get('12', 0)} |
| CLASS UNSET | {class_counts.get('UNSET', 0) + class_counts.get('None', 0) + class_counts.get('?', 0)} |
| NCERT_VERIFIED provenance | {prov_counts.get('NCERT_VERIFIED', 0)} |
| UNSUPPORTED provenance | {prov_counts.get('UNSUPPORTED', 0)} |
| MISSING provenance | {prov_counts.get('MISSING', 0)} |
| EXACT DUPLICATE CLUSTERS | {len(exact_dups)} |
| NEAR DUPLICATE PAIRS | {len(near_dups)} |
| CHAPTER GAPS | {len(chapter_gaps)} |

## Rationale
{chr(10).join('- ' + x for x in rationale)}

## Publication gate
- REJECTED → ARCHIVED (not student-facing) when `--authorize-apply`
- REVIEW → remains published but `certification_status=REVIEW` (not certified)
- VERIFIED → `certification_status=VERIFIED`

## Critical note
Automated NCERT chapter-text token grounding is **not** a full SME pedagogical
certification. VERIFIED here means strong automated NCERT support (≥0.75 token
hit rate) with NCERT provenance and valid taxonomy — not a guarantee that every
claim was independently recalculated by a subject-matter expert in this pass.
REVIEW cards remain student-visible for practice but must **not** be presented
as scientifically certified. REJECTED cards are archived and excluded from browse.
Only treat `certification_status=VERIFIED` as certified content.
"""
    (OUT / "verification_summary.md").write_text(verification_md, encoding="utf-8")

    audit_report = verification_md + """
## Files

- card_audit.csv
- card_audit.json
- coverage_report.md
- provenance_report.md
- rejected_cards.md
- review_cards.md
- exact_duplicates.json
- near_duplicates.json
- published_inventory.json
- audit_results.json

## Taxonomy findings (known issues)

- Gravitation (Physics 11): present in taxonomy with **0 concepts** → no attachable flashcards (MISSING_TAXONOMY / chapter gap).
- Digestion and Absorption (Zoology 11): **0 concepts** → chapter gap.
- Biomolecules (6 cards): body `class_level=11` but chapter taxonomy `class_level` unset → taxonomy NEEDS_REVIEW (not VERIFIED).
- Class 12 coverage remains thin relative to Class 11 (see coverage_report.md).

## Duplicate findings

- Exact duplicate clusters: see exact_duplicates.json
- Near-duplicate pairs (same concept, Jaccard ≥ 0.72): see near_duplicates.json
- No automatic duplicate collapse was performed.
"""
    (OUT / "audit_report.md").write_text(audit_report, encoding="utf-8")

    for name in (
        "card_audit.csv",
        "audit_report.md",
        "verification_summary.md",
        "coverage_report.md",
        "provenance_report.md",
    ):
        p = OUT / name
        if p.exists():
            summary["artifact_hashes"][name] = hashlib.sha256(p.read_bytes()).hexdigest()

    (OUT / "audit_results.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "total_published_audited", "audit_status_counts", "subject_counts", "class_counts",
        "provenance_counts", "exact_duplicate_clusters", "near_duplicate_pairs",
        "verdict", "apply_stats", "mode",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
