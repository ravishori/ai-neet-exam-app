"""Config + the network guard.

Import this module first (cli.py does) to install a hard fail-closed guard
against any accidental network usage during classification.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
NCERT_ROOT = REPO_ROOT / "NCERT Books"
DATA_DIR = REPO_ROOT / "data" / "ncert"
INDEX_DIR = DATA_DIR / "index"
MANIFEST_PATH = DATA_DIR / "ncert_manifest.json"
REPORTS_DIR = REPO_ROOT / "reports"

CLASSIFIER_VERSION = "ncert-local-v1"
CLASSIFIER_VERSION_PHASE2 = "ncert-local-v2"
VALID_SUBJECTS = ("Physics", "Chemistry", "Biology")

DSN = "postgresql://trinetra_app:trinetra_dev_pw@localhost:5432/trinetra_db"

# Class 11/12 x subject-dir -> canonical subject label. Biology dirs unify
# Botany+Zoology content at the source level (NCERT ships one Biology book
# per class covering both) into the single "Biology" bucket this task
# requires.
SUBJECT_DIR_MAP = {
    "physics": "Physics",
    "chemistry": "Chemistry",
    "biology": "Biology",
}


class NetworkGuardError(RuntimeError):
    pass


def install_network_guard() -> None:
    """Fail closed: any attempt to import a networking/LLM SDK module during
    this process raises immediately, so classification cannot silently make
    an external call. Applied via sys.meta_path so it also blocks import of
    submodules pulled in transitively.
    """
    blocked_prefixes = (
        "requests", "httpx", "aiohttp", "urllib3",
        "openai", "anthropic", "google.generativeai", "google.genai",
        "huggingface_hub", "cohere", "boto3",
    )

    import importlib.abc
    import importlib.machinery

    class _Blocker(importlib.abc.MetaPathFinder):
        def find_module(self, fullname, path=None):  # noqa: ARG002
            for prefix in blocked_prefixes:
                if fullname == prefix or fullname.startswith(prefix + "."):
                    raise NetworkGuardError(
                        f"pyq_subject_classifier: blocked import of '{fullname}' — "
                        "network/LLM SDKs are prohibited in this local-only classifier."
                    )
            return None

    sys.meta_path.insert(0, _Blocker())
