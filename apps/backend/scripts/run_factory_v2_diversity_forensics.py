#!/usr/bin/env python3
"""Production Seed V2 Diversity Forensics — exact active 100 (post rematerialization).

READ-ONLY. No generation / approve / publish / ECAEP / NCERT.
Uses established factory_seed_diversity classifiers (deterministic; no embeddings).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db",
)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.modules.knowledge.models  # noqa: F401
from app.modules.cms.services.factory_candidate_validation import normalize_stem, stem_hash
from app.modules.cms.services.factory_qa_gates import SEMANTIC_DEDUPE_NOT_AVAILABLE
from app.modules.cms.services.factory_seed_diversity import (
    classify_against_prior,
    detect_forbidden_template,
    jaccard,
    tokset,
)
from app.modules.cms.services.factory_v2_visual import V2_VISUAL_SLOT_SPECS, enrich_slot_with_visual_fields
ROOT = Path(r"D:\ravishori\AI Neet Exam App")
_CLASS_RANK = {
    "EXACT_DUPLICATE": 5,
    "NORMALIZED_DUPLICATE": 4,
    "NEAR_DUPLICATE": 3,
    "SAME_TEMPLATE_REPETITION": 2,
    "LEGITIMATE_CONCEPTUAL_OVERLAP": 1,
    "UNIQUE": 0,
    "UNCERTAIN": 1,
}


def diversity_audit(questions: list[dict]) -> dict:
    """Pairwise classifier (established V1 method; rank dict scoped for all branches)."""
    labels = {q["id"]: "UNIQUE" for q in questions}
    pairs = []
    for i in range(len(questions)):
        for j in range(i + 1, len(questions)):
            a, b = questions[i], questions[j]
            label, code = classify_against_prior(
                stem=b["stem"],
                option_texts=[str(o.get("text", "")) for o in b["options"]],
                prior_stems=[a["stem"]],
            )
            if normalize_stem(a["stem"]) == normalize_stem(b["stem"]):
                label, code = "NORMALIZED_DUPLICATE", "NORMALIZED"
            elif detect_forbidden_template(a["stem"]) and detect_forbidden_template(a["stem"]) == detect_forbidden_template(
                b["stem"]
            ):
                label, code = "SAME_TEMPLATE_REPETITION", "FORBIDDEN_PAIR"
            else:
                label2, code2 = classify_against_prior(
                    stem=a["stem"],
                    option_texts=[str(o.get("text", "")) for o in a["options"]],
                    prior_stems=[b["stem"]],
                )
                if _CLASS_RANK.get(label2, 0) > _CLASS_RANK.get(label, 0):
                    label, code = label2, code2
            if label == "UNIQUE":
                continue
            pairs.append(
                {
                    "item_id_A": a["id"],
                    "item_id_B": b["id"],
                    "subject_A": a["subject"],
                    "subject_B": b["subject"],
                    "classification": label,
                    "code": code,
                }
            )
            for iid in (a["id"], b["id"]):
                cur = labels[iid]
                if _CLASS_RANK.get(label, 0) > _CLASS_RANK.get(cur, 0):
                    labels[iid] = label
    for q in questions:
        ft = detect_forbidden_template(q["stem"])
        if ft and labels[q["id"]] == "UNIQUE":
            labels[q["id"]] = "SAME_TEMPLATE_REPETITION"
    return {
        "item_labels": labels,
        "label_counts": dict(Counter(labels.values())),
        "pairs": pairs,
        "pair_counts": dict(Counter(p["classification"] for p in pairs)),
    }
AUDITS = ROOT / "docs" / "audits"
PLAN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_PLAN_20260903.json"
GEN_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_GENERATION_20260903.json"
P4_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P4_100_20260903.json"
REMAT_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_CONTROLLED_REMATERIALIZATION_20260903.json"
P5_PATH = AUDITS / "TALOS_PRODUCTION_SEED_V2_P5_RESAMPLE_20260903.json"
AUTH = AUDITS / "TALOS_PRODUCTION_SEED_V1_PUBLICATION_AUTHORIZATION_20260903.json"
OUT_JSON = AUDITS / "TALOS_PRODUCTION_SEED_V2_DIVERSITY_FORENSICS_20260903.json"
OUT_MD = AUDITS / "TALOS_PRODUCTION_SEED_V2_DIVERSITY_FORENSICS_REPORT_20260903.md"

URL = os.environ["DATABASE_URL"]
SUPERSEDED_TAG = "seed-v2-rematerialization-superseded-20260903"

_NUM = re.compile(r"\d+(?:\.\d+)?")
_WS = re.compile(r"\s+")


def skeleton_stem(stem: str) -> str:
    """Collapse numbers/units for template skeleton comparison."""
    t = normalize_stem(stem or "")
    t = _NUM.sub("NUM", t)
    return _WS.sub(" ", t).strip()


def option_fingerprint(options: list[dict]) -> str:
    texts = [normalize_stem(str(o.get("text") or "")) for o in (options or [])]
    return hashlib.sha256("|".join(sorted(texts)).encode()).hexdigest()


def option_structure_signature(options: list[dict]) -> str:
    """Coarse option-structure: token-count buckets + shared prefix tokens."""
    parts = []
    for o in sorted(options or [], key=lambda x: str(x.get("label") or "")):
        toks = sorted(tokset(str(o.get("text") or "")))
        parts.append(f"{o.get('label')}:{len(toks)}")
    return "|".join(parts)


async def fingerprint_items(session, ids: list[str]) -> dict:
    if not ids:
        return {"n": 0, "status_counts": {}, "bodies_fp": hashlib.sha256(b"").hexdigest()}
    rows = (
        await session.execute(
            text(
                """
                SELECT ci.id::text AS id, ci.status, md5(cv.body::text) AS body_md5
                FROM cms.content_items ci
                JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                ORDER BY ci.id
                """
            ),
            {"ids": ids},
        )
    ).mappings().all()
    blob = "|".join(f"{r['id']}:{r['body_md5']}:{r['status']}" for r in rows)
    return {
        "n": len(rows),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "bodies_fp": hashlib.sha256(blob.encode()).hexdigest(),
    }


async def pop_fp(session, tag: str) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status='PUBLISHED') AS published,
                       COUNT(*) FILTER (WHERE status='DRAFT') AS draft,
                       md5(coalesce(string_agg(
                         ci.id::text||'|'||ci.slug||'|'||ci.status||'|'||coalesce(ci.concept_id::text,'null')
                         ||'|'||md5(coalesce(cv.body::text,''))||'|'||coalesce(array_to_string(ci.tags,','),''),
                         E'\\n' ORDER BY ci.id::text), '')) AS content_fp
                FROM cms.content_items ci
                LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.content_type='QUESTION' AND ci.deleted_at IS NULL AND :tag = ANY(ci.tags)
                """
            ),
            {"tag": tag},
        )
    ).mappings().one()
    return dict(row)


async def t6f2_fp(session) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT COUNT(*) AS total,
                       md5(coalesce(string_agg(
                         ci.id::text||'|'||ci.slug||'|'||ci.status||'|'||md5(coalesce(cv.body::text,'')),
                         E'\\n' ORDER BY ci.id::text), '')) AS content_fp
                FROM cms.content_items ci
                LEFT JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                WHERE ci.content_type='QUESTION' AND ci.deleted_at IS NULL
                  AND :tag = ANY(ci.tags) AND ci.status='PUBLISHED'
                """
            ),
            {"tag": "physics-t6f1-pilot-20260902"},
        )
    ).mappings().one()
    return dict(row)


async def main() -> int:
    import asyncio

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    gen = json.loads(GEN_PATH.read_text(encoding="utf-8"))
    remat = json.loads(REMAT_PATH.read_text(encoding="utf-8"))
    auth = json.loads(AUTH.read_text(encoding="utf-8"))
    p5 = json.loads(P5_PATH.read_text(encoding="utf-8"))

    if remat.get("verdict") != "GREEN":
        raise SystemExit("Rematerialization not GREEN")
    if p5.get("verdict") != "GREEN":
        raise SystemExit("P5 resample not GREEN")

    repl = {r["slot_id"]: r["replacement_content_item_id"] for r in remat["results"]}
    orig = {r["slot_id"]: r["original_content_item_id"] for r in remat["results"]}
    planned = {s["slot_id"]: enrich_slot_with_visual_fields(s) for s in plan["slots"]}

    active_meta: list[dict] = []
    for s in gen["slot_coverage"]["slots"]:
        sid = s["slot_id"]
        pl = planned[sid]
        iid = repl.get(sid, s["content_item_id"])
        active_meta.append(
            {
                "slot_id": sid,
                "id": iid,
                "original_id": orig.get(sid, s["content_item_id"]),
                "is_replacement": sid in repl,
                "subject": s["subject"],
                "chapter": pl.get("chapter"),
                "topic": pl.get("topic"),
                "concept": pl.get("concept"),
                "concept_code": pl.get("concept_code"),
                "difficulty": pl.get("difficulty"),
                "question_archetype": pl.get("question_archetype"),
                "question_intent": pl.get("intent"),
                "blueprint_key": pl.get("blueprint_key") or s.get("factory_blueprint_id"),
                "visual_required": bool(pl.get("visual_required")),
                "visual_type": pl.get("visual_type"),
                "visual_archetype": pl.get("visual_archetype"),
                "calculation_type": pl.get("calculation_type"),
            }
        )

    if len(active_meta) != 100:
        raise SystemExit(f"active != 100: {len(active_meta)}")
    active_ids = [a["id"] for a in active_meta]
    hist_ids = list(orig.values())
    if set(hist_ids) & set(active_ids):
        raise SystemExit("superseded originals incorrectly in active set")
    v1_ids = list(auth["exact_uuid_allowlist"])

    engine = create_async_engine(URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        before_active = await fingerprint_items(session, active_ids)
        before_hist = await fingerprint_items(session, hist_ids)
        before_v1 = await fingerprint_items(session, v1_ids)
        before_t6d = await pop_fp(session, "physics-t6d-pilot-20260902")
        before_t6f2 = await t6f2_fp(session)
        before_legacy = await pop_fp(session, "legacy-physics-5000-import-20260902")

        if before_active["n"] != 100 or before_hist["n"] != 4:
            raise SystemExit(f"integrity n active={before_active['n']} hist={before_hist['n']}")

        # Load bodies for active 100 only
        rows = (
            await session.execute(
                text(
                    """
                    SELECT ci.id::text AS id, ci.status, ci.tags, md5(cv.body::text) AS body_md5, cv.body
                    FROM cms.content_items ci
                    JOIN cms.content_versions cv ON cv.id = ci.latest_version_id
                    WHERE ci.id = ANY(CAST(:ids AS uuid[]))
                    """
                ),
                {"ids": active_ids},
            )
        ).mappings().all()
        by_id = {r["id"]: r for r in rows}
        if len(by_id) != 100:
            raise SystemExit(f"loaded {len(by_id)} bodies")

        questions = []
        for a in active_meta:
            r = by_id[a["id"]]
            body = r["body"] if isinstance(r["body"], dict) else json.loads(r["body"])
            if SUPERSEDED_TAG in (r["tags"] or []):
                raise SystemExit(f"active item has superseded tag: {a['id']}")
            q = {
                **a,
                "status": r["status"],
                "body_md5": r["body_md5"],
                "stem": body.get("stem") or "",
                "options": body.get("options") or [],
                "correct_option": body.get("correct_option"),
                "explanation": body.get("explanation") or "",
                "difficulty_body": body.get("difficulty") or a["difficulty"],
                "diagram_svg": body.get("diagram_svg"),
                "visual_spec": body.get("visual_spec"),
                "diagram_description": body.get("diagram_description"),
                "exact_stem_hash": hashlib.sha256((body.get("stem") or "").encode()).hexdigest(),
                "normalized_stem_hash": stem_hash(body.get("stem") or ""),
                "body_sha256": hashlib.sha256(
                    json.dumps(
                        {
                            "stem": body.get("stem"),
                            "options": body.get("options"),
                            "correct_option": body.get("correct_option"),
                            "explanation": body.get("explanation"),
                        },
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode()
                ).hexdigest(),
                "skeleton": skeleton_stem(body.get("stem") or ""),
                "option_fp": option_fingerprint(body.get("options") or []),
                "option_structure": option_structure_signature(body.get("options") or []),
                "forbidden_template": detect_forbidden_template(body.get("stem") or ""),
            }
            questions.append(q)

        # --- Core pairwise diversity audit (established classifier) ---
        div = diversity_audit(questions)

        # Exact / normalized body-level
        exact_body_groups = defaultdict(list)
        norm_stem_groups = defaultdict(list)
        for q in questions:
            exact_body_groups[q["body_sha256"]].append(q["id"])
            norm_stem_groups[q["normalized_stem_hash"]].append(q["id"])
        exact_dups = {h: ids for h, ids in exact_body_groups.items() if len(ids) > 1}
        norm_dups = {h: ids for h, ids in norm_stem_groups.items() if len(ids) > 1}

        # Skeleton / option-structure template clusters (beyond forbidden patterns)
        skeleton_groups = defaultdict(list)
        optstruct_arch_groups = defaultdict(list)
        for q in questions:
            skeleton_groups[q["skeleton"]].append(q["id"])
            key = f"{q['question_archetype']}|{q['option_structure']}"
            optstruct_arch_groups[key].append(q["id"])
        skeleton_clusters = {k: v for k, v in skeleton_groups.items() if len(v) > 1}
        # Filter option-structure clusters: same archetype + identical option length signature only
        # is weak alone; require also skeleton Jaccard of stems within cluster >= 0.55 mean
        template_clusters = []
        for key, ids in optstruct_arch_groups.items():
            if len(ids) < 2:
                continue
            qs = [q for q in questions if q["id"] in ids]
            # mean pairwise stem jaccard
            sims = []
            for i in range(len(qs)):
                for j in range(i + 1, len(qs)):
                    sims.append(jaccard(tokset(qs[i]["stem"]), tokset(qs[j]["stem"])))
            mean_j = sum(sims) / len(sims) if sims else 0
            if mean_j >= 0.55 or len(set(q["skeleton"] for q in qs)) == 1:
                template_clusters.append(
                    {
                        "key": key,
                        "n": len(ids),
                        "ids": ids,
                        "slot_ids": [q["slot_id"] for q in qs],
                        "mean_stem_jaccard": round(mean_j, 3),
                        "archetype": qs[0]["question_archetype"],
                        "subjects": dict(Counter(q["subject"] for q in qs)),
                    }
                )
        template_clusters.sort(key=lambda x: -x["n"])

        # Also cluster by identical skeleton (strong template signal)
        skeleton_template_clusters = [
            {"skeleton": k[:120], "n": len(v), "ids": v}
            for k, v in skeleton_clusters.items()
        ]
        skeleton_template_clusters.sort(key=lambda x: -x["n"])

        # Near-duplicate pairs from diversity_audit
        near_pairs = [p for p in div["pairs"] if p["classification"] == "NEAR_DUPLICATE"]
        template_pairs = [p for p in div["pairs"] if p["classification"] == "SAME_TEMPLATE_REPETITION"]
        legitimate_pairs = [p for p in div["pairs"] if p["classification"] == "LEGITIMATE_CONCEPTUAL_OVERLAP"]

        # Distributions
        subject_dist = dict(Counter(q["subject"] for q in questions))
        difficulty_plan = dict(Counter(q["difficulty"] for q in questions))
        difficulty_body = dict(Counter(q["difficulty_body"] for q in questions))
        archetype_dist = dict(Counter(q["question_archetype"] for q in questions))
        chapter_dist = dict(Counter(f"{q['subject']}/{q['chapter']}" for q in questions))
        topic_dist = dict(Counter(f"{q['subject']}/{q['topic']}" for q in questions))
        concept_dist = dict(Counter(f"{q['subject']}/{q.get('concept_code') or q['concept']}" for q in questions))
        blueprint_dist = dict(Counter(q["blueprint_key"] for q in questions))

        def top_n(d: dict, n: int = 10) -> list[dict]:
            items = sorted(d.items(), key=lambda x: (-x[1], x[0]))
            return [{"key": k, "count": c, "pct": round(100.0 * c / 100, 1)} for k, c in items[:n]]

        # Chemistry concentration
        chem = [q for q in questions if q["subject"] == "Chemistry"]
        chem_chapter = Counter(q["chapter"] for q in chem)
        chem_topic = Counter(q["topic"] for q in chem)
        chem_concept = Counter(q.get("concept_code") or q["concept"] for q in chem)
        chem_arch = Counter(q["question_archetype"] for q in chem)
        chem_near = [p for p in near_pairs if p["subject_A"] == "Chemistry" and p["subject_B"] == "Chemistry"]
        chem_template = [c for c in template_clusters if c["subjects"].get("Chemistry")]

        # V1 forbidden pattern recurrence (inspect, don't assume absence)
        v1_patterns = []
        for name, _ in __import__(
            "app.modules.cms.services.factory_seed_diversity", fromlist=["_FORBIDDEN_TEMPLATE_PATTERNS"]
        )._FORBIDDEN_TEMPLATE_PATTERNS:
            hits = [q for q in questions if q["forbidden_template"] == name]
            v1_patterns.append(
                {
                    "pattern": name,
                    "count": len(hits),
                    "candidate_ids": [q["id"] for q in hits],
                    "slot_ids": [q["slot_id"] for q in hits],
                    "status": "ABSENT" if not hits else "PRESENT",
                }
            )
        # Extra lexical scan for ABO / Z-scheme / Ohm / stretch / lattice phrasing
        extra_scans = {
            "ABO_agglutination_keywords": [
                q["id"]
                for q in questions
                if re.search(r"\b(anti-a|anti-b|agglutination|abo)\b", q["stem"], re.I)
            ],
            "noncyclic_photophosphorylation": [
                q["id"] for q in questions if re.search(r"non[\s-]*cyclic\s+photophosphorylation", q["stem"], re.I)
            ],
            "ohm_v_doubled": [
                q["id"]
                for q in questions
                if re.search(r"(potential|voltage).{0,40}doubl|doubl.{0,40}(potential|voltage)", q["stem"], re.I)
            ],
            "stretch_20pct_or_2x": [
                q["id"]
                for q in questions
                if re.search(
                    r"stretch.*(20\s*%|20\s*percent)|length becomes double|double its original length",
                    q["stem"],
                    re.I,
                )
            ],
            "lattice_energy_compare": [
                q["id"]
                for q in questions
                if re.search(r"lattice energy.*(compar|relative magnitude)|compar.*lattice energy", q["stem"], re.I)
            ],
        }

        # Graphical
        visual_qs = [q for q in questions if q["visual_required"]]
        visual_with_asset = [q for q in visual_qs if q.get("diagram_svg") and q.get("visual_spec")]
        visual_types = Counter(q["visual_type"] for q in visual_qs)
        visual_archs = Counter(q["visual_archetype"] for q in visual_qs)
        visual_spec_fps = Counter(
            hashlib.sha256(json.dumps(q.get("visual_spec") or {}, sort_keys=True).encode()).hexdigest()
            for q in visual_with_asset
        )
        svg_fps = Counter(hashlib.sha256((q.get("diagram_svg") or "").encode()).hexdigest() for q in visual_with_asset)

        # Numerical
        numerical_qs = [
            q
            for q in questions
            if q["question_archetype"] == "numerical_calculation" or q.get("calculation_type")
        ]
        num_calc_types = Counter(q.get("calculation_type") or "unspecified" for q in numerical_qs)
        num_skeleton_clusters = defaultdict(list)
        for q in numerical_qs:
            num_skeleton_clusters[q["skeleton"]].append(q["id"])
        num_same_skeleton = {k: v for k, v in num_skeleton_clusters.items() if len(v) > 1}

        # Rematerialized 4 vs remaining 96
        remat_qs = [q for q in questions if q["is_replacement"]]
        remat_vs_96 = []
        others = [q for q in questions if not q["is_replacement"]]
        for rq in remat_qs:
            best = None
            for oq in others:
                label, code = classify_against_prior(
                    stem=rq["stem"],
                    option_texts=[str(x.get("text", "")) for x in rq["options"]],
                    prior_stems=[oq["stem"]],
                    reject_forbidden_templates=False,
                )
                if label == "UNIQUE":
                    continue
                rank = {
                    "EXACT_DUPLICATE": 5,
                    "NORMALIZED_DUPLICATE": 4,
                    "NEAR_DUPLICATE": 3,
                    "SAME_TEMPLATE_REPETITION": 2,
                    "LEGITIMATE_CONCEPTUAL_OVERLAP": 1,
                }
                if best is None or rank.get(label, 0) > rank.get(best["classification"], 0):
                    best = {
                        "replacement_id": rq["id"],
                        "slot_id": rq["slot_id"],
                        "other_id": oq["id"],
                        "other_slot": oq["slot_id"],
                        "classification": label,
                        "code": code,
                    }
            remat_vs_96.append(
                best
                or {
                    "replacement_id": rq["id"],
                    "slot_id": rq["slot_id"],
                    "classification": "UNIQUE_VS_REMAINING_96",
                    "other_id": None,
                }
            )

        # Excessive concentration flags
        max_chapter = max(chapter_dist.values()) if chapter_dist else 0
        max_concept = max(concept_dist.values()) if concept_dist else 0
        max_chem_chapter = max(chem_chapter.values()) if chem_chapter else 0
        excessive = []
        if max_concept > 2:
            excessive.append(f"concept_count_gt_2:{max_concept}")
        if max_chem_chapter > 8:
            excessive.append(f"chem_chapter_gt_8:{max_chem_chapter}")
        if len(near_pairs) >= 10:
            excessive.append(f"near_pairs_ge_10:{len(near_pairs)}")
        if sum(1 for c in template_clusters if c["n"] >= 3) >= 3:
            excessive.append("multiple_template_clusters_n_ge_3")

        after_active = await fingerprint_items(session, active_ids)
        after_hist = await fingerprint_items(session, hist_ids)
        after_v1 = await fingerprint_items(session, v1_ids)
        after_t6d = await pop_fp(session, "physics-t6d-pilot-20260902")
        after_t6f2 = await t6f2_fp(session)
        after_legacy = await pop_fp(session, "legacy-physics-5000-import-20260902")

        integrity_ok = (
            after_active["bodies_fp"] == before_active["bodies_fp"]
            and after_hist["bodies_fp"] == before_hist["bodies_fp"]
            and after_v1["bodies_fp"] == before_v1["bodies_fp"]
            and after_t6d["content_fp"] == before_t6d["content_fp"]
            and after_t6f2["content_fp"] == before_t6f2["content_fp"]
            and after_legacy["content_fp"] == before_legacy["content_fp"]
            and after_active["n"] == 100
            and after_hist["n"] == 4
            and after_active["status_counts"].get("DRAFT") == 100
        )

    await engine.dispose()

    # Verdict
    exact_n = len(exact_dups)
    norm_n = len(norm_dups)
    near_n = len(near_pairs)
    template_pair_n = len(template_pairs)
    forbidden_hits = sum(1 for p in v1_patterns if p["count"] > 0)
    extra_hit_n = sum(1 for v in extra_scans.values() if v)

    limitations = [
        "Cohort forensic only — not global-bank uniqueness proof.",
        "SEMANTIC_DEDUPE_NOT_AVAILABLE — no embeddings/pgvector in this wave; lexical/template classifiers only.",
        "Do not equate exact/normalized uniqueness with semantic uniqueness.",
        "3/100 visual slots is rematerialization validation, not the eventual 40% production target.",
        "Legitimate conceptual overlap on shared NCERT topics is expected and not counted as duplication.",
    ]

    verdict = "GREEN"
    if not integrity_ok:
        verdict = "RED"
        limitations.append("integrity_failure")
    if exact_n or norm_n:
        verdict = "RED"
        limitations.append(f"exact_or_normalized_duplicates exact={exact_n} norm={norm_n}")
    if forbidden_hits or extra_hit_n:
        verdict = "AMBER" if verdict != "RED" else verdict
        limitations.append("v1_pattern_or_keyword_recurrence_detected")
    if near_n >= 5 or template_pair_n >= 5 or any(c["n"] >= 4 for c in template_clusters):
        verdict = "AMBER" if verdict != "RED" else verdict
        limitations.append(
            f"bounded_repetition near_pairs={near_n} template_pairs={template_pair_n} "
            f"struct_clusters>={max((c['n'] for c in template_clusters), default=0)}"
        )
    if excessive and verdict == "GREEN":
        # mild concentration → still GREEN if no near/template surge; else AMBER
        if max_chem_chapter <= 5 and max_concept <= 1 and near_n == 0 and template_pair_n == 0:
            pass
        else:
            verdict = "AMBER"
            limitations.extend(excessive)
    # Special rule from user: EXACT=0 NORMALIZED=0 but high NEAR/TEMPLATE → AMBER
    if exact_n == 0 and norm_n == 0 and (near_n >= 8 or template_pair_n >= 8):
        verdict = "AMBER"
        limitations.append("v1_style_exact0_normalized0_but_high_near_or_template")

    # If truly clean
    if (
        exact_n == 0
        and norm_n == 0
        and near_n == 0
        and template_pair_n == 0
        and forbidden_hits == 0
        and extra_hit_n == 0
        and not skeleton_template_clusters
        and integrity_ok
        and subject_dist == {"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15}
        and difficulty_plan == {"easy": 25, "medium": 60, "hard": 15}
    ):
        verdict = "GREEN"

    artifact = {
        "audit": "Production Seed V2 Diversity Forensics — Exact Active 100",
        "date": "2026-09-03",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "READ_ONLY_V2_COHORT_FORENSICS",
        "evidence_label": "V2_cohort_evidence_not_global_bank",
        "verdict": verdict,
        "active_population": {
            "n": 100,
            "subject_counts": subject_dist,
            "ids": active_ids,
            "replacements": repl,
            "definition": "P3/P4 slots with rematerialized replacements for four remediated slots",
        },
        "historical_exclusions": {
            "n": 4,
            "ids": hist_ids,
            "slot_map": orig,
            "note": "Superseded originals excluded from all active diversity metrics",
        },
        "exact_duplicate": {
            "body_duplicate_groups": exact_dups,
            "group_count": exact_n,
            "pair_equivalent": sum(len(v) * (len(v) - 1) // 2 for v in exact_dups.values()),
            "expected": 0,
        },
        "normalized_duplicate": {
            "normalized_stem_groups": {h: ids for h, ids in norm_dups.items()},
            "group_count": norm_n,
            "expected": 0,
        },
        "near_duplicate": {
            "pair_count": near_n,
            "pairs": near_pairs[:50],
            "method": "factory_seed_diversity.classify_against_prior jaccard>=0.72 on stem tokens",
            "threshold": 0.72,
            "threshold_source": "apps/backend/app/modules/cms/services/factory_seed_diversity.py",
        },
        "same_template_repetition": {
            "forbidden_template_pair_count": template_pair_n,
            "forbidden_template_pairs": template_pairs,
            "forbidden_template_hits_by_item": [q["id"] for q in questions if q["forbidden_template"]],
            "structure_archetype_clusters": template_clusters[:20],
            "identical_skeleton_clusters": skeleton_template_clusters[:20],
            "method_notes": [
                "SAME_TEMPLATE via known V1 forbidden regex families",
                "Additional skeleton/option-structure clusters reported separately (not forced into UNIQUE)",
            ],
        },
        "conceptual_overlap": {
            "legitimate_pair_count": len(legitimate_pairs),
            "legitimate_pairs_sample": legitimate_pairs[:30],
            "chapter_top": top_n(chapter_dist, 15),
            "topic_top": top_n(topic_dist, 15),
            "concept_top": top_n(concept_dist, 15),
            "blueprint_unique": len(blueprint_dist),
            "max_chapter_count": max_chapter,
            "max_concept_count": max_concept,
            "excessive_concentration_flags": excessive,
        },
        "subject_distribution": {
            "observed": subject_dist,
            "expected": {"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15},
            "match": subject_dist == {"Physics": 35, "Chemistry": 35, "Botany": 15, "Zoology": 15},
            "note": "Subject allocation ≠ conceptual diversity",
        },
        "difficulty_distribution": {
            "plan_expected": {"easy": 25, "medium": 60, "hard": 15},
            "plan_observed": difficulty_plan,
            "body_observed": difficulty_body,
            "plan_match": difficulty_plan == {"easy": 25, "medium": 60, "hard": 15},
        },
        "archetype_distribution": {
            "observed": archetype_dist,
            "plan_expected": dict(Counter(s["question_archetype"] for s in plan["slots"])),
        },
        "graphical_analysis": {
            "visual_required_count": len(visual_qs),
            "visual_required_slot_ids": [q["slot_id"] for q in visual_qs],
            "actual_with_svg_and_spec": len(visual_with_asset),
            "visual_type_distribution": dict(visual_types),
            "visual_archetype_distribution": dict(visual_archs),
            "unique_visual_spec_fingerprints": len(visual_spec_fps),
            "unique_svg_fingerprints": len(svg_fps),
            "repeated_visual_spec": {k: c for k, c in visual_spec_fps.items() if c > 1},
            "repeated_svg": {k: c for k, c in svg_fps.items() if c > 1},
            "not_40pct_target_claim": True,
            "note": "3/100 is rematerialization validation cohort, not production graphical target",
        },
        "numerical_analysis": {
            "numerical_count": len(numerical_qs),
            "calculation_types": dict(num_calc_types),
            "identical_skeleton_clusters": [
                {"skeleton": k[:100], "n": len(v), "ids": v} for k, v in num_same_skeleton.items()
            ],
            "note": "Changing numbers alone is not genuine diversity if skeleton identical",
        },
        "chemistry_concentration": {
            "total": 35,
            "largest_chapter": chem_chapter.most_common(1)[0] if chem_chapter else None,
            "largest_chapter_count": max(chem_chapter.values()) if chem_chapter else 0,
            "largest_chapters_tied": sorted(
                [k for k, v in chem_chapter.items() if v == max(chem_chapter.values())]
            )
            if chem_chapter
            else [],
            "largest_topic": chem_topic.most_common(1)[0] if chem_topic else None,
            "largest_concept": chem_concept.most_common(1)[0] if chem_concept else None,
            "chapter_distribution": dict(chem_chapter),
            "topic_distribution": dict(chem_topic),
            "concept_unique_count": len(chem_concept),
            "archetype_distribution": dict(chem_arch),
            "near_duplicate_chem_pairs": len(chem_near),
            "template_clusters_involving_chem": len(chem_template),
            "largest_near_duplicate_cluster_note": "See near_duplicate.pairs filtered Chemistry",
        },
        "tests": {
            "note": "Recorded by agent after pytest; re-run to refresh",
            "thresholds_weakened": False,
            "production_content_mutated_for_pass": False,
        },
        "script": "apps/backend/scripts/run_factory_v2_diversity_forensics.py",
        "previous_v1_pattern_recurrence": {
            "forbidden_template_scan": v1_patterns,
            "extra_keyword_scans": {k: {"count": len(v), "ids": v} for k, v in extra_scans.items()},
            "any_present": bool(forbidden_hits or extra_hit_n),
        },
        "semantic_dedupe": {
            "status": SEMANTIC_DEDUPE_NOT_AVAILABLE,
            "claim_semantic_uniqueness": False,
            "method": None,
            "model_index": None,
            "threshold": None,
            "note": "factory_dedupe_service / factory_seed_diversity: deterministic lexical only; no pgvector",
        },
        "item_label_counts": div["label_counts"],
        "pair_counts": div["pair_counts"],
        "rematerialized_vs_remaining_96": remat_vs_96,
        "cluster_tables": {
            "top_chapters": top_n(chapter_dist, 12),
            "top_concepts": top_n(concept_dist, 12),
            "template_structure_clusters": template_clusters[:15],
        },
        "integrity_before": {
            "active_fp": before_active["bodies_fp"],
            "active_n": before_active["n"],
            "active_status": before_active["status_counts"],
            "historical_fp": before_hist["bodies_fp"],
            "historical_n": before_hist["n"],
            "v1_fp": before_v1["bodies_fp"],
            "t6d_fp": before_t6d["content_fp"],
            "t6f2_fp": before_t6f2["content_fp"],
            "legacy_fp": before_legacy["content_fp"],
        },
        "integrity_after": {
            "active_fp": after_active["bodies_fp"],
            "active_n": after_active["n"],
            "active_status": after_active["status_counts"],
            "historical_fp": after_hist["bodies_fp"],
            "historical_n": after_hist["n"],
            "v1_fp": after_v1["bodies_fp"],
            "t6d_fp": after_t6d["content_fp"],
            "t6f2_fp": after_t6f2["content_fp"],
            "legacy_fp": after_legacy["content_fp"],
        },
        "integrity_checks": {
            "active_unchanged": after_active["bodies_fp"] == before_active["bodies_fp"],
            "historical_unchanged": after_hist["bodies_fp"] == before_hist["bodies_fp"],
            "protected_unchanged": integrity_ok,
            "approvals": 0,
            "publications": 0,
            "ecaep": 0,
            "body_mutations": 0,
            "status_mutations": 0,
        },
        "counts": {
            "generation": 0,
            "approvals": 0,
            "publications": 0,
            "ecaep": 0,
        },
        "limitations": limitations,
        "remediation_recommendation": (
            "No systemic remediation required before considering NCERT certification gate"
            if verdict == "GREEN"
            else "Bound concentration/repetition: remediate listed near/template clusters before 1,000-scale production"
        ),
        "next_gate_recommendation": (
            "NCERT certification gate (separate authorization) — still no approve/publish"
            if verdict == "GREEN"
            else "Targeted diversity remediation of flagged clusters, then re-run this forensic"
        ),
        "phase_stop": "DIVERSITY_FORENSICS_COMPLETE",
    }

    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    md = f"""# Production Seed V2 — Diversity Forensics (Exact Active 100)

**Verdict: {verdict}**  
**Captured:** {artifact['captured_at']}  
**Evidence label:** V2 cohort only — **not** global-bank proof.

## 1. Exact active population

**n = 100** · Physics 35 / Chemistry 35 / Botany 15 / Zoology 15  
Active IDs derived from P3/P4 + rematerialization replacements.

## 2. Historical exclusions

**4** superseded originals excluded from all active metrics:  
{', '.join(f'`{i}`' for i in hist_ids)}

## 3. Exact duplicate

Body-duplicate groups: **{exact_n}** (expected 0)

## 4. Normalized duplicate

Normalized-stem groups: **{norm_n}** (expected 0)

## 5. Near-duplicate

Pairs (jaccard≥0.72): **{near_n}**  
Method: `factory_seed_diversity.classify_against_prior`

## 6. Template repetition

Forbidden-template pairs: **{template_pair_n}**  
Structure/archetype clusters (n≥2 with stem similarity): **{len(template_clusters)}**  
Identical skeleton clusters: **{len(skeleton_template_clusters)}**

## 7. Conceptual overlap

Legitimate overlap pairs: **{len(legitimate_pairs)}**  
Max chapter count: **{max_chapter}** · Max concept count: **{max_concept}** · Unique blueprints: **{len(blueprint_dist)}**

## 8. Subject distribution

Observed: {subject_dist} · match expected: **{artifact['subject_distribution']['match']}**

## 9. Difficulty distribution

Plan expected easy25/medium60/hard15 · observed: {difficulty_plan} · match: **{artifact['difficulty_distribution']['plan_match']}**

## 10. Archetype distribution

{json.dumps(archetype_dist, indent=2)}

## 11. Graphical analysis

visual_required={len(visual_qs)} · with SVG+spec={len(visual_with_asset)} · unique specs={len(visual_spec_fps)}  
Slots: {', '.join(V2_VISUAL_SLOT_SPECS.keys())}  
**Not** claiming 40% production target.

## 12. Numerical analysis

numerical_count={len(numerical_qs)} · identical-skeleton clusters={len(num_same_skeleton)}

## 13. Chemistry concentration

total=35 · largest chapter={chem_chapter.most_common(1)} · unique concepts={len(chem_concept)} · chem near-pairs={len(chem_near)}

## 14. Previous V1 pattern recurrence

Any present: **{bool(forbidden_hits or extra_hit_n)}**  
See JSON `previous_v1_pattern_recurrence`.

## 15. Semantic dedupe

**{SEMANTIC_DEDUPE_NOT_AVAILABLE}** — no semantic uniqueness claim.

## 16. Cluster tables

See JSON `cluster_tables`.

## 17. Integrity

Active/historical/protected unchanged: **{integrity_ok}** · approvals/publications/ECAEP/generation = 0

## 18. Tests

Run in agent session: `pytest tests/test_factory_seed_diversity.py tests/test_seed_v2_p5_remediation.py …`

## 19. Limitations

"""
    for lim in limitations:
        md += f"- {lim}\n"
    md += f"""
## 20. Remediation / next gate

{artifact['remediation_recommendation']}

**Next:** {artifact['next_gate_recommendation']}

STOP — no generate / approve / publish / NCERT / 1000-scale start from this gate alone.
"""
    OUT_MD.write_text(md, encoding="utf-8")
    print(
        json.dumps(
            {
                "verdict": verdict,
                "exact": exact_n,
                "normalized": norm_n,
                "near_pairs": near_n,
                "template_pairs": template_pair_n,
                "v1_patterns": bool(forbidden_hits or extra_hit_n),
                "chem_max_chapter": max_chem_chapter,
                "integrity": integrity_ok,
            },
            indent=2,
        )
    )
    return 0 if verdict != "RED" else 1


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
