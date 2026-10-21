"""Step 1 validation: run classify_subject on a small, diverse sample of
pyq_image_staging.questions (mix of filenames/subjects) and print results
for manual eyeballing before scaling to all 899."""
import io
import sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\ravishori\AI Neet Exam App\apps\backend\scripts\pyq_image_pipeline")
import psycopg
from classify_subject import parse_taxonomy, build_index, classify_text, TAXONOMY_PATH

DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"

leaves = parse_taxonomy(TAXONOMY_PATH)
index = build_index(leaves)

conn = psycopg.connect(DSN)
cur = conn.cursor()
cur.execute(
    """
    SELECT id, source_file, subject, stem_text, options
    FROM pyq_image_staging.questions
    WHERE stem_text IS NOT NULL
    ORDER BY random()
    LIMIT 30
    """
)
rows = cur.fetchall()
for qid, source_file, subject, stem, options in rows:
    opt_text = ""
    if options:
        if isinstance(options, dict):
            opt_text = " ".join(str(v) for v in options.values())
        elif isinstance(options, list):
            opt_text = " ".join(str(v) for v in options)
    text = f"{stem or ''} {opt_text}"
    result = classify_text(text, index, source_file)
    print("=" * 100)
    print(f"id={qid} source_file={source_file} original_subject={subject}")
    print(f"stem: {(stem or '')[:150]}")
    print(f"-> proposed={result['proposed_subject']} conf={result['confidence']} status={result['status']}")
    print(f"   chapter={result['proposed_chapter_topic']}")
    print(f"   evidence={result['evidence'][:200]}")

cur.close()
conn.close()
