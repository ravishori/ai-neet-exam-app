"""Read-only inventory of StudyMaterial. Does not modify source files."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\ravishori\AI Neet Exam App\StudyMaterial")
OUT = Path(r"D:\ravishori\AI Neet Exam App\scripts\StudyMaterial_INVENTORY.json")


def infer_class(class_folder: str) -> str:
    if "Class 11" in class_folder or "Class11" in class_folder.replace(" ", ""):
        return "11"
    if "Class 12" in class_folder or "Class12" in class_folder.replace(" ", ""):
        return "12"
    return "unknown"


def main() -> int:
    try:
        import fitz
    except ImportError:
        print("NO_PYMUPDF", file=sys.stderr)
        return 1

    rows: list[dict] = []
    first_seen: dict[str, str] = {}

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if "Uploads" in path.parts:
            continue

        rel = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        checksum = hashlib.sha256(data).hexdigest()
        size = len(data)
        pages = None
        readable = "ok"
        err = None

        if path.suffix.lower() == ".pdf":
            try:
                doc = fitz.open(stream=data, filetype="pdf")
                pages = doc.page_count
                sample = ""
                for i in range(min(3, pages or 0)):
                    sample += doc[i].get_text()
                if pages == 0:
                    readable = "empty"
                elif len(sample.strip()) < 40:
                    readable = "likely_scanned_or_image_pdf"
                doc.close()
            except Exception as exc:  # noqa: BLE001 — inventory must continue
                readable = "unreadable"
                err = str(exc)

        parts = Path(rel).parts
        subject = parts[0] if parts else ""
        class_folder = parts[1] if len(parts) > 1 else ""
        dup_of = first_seen.get(checksum)
        if checksum not in first_seen:
            first_seen[checksum] = rel

        rows.append(
            {
                "absolute_source_path_dev": str(path),
                "relative_source_path": rel,
                "file_name": path.name,
                "file_type": path.suffix.lower().lstrip(".") or "unknown",
                "extension": path.suffix.lower(),
                "file_size": size,
                "class": infer_class(class_folder),
                "subject": subject,
                "class_folder": class_folder,
                "title": path.stem,
                "publisher": "NCERT" if "ncert" in path.name.lower() else None,
                "edition": None,
                "page_count": pages,
                "readability_extraction_status": readable,
                "error": err,
                "checksum_sha256": checksum,
                "duplicate_of_relative_path": dup_of,
                "is_duplicate": dup_of is not None,
            }
        )

    payload = {
        "root": str(ROOT),
        "file_count": len(rows),
        "total_bytes": sum(r["file_size"] for r in rows),
        "duplicate_count": sum(1 for r in rows if r["is_duplicate"]),
        "by_subject": dict(Counter(r["subject"] for r in rows)),
        "by_class": dict(Counter(r["class"] for r in rows)),
        "by_subject_class": dict(
            Counter(f"{r['subject']}|{r['class']}" for r in rows)
        ),
        "by_readability": dict(
            Counter(r["readability_extraction_status"] for r in rows)
        ),
        "page_count_total": sum(r["page_count"] or 0 for r in rows),
        "files": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"WROTE {OUT}")
    print(f"files={payload['file_count']} duplicates={payload['duplicate_count']}")
    print(f"by_subject={payload['by_subject']}")
    print(f"by_class={payload['by_class']}")
    print(f"by_readability={payload['by_readability']}")
    print(f"pages_total={payload['page_count_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
