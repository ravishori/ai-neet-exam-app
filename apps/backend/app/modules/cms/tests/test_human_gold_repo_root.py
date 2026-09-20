"""Regression test for the production crash: REPO_ROOT computed via a
fixed-depth Path.parents[6] raised IndexError under the Docker image's
flattened layout (only ~4 parent directories exist there), crashing the
whole app at import time. See human_gold_sandbox_service.py's
resolve_human_gold_repo_root for the fix."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.modules.cms.services.human_gold_sandbox_service import resolve_human_gold_repo_root


def test_resolve_human_gold_repo_root_in_normal_checkout():
    """A real, deep checkout resolves via the parents[6] branch — same
    result the original hardcoded expression produced, no behavior change
    for the environment that always worked."""
    root = resolve_human_gold_repo_root(__file__)
    assert isinstance(root, Path)
    assert root == Path(__file__).resolve().parents[6]


def test_resolve_human_gold_repo_root_does_not_raise_under_docker_depth():
    """Simulate the Docker image's flattened layout (/app/app/modules/...,
    only 4 parents above /) — this must NOT raise IndexError, and must
    fall back to the container's WORKDIR instead of crashing the app."""
    shallow_file = "/app/app/modules/cms/api/human_gold_sandbox_router.py"
    with patch("app.modules.cms.services.human_gold_sandbox_service._DOCKER_REPO_ROOT", Path("/app")), \
         patch.object(Path, "is_dir", return_value=True):
        root = resolve_human_gold_repo_root(shallow_file)
    assert root == Path("/app")


def test_resolve_human_gold_repo_root_fails_safely_when_undeterminable():
    """Neither the deep-checkout depth nor the Docker fallback directory
    exists — must raise a clear, actionable error rather than silently
    pointing at an unrelated directory."""
    shallow_file = "/app/app/modules/cms/api/human_gold_sandbox_router.py"
    with patch("app.modules.cms.services.human_gold_sandbox_service._DOCKER_REPO_ROOT", Path("/nonexistent-root-xyz")):
        with pytest.raises(RuntimeError, match="Cannot determine repo root"):
            resolve_human_gold_repo_root(shallow_file)
