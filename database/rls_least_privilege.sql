-- OPTIONAL operator script — REQUIRES INFRASTRUCTURE.
-- Do NOT run blindly against production. Review with DBA.
-- Goal: separate DDL owner from runtime DML role; optional RLS scaffolding.
--
-- Prerequisites: roles from database/init.sql already exist.
-- After cutover, point DATABASE_URL at trinetra_app (non-owner) and
-- DATABASE_URL_SYNC / Alembic at trinetra_migration.

-- Example: transfer schema ownership to migration role (run as superuser)
-- ALTER SCHEMA identity OWNER TO trinetra_migration;
-- ALTER SCHEMA academic OWNER TO trinetra_migration;
-- ALTER SCHEMA cms OWNER TO trinetra_migration;
-- ALTER SCHEMA assessment OWNER TO trinetra_migration;
-- ALTER SCHEMA ai OWNER TO trinetra_migration;
-- ALTER SCHEMA analytics OWNER TO trinetra_migration;
-- ALTER SCHEMA commerce OWNER TO trinetra_migration;
-- ALTER SCHEMA system OWNER TO trinetra_migration;

-- Example grants for runtime app (adjust after ownership transfer)
-- GRANT USAGE ON SCHEMA identity, academic, cms, assessment, ai, analytics, commerce, system TO trinetra_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA identity TO trinetra_app;
-- ... repeat per schema; set ALTER DEFAULT PRIVILEGES for future tables.

-- Example RLS scaffold (policy body is illustrative — not production-ready)
-- ALTER TABLE assessment.attempts ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY attempts_owner ON assessment.attempts
--   USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);

SELECT 'Review docs/database-security.md before applying any statements in this file.' AS notice;
