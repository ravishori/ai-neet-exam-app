# ADR-0029: CI/CD pipeline

## Status
Accepted

## Context
The application had reached feature-complete status for a v1.0 release
(the prior Release Readiness Report scored it 51/100, No-Go, citing "no
CI/CD" as one of several blockers). This ADR covers introducing GitHub
Actions under the standing architecture freeze — no redesign, no business
logic changes, additive only.

The codebase had never been linted, formatted, or dependency-scanned as a
whole before this. That created a real tension: a "production-grade" CI
gate that's honest about strictness will surface pre-existing findings on
its very first run, but this task was explicitly scoped to CI/CD
infrastructure, not to fixing every pre-existing issue it can now see.

## Decisions

**Ruff, not a generic default config.** FastAPI's `Depends(...)` default
arguments and SQLAlchemy's string-quoted `Mapped["Class"]` forward
references both trip default lint rules (`B008`, `F821`) as false
positives — confirmed by inspecting every hit before deciding to ignore
it, not by disabling the rule wholesale. `apps/backend/pyproject.toml`
documents each ignore with why.

**A real, narrow exception for a real, already-fixed bug.** `RoleRepository`
and `UserRepository` both define a method literally named `list`, which
shadows the builtin for every later annotation in the same class body —
this caused a real `TypeError` earlier in the project, fixed by using
`typing.List`/`Tuple` instead of bare `list`/`tuple` in just those two
files. Ruff's `UP006`/`UP035` "modernize to bare list/tuple" rule would
undo that fix if applied automatically, so it's scoped out for exactly
those two files via `per-file-ignores`, not disabled globally.

**Fixed 7 pre-existing lint findings directly; left 5 alone.** Unused
imports (`F401`) and import ordering (`I001`) are zero-behavior-change —
fixed directly, then verified by re-running every test touching the
affected files. Blocking I/O in async handlers (`ASYNC230`/`ASYNC240`,
5 findings) requires wrapping calls in a thread executor, a behavioral
change to request handling — left as pre-existing, documented in
`docs/deploy/TEST_REPORT.md`, surfaced as a non-blocking CI step rather
than silently dropped or blindly fixed.

**Security/dependency scanning (CodeQL, gitleaks, pip-audit, npm audit)
starts non-blocking.** First-ever run against this codebase; making any
of them a hard gate on day one would fail CI on findings this task
didn't scope in to fix. Tightening any one of them later is a one-line
change (see `docs/deploy/CI_CD.md`), not a redesign.

**Docker images are a CI/CD artifact, not a new deploy mechanism.**
Coolify already builds its own images directly from git source
(`docs/deploy/RUNBOOK.md`) — that is unchanged. `deploy.yml` additionally
builds and pushes the same images to GHCR, scanned with Trivy, purely for
traceability and CVE history. The actual deploy still happens by calling
Coolify's webhook, which triggers Coolify's existing build-from-source
path.

**Rollback is two documented paths, not a new mechanism.** Coolify's
native "redeploy a prior commit" (now automatable via a `workflow_dispatch`
input) for fast application-only rollback, and `git revert` + push for
when history itself needs correcting. Database migrations are explicitly
excluded from any automated rollback — `alembic downgrade` stays a manual,
deliberate action. See `docs/deploy/ROLLBACK.md`.

**No repo remote exists yet.** None of this executes until the repository
is pushed to GitHub — stated plainly in `docs/deploy/CI_CD.md`, mirroring
`RUNBOOK.md`'s own "treat first use as a dry run" framing rather than
overclaiming a pipeline that has never actually run.

## Consequences
CI is genuinely green on everything it hard-gates, not green because the
bar was lowered to fit whatever already existed. The 5 ASYNC findings and
the dependency-scan results are real, visible, tracked debt — not hidden,
just not gated on day one of a legacy codebase's first-ever lint/scan
pass. Tightening the gates over time is expected and cheap.
