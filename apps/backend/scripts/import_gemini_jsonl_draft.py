#!/usr/bin/env python3
"""CLI: Gemini JSONL → TALOS DRAFT importer.

Usage (from apps/backend):
  .venv/Scripts/python.exe scripts/import_gemini_jsonl_draft.py --input ../../docs/acquisition/batches/NEET_GEMINI_20260911-PHY11-CH02-B001/questions.jsonl
  .venv/Scripts/python.exe scripts/import_gemini_jsonl_draft.py --input .../questions.jsonl --commit

Or:
  python -m app.modules.cms.acquisition.gemini_jsonl_draft_importer --input ...

Default is dry-run (no DB writes). Never publishes.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.modules.cms.acquisition.gemini_jsonl_draft_importer import main

if __name__ == "__main__":
    main()
