"""CLI for PASTQ-OCR-002 OCR staging (no production import).

  python -m app.modules.cms.acquisition.pastq.ocr_cli --stage
  python -m app.modules.cms.acquisition.pastq.ocr_cli --stage --force
  python -m app.modules.cms.acquisition.pastq.ocr_cli --stage --only NEET2015.pdf
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.modules.cms.acquisition.pastq.ocr_pipeline import (
    DEFAULT_SOURCE_ROOT,
    DEFAULT_STAGING,
    list_scanned_from_inventory,
    run_ocr_staging,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="PASTQ-OCR-002 OCR staging for scanned past papers")
    p.add_argument("--source-root", default=str(DEFAULT_SOURCE_ROOT))
    p.add_argument("--staging-dir", default=str(DEFAULT_STAGING))
    p.add_argument("--stage", action="store_true", help="Run OCR staging (default action)")
    p.add_argument("--force", action="store_true", help="Re-OCR even if cache exists")
    p.add_argument("--dpi", type=int, default=300)
    p.add_argument("--only", default="", help="Comma-separated filenames")
    p.add_argument("--list-scanned", action="store_true", help="List the 7 scanned targets and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    only = [x.strip() for x in args.only.split(",") if x.strip()]

    if args.list_scanned:
        scanned = list_scanned_from_inventory(Path(args.source_root))
        print(json.dumps(scanned, indent=2))
        return 0

    # Default to staging
    summary = run_ocr_staging(
        source_root=args.source_root,
        staging_dir=args.staging_dir,
        dpi=args.dpi,
        force=args.force,
        only=only or None,
    )
    print(json.dumps(asdict(summary), indent=2, ensure_ascii=False)[:8000])
    print("STOP: OCR staging complete — no production import performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
