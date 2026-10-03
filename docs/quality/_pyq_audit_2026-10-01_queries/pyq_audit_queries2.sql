BEGIN TRANSACTION READ ONLY;

\echo '=== 45. STATE x EXAM_YEAR ==='
SELECT sf.exam_year, q.state, count(*) FROM pyq.questions q JOIN pyq.source_files sf ON sf.id=q.source_file_id
GROUP BY sf.exam_year, q.state ORDER BY 1,2;

\echo '=== 46. STATE x SUBJECT ==='
SELECT COALESCE(subject,'(null)') AS subject, state, count(*) FROM pyq.questions GROUP BY subject, state ORDER BY 1,2;

\echo '=== 47. EXACT question_hash DUPLICATES: WITHIN SAME source_file vs ACROSS DIFFERENT source_files ==='
WITH dup_groups AS (
  SELECT question_hash FROM pyq.questions GROUP BY question_hash HAVING count(*) > 1
),
dup_rows AS (
  SELECT q.id, q.question_hash, q.source_file_id FROM pyq.questions q
  JOIN dup_groups d ON d.question_hash = q.question_hash
),
per_group AS (
  SELECT question_hash, count(DISTINCT source_file_id) AS distinct_files, count(*) AS rows_in_group
  FROM dup_rows GROUP BY question_hash
)
SELECT
  count(*) FILTER (WHERE distinct_files = 1) AS groups_within_single_file,
  count(*) FILTER (WHERE distinct_files > 1) AS groups_across_multiple_files,
  sum(rows_in_group) FILTER (WHERE distinct_files = 1) AS rows_within_single_file,
  sum(rows_in_group) FILTER (WHERE distinct_files > 1) AS rows_across_multiple_files
FROM per_group;

\echo '=== 48. SAMPLE OF WITHIN-SAME-FILE EXACT HASH DUPLICATE GROUPS (first 5, question_number list) ==='
WITH dup_groups AS (
  SELECT question_hash FROM pyq.questions GROUP BY question_hash HAVING count(*) > 1
),
per_file AS (
  SELECT q.question_hash, q.source_file_id, array_agg(q.question_number ORDER BY q.question_number) AS qnums, count(*) AS n
  FROM pyq.questions q JOIN dup_groups d ON d.question_hash=q.question_hash
  GROUP BY q.question_hash, q.source_file_id
  HAVING count(*) > 1
)
SELECT question_hash, source_file_id, qnums, n FROM per_file ORDER BY n DESC LIMIT 5;

\echo '=== 49. source_files with NULL exam_year / paper_code: which rows ==='
SELECT id, paper_id, paper_code, exam_year, relative_path FROM pyq.source_files WHERE exam_year IS NULL OR paper_code IS NULL OR btrim(paper_code)='';

\echo '=== 50. VERIFIED assertions: asserted_option DISTRIBUTION (answer-key letter balance sanity) ==='
SELECT asserted_option, count(*) FROM pyq.answer_assertions GROUP BY asserted_option ORDER BY 1;

\echo '=== 51. VERIFIED questions BY exam_year x subject (coverage of the 2452 verified rows) ==='
SELECT COALESCE(sf.exam_year,'(null)') AS exam_year, COALESCE(q.subject,'(null)') AS subject, count(*) AS verified_count
FROM pyq.questions q
JOIN pyq.source_files sf ON sf.id = q.source_file_id
WHERE q.state = 'ANSWER_VERIFIED'
GROUP BY sf.exam_year, q.subject ORDER BY 1,2;

\echo '=== 52. extraction_confidence bucket x state (is low-confidence correlated with pending) ==='
SELECT state,
  count(*) FILTER (WHERE extraction_confidence >= 0.9) AS ge_0_9,
  count(*) FILTER (WHERE extraction_confidence < 0.9) AS lt_0_9
FROM pyq.questions GROUP BY state;

\echo '=== 53. Distinct extraction_confidence values actually present (coarse/binary check) ==='
SELECT extraction_confidence, count(*) FROM pyq.questions GROUP BY extraction_confidence ORDER BY 1;

COMMIT;
