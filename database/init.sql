-- Trinetra AI Learning OS — database bootstrap (SP0-03)
-- Run once as a Postgres superuser. Idempotent where practical.

-- Roles -----------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'trinetra_app') THEN
    CREATE ROLE trinetra_app LOGIN PASSWORD 'trinetra_dev_pw';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'trinetra_migration') THEN
    CREATE ROLE trinetra_migration LOGIN PASSWORD 'trinetra_migration_dev_pw';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'trinetra_readonly') THEN
    CREATE ROLE trinetra_readonly LOGIN PASSWORD 'trinetra_readonly_dev_pw';
  END IF;
END
$$;

-- Database ----------------------------------------------------------------
-- (created separately via `CREATE DATABASE`, see setup.md — cannot run
-- inside a DO block / transaction)

-- Everything below runs with \c trinetra_db first ------------------------
