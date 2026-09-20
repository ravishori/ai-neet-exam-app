"""Mode-A DRAFT acquisition: Gemini JSONL batch for Physics 11 Ch2.

Does NOT publish / approve / mutate CMS. Writes questions.jsonl + manifest.json only.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent.parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from app.core.config import get_settings
from app.modules.ai.gateway.base import GenerateRequest, ProviderError
from app.modules.ai.gateway.gemini_provider import GeminiProvider

BATCH_ID = "20260911-PHY11-CH02-B001"
SOURCE_FILE = "ncert-books-class-11-physics-chapter-2.pdf"
PDF_PATH = REPO / "StudyMaterial" / "Physics" / "Class 11-Physics" / SOURCE_FILE
OUT_DIR = REPO / "docs" / "acquisition" / "batches" / f"NEET_GEMINI_{BATCH_ID}"
TARGET = 25
CHUNK = 5
CHAPTER = "Motion in a Straight Line"
SUBJECT = "Physics"
CLASS_LEVEL = "11"


SYSTEM = """You are a NEET MCQ acquisition engine. Use ONLY the provided NCERT excerpt.
Do not invent facts, page numbers, or quotations not supported by the excerpt.
You are NOT a publication authority. Output DRAFT acquisition JSON only.
Never claim NCERT verified, scientifically verified, expert approved, or publication ready.
Return a JSON object: {"questions":[...]} with exactly the requested count.
Each question must match this schema exactly:
{
  "external_question_id": "GEMINI-BATCH-NNNNNN",
  "subject": "Physics",
  "class_level": "11",
  "chapter": "Motion in a Straight Line",
  "topic": "...",
  "concept": "...",
  "question_type": "conceptual" | "numerical",
  "difficulty": "easy" | "medium" | "hard",
  "stem": "...",
  "options": {"A":"...","B":"...","C":"...","D":"..."},
  "correct_option": "A"|"B"|"C"|"D",
  "explanation": "...",
  "source": {
    "source_file": "ncert-books-class-11-physics-chapter-2.pdf",
    "chapter": "Motion in a Straight Line",
    "section": "...",
    "page_number": null,
    "source_evidence": "..."
  },
  "provenance": {
    "provider": "gemini",
    "generation_source": "attached_ncert_pdf",
    "generation_batch_id": "20260911-PHY11-CH02-B001"
  },
  "visual": {"visual_required": false, "visual_type": null, "visual_description": null},
  "numerical": {"is_numerical": false, "calculation_check": null},
  "tags": []
}
Rules:
- Exactly four unique options; exactly one correct answer; no all/none of the above.
- page_number must be null unless the printed page is explicitly present in the excerpt label.
- For numerical questions set question_type numerical, is_numerical true, and fill calculation_check.
- Vary structures; avoid near-duplicates.
- Taxonomy text only; never invent database UUIDs.
"""


def extract_pdf_text(path: Path) -> str:
    import fitz

    doc = fitz.open(path)
    parts: list[str] = []
    for i in range(doc.page_count):
        text = doc.load_page(i).get_text("text")
        parts.append(f"\n----- PDF_PAGE_INDEX={i + 1} (not necessarily NCERT printed page) -----\n{text}")
    doc.close()
    return "\n".join(parts)


def validate_q(q: dict, *, seq: int) -> dict | None:
    required = [
        "subject",
        "class_level",
        "chapter",
        "topic",
        "concept",
        "question_type",
        "difficulty",
        "stem",
        "options",
        "correct_option",
        "explanation",
        "source",
        "provenance",
        "visual",
        "numerical",
    ]
    if not isinstance(q, dict) or any(k not in q for k in required):
        return None
    opts = q.get("options")
    if not isinstance(opts, dict) or set(opts.keys()) != {"A", "B", "C", "D"}:
        return None
    texts = [str(opts[k]).strip() for k in "ABCD"]
    if any(not t for t in texts) or len(set(t.lower() for t in texts)) != 4:
        return None
    if q.get("correct_option") not in {"A", "B", "C", "D"}:
        return None
    if not str(q.get("stem", "")).strip() or not str(q.get("explanation", "")).strip():
        return None
    if q.get("difficulty") not in {"easy", "medium", "hard"}:
        return None
    src = q.get("source") or {}
    if not isinstance(src, dict) or not str(src.get("source_evidence", "")).strip():
        return None
    # Never trust model-claimed verification fields; force safe provenance.
    q["external_question_id"] = f"GEMINI-{BATCH_ID}-{seq:06d}"
    q["subject"] = SUBJECT
    q["class_level"] = CLASS_LEVEL
    q["chapter"] = CHAPTER
    q["source"] = {
        "source_file": SOURCE_FILE,
        "chapter": CHAPTER,
        "section": src.get("section") or "",
        "page_number": None,  # PDF index ≠ printed page; do not invent
        "source_evidence": str(src.get("source_evidence", "")).strip()[:1200],
    }
    q["provenance"] = {
        "provider": "gemini",
        "generation_source": "attached_ncert_pdf",
        "generation_batch_id": BATCH_ID,
        "model": get_settings().gemini_model,
    }
    q.setdefault("tags", [])
    q["tags"] = list(q["tags"]) + ["acquisition", "draft_only", "unverified", BATCH_ID]
    # Strip forbidden claim language from explanation if present
    bad = re.compile(
        r"\b(ncert\s+verified|scientifically\s+verified|expert\s+approved|publication\s+ready|student\s+ready)\b",
        re.I,
    )
    q["explanation"] = bad.sub("NCERT-supported (unverified acquisition)", str(q["explanation"]))
    return q


def parse_questions(text: str) -> list[dict]:
    data = json.loads(text)
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        qs = data.get("questions")
        if isinstance(qs, list):
            return [x for x in qs if isinstance(x, dict)]
        # single question object
        if "stem" in data:
            return [data]
    return []


async def gen_chunk(
    provider: GeminiProvider,
    *,
    ncert: str,
    start_seq: int,
    count: int,
    avoid_stems: list[str],
) -> tuple[list[dict], dict]:
    avoid = "\n".join(f"- {s[:160]}" for s in avoid_stems[-40:]) or "(none yet)"
    user = f"""BATCH_ID={BATCH_ID}
Generate exactly {count} original NEET-style MCQs from the NCERT excerpt below.
Assign external_question_id as GEMINI-{BATCH_ID}-{(start_seq):06d} onward sequentially.
Aim difficulty mix roughly easy/medium/hard within this chunk when possible.
Do NOT repeat or paraphrase these prior stems:
{avoid}

NCERT EXCERPT (Physics Class 11, Chapter 2 — Motion in a Straight Line):
{ncert}
"""
    req = GenerateRequest(
        system_prompt=SYSTEM,
        user_prompt=user,
        max_tokens=8192,
        model=get_settings().gemini_model,
        temperature=0.4,
        require_json=True,
    )
    resp = await provider.generate_request(req)
    raw = parse_questions(resp.text)
    out: list[dict] = []
    seq = start_seq
    for item in raw:
        fixed = validate_q(item, seq=seq)
        if fixed is None:
            continue
        out.append(fixed)
        seq += 1
        if len(out) >= count:
            break
    meta = {
        "prompt_tokens": resp.prompt_tokens,
        "completion_tokens": resp.completion_tokens,
        "model": resp.model,
        "finish_reason": resp.finish_reason,
        "accepted": len(out),
        "raw_count": len(raw),
    }
    return out, meta


async def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    if not settings.gemini_enabled or not (settings.gemini_api_key or "").strip():
        raise SystemExit("Gemini not enabled or API key missing")
    if not PDF_PATH.is_file():
        raise SystemExit(f"Missing PDF: {PDF_PATH}")

    ncert = extract_pdf_text(PDF_PATH)
    # Cap prompt size while keeping chapter body (drop exercises-heavy tail if huge)
    if len(ncert) > 90000:
        ncert = ncert[:90000]

    provider = GeminiProvider(settings.gemini_api_key, settings.gemini_model, timeout=180.0)
    collected: list[dict] = []
    chunk_logs: list[dict] = []
    stems: list[str] = []
    attempts = 0
    max_attempts = 12

    while len(collected) < TARGET and attempts < max_attempts:
        attempts += 1
        need = min(CHUNK, TARGET - len(collected))
        try:
            got, meta = await gen_chunk(
                provider,
                ncert=ncert,
                start_seq=len(collected) + 1,
                count=need,
                avoid_stems=stems,
            )
        except ProviderError as exc:
            chunk_logs.append({"attempt": attempts, "error": f"{exc.code}:{exc}", "retryable": exc.retryable})
            if not exc.retryable:
                break
            await asyncio.sleep(2)
            continue
        except Exception as exc:  # noqa: BLE001
            chunk_logs.append({"attempt": attempts, "error": type(exc).__name__ + ":" + str(exc)[:300]})
            await asyncio.sleep(2)
            continue

        # Dedupe by normalized stem within batch
        for q in got:
            stem_key = re.sub(r"\s+", " ", q["stem"].strip().lower())
            if stem_key in {re.sub(r"\s+", " ", s.strip().lower()) for s in stems}:
                continue
            # renumber at append time
            q["external_question_id"] = f"GEMINI-{BATCH_ID}-{len(collected) + 1:06d}"
            collected.append(q)
            stems.append(q["stem"])
            if len(collected) >= TARGET:
                break
        chunk_logs.append({"attempt": attempts, **meta, "batch_size": len(collected)})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUT_DIR / "questions.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for q in collected:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    status = "COMPLETE" if len(collected) == TARGET else "PARTIAL"
    manifest = {
        "batch_id": BATCH_ID,
        "provider": "gemini",
        "model": settings.gemini_model,
        "mode": "A",
        "source_files": [SOURCE_FILE],
        "subject": SUBJECT,
        "class_level": CLASS_LEVEL,
        "chapter": CHAPTER,
        "requested_count": TARGET,
        "generated_count": len(collected),
        "generation_status": status,
        "format": "JSONL",
        "validation_status": "UNVERIFIED",
        "publication_status": "DRAFT_ONLY",
        "notes": [
            "Acquisition only — not ECAEP approved/published.",
            "page_number forced null (PDF index ≠ printed NCERT page).",
            "Local structural checks only; no scientific/NCERT certification claimed.",
        ],
        "chunk_logs": chunk_logs,
        "output_dir": str(OUT_DIR),
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": "GREEN" if status == "COMPLETE" else "AMBER", "manifest": manifest}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
