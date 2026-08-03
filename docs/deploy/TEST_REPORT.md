# Test report — CI/CD pipeline introduction

Baseline snapshot taken while adding the CI/CD pipeline (GitHub Actions,
linting, Docker build, security/dependency scanning, deploy + rollback).
Scope for this change was CI/CD infrastructure only — "do not modify
business logic" — so findings below are reported honestly rather than
fixed where fixing them would mean editing existing application files
beyond trivial, zero-behavior-change cleanup.

## Backend

**Test suite:** 209 passed, 0 failed — both before and after this change
(full suite re-run, 359.80s). The only application files touched were 7
mechanical import fixes (see "Lint" below); the 82 tests covering those
specific files were also re-run in isolation immediately after the fix,
before the full-suite re-run confirmed no regressions anywhere else.

**Lint (`ruff`, `apps/backend/pyproject.toml`):**
- Hard-gated rule set (`E, F, I, UP, B`): **0 findings**, after fixing 7
  pre-existing issues directly (3 unused imports, 4 unsorted-import
  blocks) — purely mechanical, no behavior change, verified by re-running
  every test that touches the affected files.
- `F821` (undefined-name) false positives across every SQLAlchemy model
  with a `relationship()` — ruff doesn't resolve `Mapped["ClassName"]`
  string forward-references. Scoped out via
  `per-file-ignores: "app/modules/*/models/*.py" = ["F821"]`, not a
  blanket ignore.
- `UP006`/`UP035` (modernize `typing.List`/`Tuple` to bare `list`/`tuple`)
  scoped out for exactly two files —
  `role_repository.py` and `user_repository.py` — because both classes
  define a method literally named `list`, which shadows the builtin
  `list` name for every annotation evaluated later in the class body.
  Applying ruff's own suggested fix here would reintroduce a real bug
  that was already hit and fixed earlier in this project (a
  `TypeError: 'function' object is not subscriptable` at import time).
- **ASYNC (5 findings, not in the hard gate — pre-existing, out of scope
  for this task):**
  - `ingestion_router.py:71` — blocking `open()` call in an async handler.
  - `ingestion_router.py:261,262` and `knowledge_router.py:51,52` —
    blocking `pathlib.Path` methods in async handlers.
  - Real fix requires wrapping the blocking I/O in a thread executor
    (`anyio.to_thread.run_sync` or similar), which is a behavioral change
    to request handling, not a style fix — belongs in its own PR.
    Currently visible as an informational CI step
    (`ruff check app/ --select ASYNC`), not a blocker.

**Dependency scan (`pip-audit`, first run, informational):** results are
visible in the `security.yml` job output / GitHub Actions logs once the
repo is pushed; not reproduced here since findings shift as new CVEs are
disclosed — check the live job output, not this document, for current
status.

## Frontend

**Test suite:** did not exist before this change (`package.json` had no
`test` script and no test framework in `devDependencies`). Added Vitest +
React Testing Library with 2 test files / 7 tests as a genuine starter
suite, not a placeholder:
- `src/lib/utils.test.ts` — the `cn()` class-merging utility (3 tests).
- `src/components/ui/empty-state.test.tsx` — the `EmptyState` component,
  rendering + conditional description + action slot (4 tests).

All 7 pass. **This is intentionally a minimal starter suite, not
coverage of existing features** — writing tests for the full existing
frontend (auth forms, question browser, practice runner, admin portal's
9 modules, etc.) is a substantial separate effort, already estimated at
2–3 days in the prior Release Readiness Report, and out of scope for a
CI/CD-infrastructure task.

**Lint (`eslint`) + typecheck (`tsc --noEmit`):** 0 errors. 4 pre-existing
warnings (`@next/next/no-img-element` on 3 files using `<img>` instead of
`next/image`) — cosmetic/perf advice, not correctness issues, left as-is.

**Dependency scan (`npm audit`):** 3 high-severity findings, all
transitive through `next`'s bundled `postcss`/`sharp` versions (XSS in
CSS stringification, libvips CVEs). `npm audit fix --force`'s only
suggested remedy is downgrading `next` to `9.3.3` — a 6-major-version
downgrade that would break the entire application, not a real fix; this
is a known class of false lead in npm's audit resolution when a
transitive range is misresolved. Recommend tracking via Dependabot
(configured, weekly) and applying the real fix once Next.js ships a
patched `postcss`/`sharp` transitive version, not by downgrading now.

## Overall
No test regressions from this change. CI/CD pipeline is genuinely green
on the rules it hard-gates; every non-blocking finding above is
pre-existing, documented, and tracked rather than silently ignored.
