import json
from collections import Counter
from pathlib import Path

staging = Path(r"D:\ravishori\AI Neet Exam App\data\staging\pastq_ocr_002")
recs = [
    json.loads(line)
    for line in (staging / "questions_all.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
out = {
    "by_file": dict(Counter(r["source"]["file"] for r in recs)),
    "answer_status": dict(Counter(r["answer"].get("status") for r in recs)),
    "staging_status": dict(Counter(r["quality"].get("staging_status") for r in recs)),
    "duplicate_class": dict(Counter(r["quality"].get("duplicate_class") for r in recs)),
    "ready_for_review": sum(1 for r in recs if r["quality"].get("staging_status") == "READY_FOR_REVIEW"),
    "conflict_examples": [
        {
            "file": r["source"]["file"],
            "q": r["question"].get("number"),
            "answer": r["answer"],
        }
        for r in recs
        if r["answer"].get("status") == "ANSWER_CONFLICT"
    ][:8],
}
conf = [r["quality"].get("ocr_confidence") for r in recs if r["quality"].get("ocr_confidence") is not None]
out["ocr_confidence_present"] = len(conf)
out["ocr_confidence_avg"] = round(sum(conf) / len(conf), 2) if conf else None
print(json.dumps(out, indent=2, ensure_ascii=False))
(Path(r"D:\ravishori\AI Neet Exam App\docs\audits\_pastq_ocr_002_stats.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
))
