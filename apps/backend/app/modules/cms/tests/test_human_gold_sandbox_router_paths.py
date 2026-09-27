"""Path-resolution regression test for
app/modules/cms/api/human_gold_sandbox_router.py.

Proves _resolve_repo_root() picks the correct repo root in a local
checkout and falls back safely under the flattened Docker layout, without
needing two real directory trees on disk. No database, no network, no
staging data required. Mirrors
tests/test_import_pyq_staging_paths.py's coverage for the analogous fix in
scripts/import_pyq_staging.py, adjusted for this file's one-level-deeper
local-checkout ancestry (parents[6] here vs. parents[3] there, since this
file lives under apps/backend/app/modules/cms/api/ instead of
apps/backend/scripts/).
"""

from __future__ import annotations

from pathlib import Path

from app.modules.cms.api.human_gold_sandbox_router import _resolve_repo_root


def test_local_checkout_layout_resolves_to_repo_root():
    """apps/backend/app/modules/cms/api/human_gold_sandbox_router.py ->
    repo root is 6 directories up (parents[6]), same as the module's own
    default."""
    synthetic = (
        Path("some") / "repo" / "apps" / "backend" / "app" / "modules" / "cms" / "api" / "human_gold_sandbox_router.py"
    )
    resolved = _resolve_repo_root(synthetic)
    expected = Path(synthetic).resolve().parents[6]
    assert resolved == expected
    assert resolved.name == "repo"


def test_docker_flattened_layout_resolves_to_app_root():
    """/app/app/modules/cms/api/human_gold_sandbox_router.py -> only 5
    directories above the filesystem root exist (parents = [.../api,
    .../cms, .../modules, /app/app, /app, /]), so parents[6] would raise
    IndexError — must fall back to the actual Docker COPY root (/app), not
    "/", since that's where the rest of the app's runtime paths land in
    the deployed image."""
    synthetic = Path("/") / "app" / "app" / "modules" / "cms" / "api" / "human_gold_sandbox_router.py"
    parents = synthetic.resolve().parents
    assert len(parents) == 6  # confirms this synthetic path actually reproduces the crash precondition

    resolved = _resolve_repo_root(synthetic)
    assert resolved == Path("/app").resolve()


def test_unrecognized_flattened_layout_falls_back_to_filesystem_root():
    """A flattened layout that isn't rooted at /app (some other container
    convention) has no better anchor available, so it must still fall back
    to "/" rather than raising."""
    synthetic = Path("/") / "srv" / "human_gold_sandbox_router.py"
    resolved = _resolve_repo_root(synthetic)
    assert resolved == Path("/")
