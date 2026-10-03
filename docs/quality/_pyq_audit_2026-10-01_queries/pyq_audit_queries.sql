BEGIN TRANSACTION READ ONLY;

\echo '=== 1. TOTAL QUESTIONS ==='
SELECT count(*) AS total_questions FROM pyq.questions;

\echo '=== 2. STATE DISTRIBUTION ==='
SELECT state, count(*) FROM pyq.questions GROUP BY state ORDER BY count(*) DESC;

\echo '=== 3. VALIDATION_STATUS DISTRIBUTION ==='
SELECT validation_status, count(*) FROM pyq.questions GROUP BY validation_status ORDER BY count(*) DESC;

\echo '=== 4. SUBJECT DISTRIBUTION (incl NULL) ==='
SELECT COALESCE(subject,'(null)') AS subject, count(*) FROM pyq.questions GROUP BY subject ORDER BY count(*) DESC;

\echo '=== 5. CLASS_LEVEL DISTRIBUTION ==='
SELECT COALESCE(class_level,'(null)') AS class_level, count(*) FROM pyq.questions GROUP BY class_level ORDER BY count(*) DESC;

\echo '=== 6. QUESTIONS WITH NULL concept_id ==='
SELECT count(*) FILTER (WHERE concept_id IS NULL) AS null_concept, count(*) FILTER (WHERE concept_id IS NOT NULL) AS has_concept FROM pyq.questions;

\echo '=== 7. QUESTIONS WITH AT LEAST ONE ANSWER ASSERTION (any status) ==='
SELECT count(DISTINCT q.id) AS questions_with_any_assertion
FROM pyq.questions q JOIN pyq.answer_assertions a ON a.question_id = q.id;

\echo '=== 8. QUESTIONS WITH NO ANSWER ASSERTION AT ALL ==='
SELECT count(*) AS questions_with_no_assertion
FROM pyq.questions q
WHERE NOT EXISTS (SELECT 1 FROM pyq.answer_assertions a WHERE a.question_id = q.id);

\echo '=== 9. ANSWER ASSERTION VERIFICATION_STATUS DISTRIBUTION (row-level, not question-level) ==='
SELECT verification_status, count(*) FROM pyq.answer_assertions GROUP BY verification_status ORDER BY count(*) DESC;

\echo '=== 10. QUESTIONS WITH >=1 VERIFIED ASSERTION ==='
SELECT count(DISTINCT question_id) FROM pyq.answer_assertions WHERE verification_status = 'VERIFIED';

\echo '=== 11. QUESTIONS WITH >=1 DISPUTED ASSERTION ==='
SELECT count(DISTINCT question_id) FROM pyq.answer_assertions WHERE verification_status = 'DISPUTED';

\echo '=== 12. QUESTIONS WITH ONLY ASSERTED (no VERIFIED, no DISPUTED) ==='
SELECT count(*) FROM (
  SELECT question_id FROM pyq.answer_assertions
  GROUP BY question_id
  HAVING bool_or(verification_status='VERIFIED') = false AND bool_or(verification_status='DISPUTED') = false
) x;

\echo '=== 13. QUESTIONS WITH MULTIPLE DISTINCT ASSERTED_OPTION VALUES (conflicting assertions) ==='
SELECT count(*) FROM (
  SELECT question_id FROM pyq.answer_assertions
  GROUP BY question_id
  HAVING count(DISTINCT asserted_option) > 1
) x;

\echo '=== 13b. SAME, BROKEN DOWN BY WHETHER question.state = ANSWER_CONFLICT ==='
SELECT q.state, count(*) FROM (
  SELECT question_id FROM pyq.answer_assertions GROUP BY question_id HAVING count(DISTINCT asserted_option) > 1
) c JOIN pyq.questions q ON q.id = c.question_id GROUP BY q.state ORDER BY 2 DESC;

\echo '=== 14. ASSERTION_SOURCE DISTRIBUTION ==='
SELECT assertion_source, verification_status, count(*) FROM pyq.answer_assertions GROUP BY assertion_source, verification_status ORDER BY 1,2;

\echo '=== 15. ASSERTIONS WITH NULL/EMPTY evidence_note, BY VERIFICATION_STATUS ==='
SELECT verification_status,
  count(*) FILTER (WHERE evidence_note IS NULL OR btrim(evidence_note) = '') AS no_evidence_note,
  count(*) FILTER (WHERE evidence_note IS NOT NULL AND btrim(evidence_note) <> '') AS has_evidence_note,
  count(*) AS total
FROM pyq.answer_assertions GROUP BY verification_status ORDER BY 1;

\echo '=== 16. ASSERTIONS WITH NULL explanation vs present, BY STATUS ==='
SELECT verification_status,
  count(*) FILTER (WHERE explanation IS NULL OR btrim(explanation)='') AS no_explanation,
  count(*) FILTER (WHERE explanation IS NOT NULL AND btrim(explanation)<>'') AS has_explanation
FROM pyq.answer_assertions GROUP BY verification_status ORDER BY 1;

\echo '=== 17. resolver_version DISTRIBUTION ==='
SELECT COALESCE(resolver_version,'(null)') AS resolver_version, count(*) FROM pyq.answer_assertions GROUP BY resolver_version ORDER BY count(*) DESC;

\echo '=== 18. DUPLICATE_CANDIDATES: CLASSIFICATION DISTRIBUTION ==='
SELECT classification, count(*) FROM pyq.duplicate_candidates GROUP BY classification ORDER BY count(*) DESC;

\echo '=== 19. DUPLICATE_CANDIDATES: METHOD DISTRIBUTION ==='
SELECT method, classification, count(*) FROM pyq.duplicate_candidates GROUP BY method, classification ORDER BY 1,2;

\echo '=== 20. QUESTIONS INVOLVED IN >=1 DUPLICATE_CANDIDATE ROW (as source) ==='
SELECT count(DISTINCT question_id) FROM pyq.duplicate_candidates;

\echo '=== 21. CONFIRMED DUPLICATES (QA_CONFIRMED or EXACT_HASH) vs POSSIBLE (CANDIDATE/LIKELY) vs REJECTED ==='
SELECT
  count(DISTINCT question_id) FILTER (WHERE classification IN ('EXACT_HASH','QA_CONFIRMED')) AS confirmed_duplicate_questions,
  count(DISTINCT question_id) FILTER (WHERE classification IN ('CANDIDATE','LIKELY')) AS possible_duplicate_questions,
  count(DISTINCT question_id) FILTER (WHERE classification = 'QA_REJECTED_NOT_DUPLICATE') AS rejected_not_duplicate_questions
FROM pyq.duplicate_candidates;

\echo '=== 22. SOURCE_FILES: EXAM_YEAR DISTRIBUTION ==='
SELECT COALESCE(exam_year,'(null)') AS exam_year, count(*) AS source_files FROM pyq.source_files GROUP BY exam_year ORDER BY 1;

\echo '=== 23. QUESTIONS PER EXAM_YEAR (via source_files join) ==='
SELECT COALESCE(sf.exam_year,'(null)') AS exam_year, count(*) AS questions
FROM pyq.questions q JOIN pyq.source_files sf ON sf.id = q.source_file_id
GROUP BY sf.exam_year ORDER BY 1;

\echo '=== 24. QUESTIONS PER SUBJECT x EXAM_YEAR ==='
SELECT COALESCE(q.subject,'(null)') AS subject, COALESCE(sf.exam_year,'(null)') AS exam_year, count(*) AS questions
FROM pyq.questions q JOIN pyq.source_files sf ON sf.id = q.source_file_id
GROUP BY q.subject, sf.exam_year ORDER BY 1,2;

\echo '=== 25. SOURCE PROVENANCE COMPLETENESS: source_files missing paper_code ==='
SELECT count(*) FILTER (WHERE paper_code IS NULL OR btrim(paper_code)='') AS missing_paper_code,
       count(*) FILTER (WHERE exam_year IS NULL OR btrim(exam_year)='') AS missing_exam_year,
       count(*) AS total_source_files
FROM pyq.source_files;

\echo '=== 26. RAW_OPTIONS SHAPE SANITY: questions where raw_options is not a 4-element array-like / jsonb type check ==='
SELECT jsonb_typeof(raw_options) AS raw_options_type, count(*) FROM pyq.questions GROUP BY jsonb_typeof(raw_options) ORDER BY 2 DESC;

\echo '=== 26b. QUESTIONS WHERE raw_options ARRAY LENGTH <> 4 (when array type) ==='
SELECT jsonb_array_length(raw_options) AS option_count, count(*)
FROM pyq.questions WHERE jsonb_typeof(raw_options)='array'
GROUP BY jsonb_array_length(raw_options) ORDER BY 1;

\echo '=== 27. EXTRACTION_CONFIDENCE: NULL vs distribution buckets ==='
SELECT
  count(*) FILTER (WHERE extraction_confidence IS NULL) AS null_confidence,
  count(*) FILTER (WHERE extraction_confidence >= 0.9) AS ge_0_9,
  count(*) FILTER (WHERE extraction_confidence >= 0.7 AND extraction_confidence < 0.9) AS b_0_7_0_9,
  count(*) FILTER (WHERE extraction_confidence < 0.7) AS lt_0_7
FROM pyq.questions;

\echo '=== 28. QA_REVIEWS: DECISION DISTRIBUTION ==='
SELECT decision, count(*) FROM pyq.qa_reviews GROUP BY decision ORDER BY count(*) DESC;

\echo '=== 29. QUESTIONS WITH NO QA_REVIEW AT ALL (by current state) ==='
SELECT q.state, count(*) FROM pyq.questions q
WHERE NOT EXISTS (SELECT 1 FROM pyq.qa_reviews r WHERE r.question_id = q.id)
GROUP BY q.state ORDER BY 2 DESC;

\echo '=== 30. PROMOTION_LOG: OUTCOME DISTRIBUTION ==='
SELECT outcome, count(*) FROM pyq.promotion_log GROUP BY outcome ORDER BY count(*) DESC;

\echo '=== 31. QUESTIONS PROMOTED (state=PROMOTED) vs promotion_log rows (sanity cross-check) ==='
SELECT
  (SELECT count(*) FROM pyq.questions WHERE state='PROMOTED') AS state_promoted_count,
  (SELECT count(*) FROM pyq.promotion_log WHERE outcome='PROMOTED') AS log_promoted_count;

\echo '=== 32. SUBJECT_CONFLICT_REVIEWS: STATUS DISTRIBUTION ==='
SELECT review_status, count(*) FROM pyq.subject_conflict_reviews GROUP BY review_status ORDER BY count(*) DESC;

\echo '=== 33. SUBJECT_CLASSIFICATION_AUDIT: STATUS / CONFIDENCE DISTRIBUTION ==='
SELECT classification_status, confidence, count(*) FROM pyq.subject_classification_audit GROUP BY 1,2 ORDER BY 1,2;

\echo '=== 34. SUBJECT_CLASSIFICATION_AUDIT: NCERT_SOURCE presence ==='
SELECT count(*) FILTER (WHERE ncert_source IS NOT NULL AND btrim(ncert_source)<>'') AS has_ncert_source,
       count(*) FILTER (WHERE ncert_source IS NULL OR btrim(ncert_source)='') AS no_ncert_source,
       count(*) AS total
FROM pyq.subject_classification_audit;

\echo '=== 35. GEMINI_BATCH_ITEMS: STATUS DISTRIBUTION ==='
SELECT status, count(*) FROM pyq.gemini_batch_items GROUP BY status ORDER BY count(*) DESC;

\echo '=== 36. GEMINI_BATCH_JOBS: overview ==='
SELECT count(*) FROM pyq.gemini_batch_jobs;

\echo '=== 37. IMPORT_BATCHES: STATUS DISTRIBUTION ==='
SELECT status, count(*) FROM pyq.import_batches GROUP BY status ORDER BY count(*) DESC;

\echo '=== 38. SOURCES: LIST ==='
SELECT source_key, name, authority_type FROM pyq.sources ORDER BY source_key;

\echo '=== 39. EXACT HASH DUPLICATES WITHIN QUESTIONS TABLE ITSELF (question_hash appearing >1x) ==='
SELECT count(*) AS groups_with_duplicate_hash, sum(cnt) AS rows_involved FROM (
  SELECT question_hash, count(*) AS cnt FROM pyq.questions GROUP BY question_hash HAVING count(*) > 1
) x;

\echo '=== 40. NORMALIZED_QUESTION_HASH DUPLICATES ==='
SELECT count(*) AS groups_with_duplicate_norm_hash, sum(cnt) AS rows_involved FROM (
  SELECT normalized_question_hash, count(*) AS cnt FROM pyq.questions GROUP BY normalized_question_hash HAVING count(*) > 1
) x;

\echo '=== 41. QUESTIONS MISSING normalized_stem/normalized_options (NORMALIZED or later state expected to have these) ==='
SELECT state,
  count(*) FILTER (WHERE normalized_stem IS NULL) AS missing_normalized_stem,
  count(*) FILTER (WHERE normalized_options IS NULL) AS missing_normalized_options,
  count(*) AS total
FROM pyq.questions GROUP BY state ORDER BY state;

\echo '=== 42. BLOCKED QUESTIONS (state=BLOCKED) - sample reasons via promotion_log/qa_reviews if any ==='
SELECT count(*) FROM pyq.questions WHERE state = 'BLOCKED';

\echo '=== 43. TOTAL distinct question ids referenced vs promotion-eligible-but-not-promoted ==='
SELECT state, count(*) FROM pyq.questions WHERE state IN ('PROMOTION_ELIGIBLE') GROUP BY state;

\echo '=== 44. CMS content_items linked back from promotion_log (sanity: promoted content exists) ==='
SELECT count(*) AS promotion_log_rows,
       count(*) FILTER (WHERE content_item_id IS NOT NULL) AS with_content_item,
       count(*) FILTER (WHERE content_item_id IS NULL) AS without_content_item
FROM pyq.promotion_log;

COMMIT;
