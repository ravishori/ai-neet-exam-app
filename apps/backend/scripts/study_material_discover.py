"""Thin wrapper so operators can run::

    python scripts/study_material_discover.py discover
    python scripts/study_material_discover.py discover --dry-run

from apps/backend (same pattern as scripts/seed.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.modules.ingestion.cli.study_material import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
