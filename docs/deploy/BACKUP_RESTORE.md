# PostgreSQL backup and restore — TALOS

**Audience:** operators performing H1 Ops Truth / production DR.  
**Scope:** logical backups via `pg_dump` / `pg_restore` (or `psql` for plain SQL).  
**Do not commit backup files.** The repo ignores `/database/backups/`.

---

## 1. Naming convention

```text
database/backups/
  {env}_{dbname}_{YYYYMMDD_HHMMSS}Z.dump
  {env}_{dbname}_{YYYYMMDD_HHMMSS}Z.sql.gz   # optional plain format
```

Examples:

- `local_trinetra_db_20260912_120000Z.dump`
- `prod_trinetra_db_20260912_030000Z.dump`

Use **UTC** timestamps (`Z` suffix). Prefer custom format (`.dump`) for selective restore.

---

## 2. Retention guidance

| Environment | Suggested retention | Notes |
|-------------|---------------------|-------|
| Local/dev | 3–7 days or on-demand | Delete after successful restore drills |
| Staging | 7–14 days | Keep last successful pre-migration dump |
| Production | ≥14 daily + ≥4 weekly | Store **off-host** (object storage); encrypt at rest |

Production: Docker volumes alone are **not** a backup strategy (see `docs/deploy/RUNBOOK.md` §8).

---

## 3. Backup procedure (`pg_dump`)

### Prerequisites

- `pg_dump` / `pg_restore` / `psql` on PATH (or full path to PostgreSQL bin)
- Network access to the target Postgres
- Credentials via environment (never commit):

```powershell
# PowerShell — values from your secret store / Coolify env, not from git
$env:PGHOST = "localhost"          # or prod host
$env:PGPORT = "5432"
$env:PGUSER = "trinetra_app"       # or dedicated backup role
$env:PGDATABASE = "trinetra_db"
$env:PGPASSWORD = "<from-secret-store>"   # do not echo / log
```

### Custom-format dump (recommended)

```powershell
$ts = (Get-Date).ToUniversalTime().ToString("yyyyMMdd_HHmmss")
$outDir = "database/backups"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$out = Join-Path $outDir "local_trinetra_db_${ts}Z.dump"

& pg_dump --format=custom --no-owner --no-acl --file=$out
Write-Host "Wrote backup artifact (path only): $out"
Get-Item $out | Select-Object Name, Length, LastWriteTimeUtc
```

### Plain SQL (optional)

```powershell
& pg_dump --format=plain --no-owner --no-acl | gzip > "database/backups/local_trinetra_db_${ts}Z.sql.gz"
```

### Integrity of the dump file

```powershell
# Custom format: list TOC (fails if corrupt)
& pg_restore --list $out | Select-Object -First 5
```

---

## 4. Restore procedure

### Clean restore target

Never restore over production without an explicit maintenance window.  
For drills, create a **new** database.

**Privilege note:** the application role (`trinetra_app`) typically lacks
`CREATEDB`. Full clean-DB restore drills require either:

- a dedicated backup/restore role with `CREATEDB`, or  
- a short-lived superuser connection used **only** for the drill  

H1 Ops Truth does **not** grant extra privileges to the app role (that is
H3 / DBA territory). Without `CREATEDB`, operators must still verify dump
integrity with `pg_restore --list` (automated by `pg_restore_drill.ps1`,
exit code `2` = TOC OK / restore blocked on privilege).

```powershell
$env:PGDATABASE = "postgres"   # connect to maintenance DB
& psql -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS trinetra_db_h1_restore_drill WITH (FORCE);"
& psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE trinetra_db_h1_restore_drill OWNER trinetra_app;"
```

### Restore custom dump

```powershell
$env:PGDATABASE = "trinetra_db_h1_restore_drill"
& pg_restore --no-owner --no-acl --dbname=$env:PGDATABASE --exit-on-error $out
```

### Post-restore integrity checks

Compare key row counts (source vs restore), e.g.:

```sql
SELECT 'identity.users' AS t, count(*) FROM identity.users
UNION ALL SELECT 'cms.content_items', count(*) FROM cms.content_items
UNION ALL SELECT 'cms.content_versions', count(*) FROM cms.content_versions
UNION ALL SELECT 'academic.subjects', count(*) FROM academic.subjects
UNION ALL SELECT 'academic.chapters', count(*) FROM academic.chapters
UNION ALL SELECT 'academic.topics', count(*) FROM academic.topics
UNION ALL SELECT 'academic.concepts', count(*) FROM academic.concepts;
```

Also verify:

```sql
SELECT schema_name FROM information_schema.schemata
WHERE schema_name IN ('identity','academic','cms','assessment','ai','commerce','system')
ORDER BY 1;
```

### Cleanup after drill

```powershell
$env:PGDATABASE = "postgres"
& psql -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS trinetra_db_h1_restore_drill WITH (FORCE);"
```

---

## 5. Production schedule (operator checklist)

1. Nightly `pg_dump` custom format to off-host storage  
2. Weekly restore drill to a non-prod instance (monthly minimum)  
3. Before every production Alembic migration: take a named pre-migration dump  
4. Record artifact path, checksum (`Get-FileHash -Algorithm SHA256`), and restore result in the ops log / H1 evidence pack  

Helper scripts (local):

- `scripts/ops/pg_backup.ps1`
- `scripts/ops/pg_restore_drill.ps1`

---

## 6. What this does **not** cover

- WAL / point-in-time recovery (PITR) — configure at the provider if required  
- Coolify volume snapshots — complementary, not a substitute for logical dumps  
- Application object storage (StudyMaterial / visual assets) — back up volume mounts separately  
