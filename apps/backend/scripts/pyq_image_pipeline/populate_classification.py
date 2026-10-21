"""Populate proposed_subject/proposed_chapter_topic/classification_* columns
for all rows in pyq_image_staging.questions. Local DB only. Never writes to
the original `subject` column."""
import sys
sys.path.insert(0, r"D:\ravishori\AI Neet Exam App\apps\backend\scripts\pyq_image_pipeline")
import psycopg
from classify_subject import parse_taxonomy, build_index, classify_text, TAXONOMY_PATH

DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"

assert "localhost" in DSN, "refusing to run against non-local DSN"

leaves = parse_taxonomy(TAXONOMY_PATH)
index = build_index(leaves)

conn = psycopg.connect(DSN)
cur = conn.cursor()
cur.execute(
    """
    SELECT id, source_file, subject, stem_text, options
    FROM pyq_image_staging.questions
    """
)
rows = cur.fetchall()
print(f"Processing {len(rows)} rows")

update_cur = conn.cursor()
count_classified = 0
count_manual = 0
for qid, source_file, subject, stem, options in rows:
    opt_text = ""
    if options:
        if isinstance(options, dict):
            opt_text = " ".join(str(v) for v in options.values())
        elif isinstance(options, list):
            opt_text = " ".join(str(v) for v in options)
    text = f"{stem or ''} {opt_text}"
    result = classify_text(text, index, source_file)
    update_cur.execute(
        """
        UPDATE pyq_image_staging.questions
        SET proposed_subject = %s,
            proposed_chapter_topic = %s,
            classification_confidence = %s,
            classification_evidence = %s,
            classification_status = %s
        WHERE id = %s
        """,
        (
            result["proposed_subject"],
            result["proposed_chapter_topic"],
            result["confidence"],
            result["evidence"][:4000],
            result["status"],
            qid,
        ),
    )
    if result["status"] == "CLASSIFIED":
        count_classified += 1
    else:
        count_manual += 1

conn.commit()
print(f"Done. CLASSIFIED={count_classified} MANUAL_REVIEW_REQUIRED={count_manual} total={len(rows)}")
cur.close()
update_cur.close()
conn.close()
