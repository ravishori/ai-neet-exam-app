-- Trinetra AI Learning OS — schema + extensions bootstrap (SP0-03)
-- Run against trinetra_db as a superuser, after database/init.sql.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "citext";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";

CREATE SCHEMA IF NOT EXISTS identity   AUTHORIZATION trinetra_app;
CREATE SCHEMA IF NOT EXISTS academic   AUTHORIZATION trinetra_app;
CREATE SCHEMA IF NOT EXISTS cms        AUTHORIZATION trinetra_app;
CREATE SCHEMA IF NOT EXISTS assessment AUTHORIZATION trinetra_app;
CREATE SCHEMA IF NOT EXISTS ai         AUTHORIZATION trinetra_app;
CREATE SCHEMA IF NOT EXISTS analytics  AUTHORIZATION trinetra_app;
CREATE SCHEMA IF NOT EXISTS commerce   AUTHORIZATION trinetra_app;
CREATE SCHEMA IF NOT EXISTS system     AUTHORIZATION trinetra_app;

GRANT ALL PRIVILEGES ON DATABASE trinetra_db TO trinetra_app;

-- trinetra_migration / trinetra_readonly are created by database/init.sql for
-- native/production setups. In the Docker Compose path, trinetra_app is the
-- bootstrap superuser and those roles don't exist yet — skip gracefully.
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'trinetra_migration') THEN
    GRANT trinetra_app TO trinetra_migration;
  END IF;
END
$$;

DO $$
DECLARE s TEXT;
BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'trinetra_readonly') THEN
    FOREACH s IN ARRAY ARRAY['identity','academic','cms','assessment','ai','analytics','commerce','system']
    LOOP
      EXECUTE format('GRANT USAGE ON SCHEMA %I TO trinetra_readonly', s);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT ON TABLES TO trinetra_readonly', s);
    END LOOP;
  END IF;
END
$$;
