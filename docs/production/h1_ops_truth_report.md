# H1 Ops Truth Report — TALOS Production Hardening

**Date:** 2026-09-12  
**Branch:** `phase2-question-bank`  
**Authorization:** H1 only (not H2–H6)  
**Overall verdict: AMBER — H1 REMEDIATION PARTIALLY VERIFIED**

Phase 0 baseline artifacts under `docs/production/*_audit.*` were **preserved** (not rewritten).

---

## Baseline (pre-H1)

| Item | Baseline state |
|------|----------------|
| Coolify / production TLS | Documented only; RUNBOOK states never executed against real VPS |
| SMTP / alerts | Code present; local SMTP/ALERT unset; Mailpit not running |
| Secrets in git | `.env` gitignored; examples placeholders |
| ENCRYPTION_KEY (local settings) | MISSING (MFA crypto will 503) |
| Backups | Volumes noted; no `pg_dump` procedure/scripts |
| Restore drill | Not performed |
| Payments | Keys unset → fail-closed (correct for H1) |

---

## Changes made (H1 scope only)

| Change | Path |
|--------|------|
| Backup/restore runbook | `docs/deploy/BACKUP_RESTORE.md` **(new)** |
| Backup script | `scripts/ops/pg_backup.ps1` **(new)** |
| Restore-drill script | `scripts/ops/pg_restore_drill.ps1` **(new)** |
| RUNBOOK SMTP/alerts/MFA/payments/backup corrections | `docs/deploy/RUNBOOK.md` |
| Prod env example: SMTP, ALERT, ENCRYPTION, WEB_APP_URL, payments go/no-go | `infrastructure/docker/.env.production.example` |
| This report | `docs/production/h1_ops_truth_report.md` / `.json` |

**Not changed:** application runtime auth/RLS/Redis/caching/OTel/Prometheus/payments code; Phase 0 audit files; live Coolify deploy.

---

## Control results

| # | Control | Classification | Evidence |
|---|---------|----------------|----------|
| H1.1 | Production TLS proof | **UNVERIFIED_PRODUCTION** | No Coolify/domain reachable; RUNBOOK still states no real VPS executed. Local `http://127.0.0.1:8000` is **not** production TLS. |
| H1.2 | SMTP + alert E2E | **PARTIALLY_IMPLEMENTED** | SMTP sender **IMPLEMENTED** in `email_service.py`. Local `SMTP_*` / `ALERT_EMAIL` = **MISSING**. Mailpit ports 1025/8025 unreachable. **No mailbox receipt proven.** Production delivery = **UNVERIFIED_PRODUCTION**. |
| H1.3 | Secrets hygiene | **PARTIALLY_IMPLEMENTED** | Tracked `.env` files: none (`git check-ignore` confirms `apps/backend/.env`). No committed PEM/private-key hits in app sources (scan). Examples remain empty placeholders. Prod vault / rotation = **UNVERIFIED**. Status labels: local secrets store **PRESENT** (gitignored); git exposure **MISSING** (good); rotation **UNVERIFIED**. |
| H1.4 | ENCRYPTION_KEY | **PARTIALLY_IMPLEMENTED** | Required for MFA TOTP (`crypto.py` / `totp_service.py`). Local settings: **MISSING** → MFA encrypt paths return 503. Tests inject a key via `conftest.py` (test-only). Prod presence: **UNVERIFIED_PRODUCTION**. **No key generated/rotated** (not authorized). |
| H1.5 | Payments go/no-go | **VERIFIED** (policy) | Razorpay keys unset → fail-closed. Documented in RUNBOOK + `.env.production.example`: do not enable live payments in H1. |
| H1.6 | `pg_dump` procedure | **IMPLEMENTED** + **VERIFIED** (local) | Procedure in `BACKUP_RESTORE.md`; script executed successfully. |
| H1.7 | Restore procedure | **IMPLEMENTED** (documented + scripted) | Full clean-DB restore path documented. |
| H1.8 | Restore drill | **PARTIALLY_IMPLEMENTED** | Dump TOC verified (`pg_restore --list`, 417 lines). Clean restore **blocked**: app role `CREATEDB=false` (H1 must not escalate DB privileges). Exit code `2` = intentional. Full row-count restore = **UNVERIFIED** until CREATEDB/superuser drill credential supplied by ops. |

---

## Backup / restore evidence (local)

| Field | Value |
|-------|-------|
| Source database | `trinetra_db` @ `localhost:5432` (user `trinetra_app`) |
| Backup artifact | `database/backups/local_trinetra_db_20260912_115341Z.dump` (gitignored) |
| Backup timestamp (UTC) | 2026-09-12T11:53:41Z (filename) / archive header 2026-09-12 17:23:42 local tool clock |
| Backup SHA-256 | `e4857c55385832010b32700881af4346a679d6abe750d7612f8d360b856ff82d` |
| Backup size | 5,049,104 bytes |
| Dump format | PostgreSQL custom, gzip, TOC entries 406 |
| Restore target | Intended `trinetra_db_h1_restore_drill` |
| Restore result | **BLOCKED** — `permission denied to create database` / `CREATEDB=false` |
| Integrity checks | Source counts captured prior to blocked create: users=136, content_items=6829, content_versions=6907, subjects=4, chapters=36, topics=113, concepts=163 |
| Recovery observation | Scripts now fail soft with TOC verification when CREATEDB absent; do not grant CREATEDB in H1 |

---

## TLS evidence

| Check | Result |
|-------|--------|
| Production HTTPS URL available | No |
| Certificate validity | **UNVERIFIED_PRODUCTION** |
| HTTP→HTTPS redirect | **UNVERIFIED_PRODUCTION** |
| HSTS at edge | **UNVERIFIED_PRODUCTION** (app middleware sets HSTS only when `ENVIRONMENT=production`) |
| Local HTTP API | Reachable historically; not TLS proof |

---

## SMTP / alert evidence

| Check | Result |
|-------|--------|
| Code path SMTP | **IMPLEMENTED** (`smtplib` when host+from set) |
| Local SMTP configured | **MISSING** |
| Mailpit listening | **MISSING** (timeout) |
| Real alert → mailbox | **UNVERIFIED** / not executed |
| Credentials exposed in report | **No** |

---

## Secrets hygiene summary

| Check | Status |
|-------|--------|
| `apps/backend/.env` tracked in git | **MISSING** (ignored — good) |
| Real secrets in committed examples | **MISSING** (placeholders only) |
| CI/deploy example updated with SMTP/ALERT/ENCRYPTION slots | **PRESENT** (empty values) |
| Secret values printed in this report | **No** |
| Production secret rotation | **UNVERIFIED** |

---

## Tests executed

| Suite | Result |
|-------|--------|
| `tests/test_security_wave_a.py` + `test_security_wave_c.py` | **12 passed** |
| H2–H6 feature tests | Not run (out of scope) |

---

## Unresolved production dependencies

1. Coolify / domain / Let’s Encrypt access for TLS proof  
2. Real SMTP provider + `ALERT_EMAIL` mailbox for alert E2E  
3. Production `ENCRYPTION_KEY` if MFA enabled  
4. Backup role with `CREATEDB` (or supervised superuser) for full restore drill  
5. Off-host backup storage + retention enforcement  

---

## Final H1 verdict

**AMBER — H1 REMEDIATION PARTIALLY VERIFIED**

Locally verifiable items advanced (backup procedure, dump artifact, TOC integrity, runbook/env example truth, payments go/no-go, security regression tests).  
Required production evidence (TLS, SMTP mailbox, full restore, prod secrets) remains **UNVERIFIED_PRODUCTION**.

---

## Mandatory stop

**Do not proceed to H2** without a separate authorization.
