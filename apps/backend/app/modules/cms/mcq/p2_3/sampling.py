"""P2.3 stratified human gold sample."""

from __future__ import annotations

import csv
import random
from pathlib import Path

from app.modules.cms.mcq.p2_3.schemas import McqRecord

GOLD_SAMPLE_SIZE = 100
GOLD_SEED = 20260903


def select_gold_sample(records: list[McqRecord], *, seed: int = GOLD_SEED, target: int = GOLD_SAMPLE_SIZE) -> list[McqRecord]:
    rng = random.Random(seed)
    buckets: dict[str, list[McqRecord]] = {}
    for rec in records:
        if rec.generation_status != "GENERATED" or rec.qa_status != "PASS":
            continue
        key = f"{rec.subject}:{rec.class_level}:{rec.difficulty}:{rec.question_type}:{rec.generation_provider}:{rec.validation_status}"
        buckets.setdefault(key, []).append(rec)
    selected: list[McqRecord] = []
    keys = list(buckets.keys())
    rng.shuffle(keys)
    per = max(1, target // max(len(keys), 1))
    for key in keys:
        pool = buckets[key][:]
        rng.shuffle(pool)
        selected.extend(pool[:per])
    remaining = [r for r in records if r not in selected and r.generation_status == "GENERATED"]
    rng.shuffle(remaining)
    while len(selected) < target and remaining:
        selected.append(remaining.pop())
    for rec in selected:
        rec.human_review_status = "SAMPLED"
    return selected[:target]


def write_human_gold_csv(path: Path, sample: list[McqRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "question_id",
                "subject",
                "class",
                "chapter",
                "topic",
                "provider",
                "difficulty",
                "question_type",
                "question",
                "option_A",
                "option_B",
                "option_C",
                "option_D",
                "proposed_answer",
                "NCERT_source",
                "validator_verdict",
                "human_stem",
                "human_option_A",
                "human_option_B",
                "human_option_C",
                "human_option_D",
                "human_answer",
                "human_explanation",
                "human_ncert_support",
                "human_ambiguity",
                "human_duplicate",
                "human_difficulty",
                "human_neet_suitability",
                "human_overall",
                "reviewer_notes",
            ]
        )
        for rec in sample:
            opts = rec.options or {}
            w.writerow(
                [
                    rec.question_id,
                    rec.subject,
                    rec.class_level,
                    rec.chapter,
                    rec.topic,
                    rec.generation_provider,
                    rec.difficulty,
                    rec.question_type,
                    rec.question,
                    opts.get("A", ""),
                    opts.get("B", ""),
                    opts.get("C", ""),
                    opts.get("D", ""),
                    rec.correct_option,
                    rec.source_file,
                    rec.validation_status,
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "PENDING",
                    "",
                ]
            )
