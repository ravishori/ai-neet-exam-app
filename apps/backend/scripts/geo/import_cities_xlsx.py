"""Regenerate india_cities_source.json from a Cities-List.xlsx export.

Idempotent, source-preserving:
* Only exact-duplicate rows (State + City string-equal) are removed.
* Casing and spelling from the XLSX are preserved verbatim.
* The JSON is deterministic (states sorted A-Z, cities sorted A-Z per state).

Usage::

    python -m scripts.geo.import_cities_xlsx --xlsx path/to/Cities-List.xlsx
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

_OUT = Path(__file__).resolve().parents[2] / "app" / "modules" / "identity" / "data" / "india_cities_source.json"


def convert(xlsx_path: Path) -> dict:
    df = pd.read_excel(xlsx_path, sheet_name="Cities", dtype=str)
    df["City"] = df["City"].str.strip()
    df["State"] = df["State"].str.strip()
    before = len(df)
    df = df.drop_duplicates(subset=["State", "City"])
    after = len(df)

    grouped: dict[str, list[str]] = {}
    for _, r in df.iterrows():
        grouped.setdefault(r["State"], []).append(r["City"])
    for k in grouped:
        grouped[k].sort()

    return {
        "schema_version": 1,
        "source": xlsx_path.name,
        "exact_dups_removed": before - after,
        "notes": (
            'Regenerated from the authoritative Cities-List.xlsx. Values preserved '
            'verbatim from the source; only exact duplicate rows are removed. '
            'Do not hand-edit — regenerate via '
            'python -m scripts.geo.import_cities_xlsx --xlsx <path>.'
        ),
        "states": [
            {"name": s, "cities": grouped[s]}
            for s in sorted(grouped.keys())
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True, type=Path)
    args = ap.parse_args()
    data = convert(args.xlsx)
    _OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"wrote {_OUT} "
        f"states={len(data['states'])} "
        f"cities={sum(len(s['cities']) for s in data['states'])} "
        f"exact_dups_removed={data['exact_dups_removed']}"
    )


if __name__ == "__main__":
    main()
