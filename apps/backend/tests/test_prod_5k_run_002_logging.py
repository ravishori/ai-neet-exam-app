"""Regression test for the pilot driver crashing before any provider call
because LOG_PATH's parent directory (scratchpad/) did not exist on disk.

The live pilot for batch 926752d7-a8c9-4f46-ba70-3848dbd08ef9 hit this
exact failure. `_log()` must create its log file's parent directory on
first write instead of assuming it pre-exists.

Pure filesystem test — no DB, no provider, no network.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_DRIVER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prod_5k_run_002_subject_quota.py"


def _load_driver_module():
    spec = importlib.util.spec_from_file_location("prod_5k_run_002_subject_quota_logtest", _DRIVER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_log_creates_missing_parent_directory(tmp_path):
    driver = _load_driver_module()

    missing_dir = tmp_path / "does" / "not" / "exist" / "yet"
    log_path = missing_dir / "prod_5k_run_002.log.jsonl"
    assert not missing_dir.exists()

    driver._log({"level": "INFO", "event": "test"}, log_path=str(log_path))

    assert missing_dir.exists()
    assert log_path.exists()
    line = log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    record = json.loads(line)
    assert record["event"] == "test"
    assert "ts" in record


def test_log_appends_when_directory_already_exists(tmp_path):
    driver = _load_driver_module()

    log_path = tmp_path / "already-exists" / "run.log.jsonl"
    log_path.parent.mkdir(parents=True)

    driver._log({"level": "INFO", "event": "first"}, log_path=str(log_path))
    driver._log({"level": "INFO", "event": "second"}, log_path=str(log_path))

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "first"
    assert json.loads(lines[1])["event"] == "second"


def test_log_default_log_path_parent_is_creatable():
    """The module-level default LOG_PATH (scratchpad/prod_5k_run_002.log.jsonl)
    must resolve to a path whose parent can be created without error, even
    if that directory doesn't exist yet at import time."""
    driver = _load_driver_module()
    parent = Path(driver.LOG_PATH).parent
    parent.mkdir(parents=True, exist_ok=True)
    assert parent.exists()
