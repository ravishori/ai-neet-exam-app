"""Path-resolution regression test for scripts/import_pyq_staging.py.

Proves _resolve_repo_root() picks the correct repo root in a local
checkout and falls back safely under the flattened Docker layout,
without needing two real directory trees on disk — Path.resolve() on a
synthetic path doesn't require the path to exist, only that its parent
count matches the real layout being simulated. No database, no network,
no staging data required.
"""

from __future__ import annotations

from pathlib import Path

from scripts.import_pyq_staging import _resolve_repo_root


def test_local_checkout_layout_resolves_to_repo_root():
    """apps/backend/scripts/import_pyq_staging.py -> repo root is 3
    directories up (parents[3]), same as the module's own default."""
    synthetic = Path("some") / "repo" / "apps" / "backend" / "scripts" / "import_pyq_staging.py"
    resolved = _resolve_repo_root(synthetic)
    expected = Path(synthetic).resolve().parents[3]
    assert resolved == expected
    # The repo root is the ancestor two levels above "apps" — sanity-check
    # the structure, not just that parents[3] didn't raise.
    assert resolved.name == "repo"


def test_docker_flattened_layout_resolves_to_app_root():
    """/app/scripts/import_pyq_staging.py -> only 2 directories above the
    filesystem root exist (parents = [/app/scripts, /app, /]), so
    parents[3] would raise IndexError — must fall back to the actual
    Docker COPY root (/app), not "/", since that's where data/staging/
    actually lands in the deployed image."""
    synthetic = Path("/") / "app" / "scripts" / "import_pyq_staging.py"
    parents = synthetic.resolve().parents
    assert len(parents) == 3  # confirms this synthetic path actually reproduces the crash precondition

    resolved = _resolve_repo_root(synthetic)
    assert resolved == Path("/app").resolve()


def test_unrecognized_flattened_layout_falls_back_to_filesystem_root():
    """A flattened layout that isn't rooted at /app (some other container
    convention) has no better anchor available, so it must still fall back
    to "/" rather than raising."""
    synthetic = Path("/") / "srv" / "import_pyq_staging.py"
    resolved = _resolve_repo_root(synthetic)
    assert resolved == Path("/")


def test_staging_root_derives_identically_regardless_of_repo_root_fallback():
    """The manifest_path/staging-root provenance string must stay
    identical in shape ("data/staging/pyq/2020-2025/...") whether
    REPO_ROOT resolved via the local branch or the Docker fallback — this
    fix only changes where the root points to, never the importer's own
    relative structure or behavior."""
    local_root = _resolve_repo_root(Path("some") / "repo" / "apps" / "backend" / "scripts" / "import_pyq_staging.py")
    docker_root = _resolve_repo_root(Path("/") / "app" / "scripts" / "import_pyq_staging.py")

    local_staging = local_root / "data" / "staging" / "pyq" / "2020-2025"
    docker_staging = docker_root / "data" / "staging" / "pyq" / "2020-2025"

    assert local_staging.relative_to(local_root) == docker_staging.relative_to(docker_root)
    assert docker_staging == Path("/app").resolve() / "data" / "staging" / "pyq" / "2020-2025"
