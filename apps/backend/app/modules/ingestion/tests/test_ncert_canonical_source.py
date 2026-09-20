"""CF-SOURCE-001 — canonical NCERT source guard tests (no AI, no DB mutation)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.ingestion.services.ncert_books_inventory import scan_ncert_books
from app.modules.ingestion.services.ncert_canonical_source import (
    NCERT_SOURCE_MISSING,
    NCERT_SOURCE_NOT_ALLOWED,
    NCERT_SOURCE_NOT_PDF,
    NcertSourceError,
    assert_blueprint_ncert_source,
    assert_ncert_generation_root,
    is_allowed_ncert_source,
    validate_ncert_generation_source,
)


def _write_pdf(path: Path, body: bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


@pytest.fixture
def ncert_root(tmp_path: Path) -> Path:
    root = tmp_path / "NCERT Books"
    root.mkdir()
    return root


def test_accepts_pdf_inside_canonical_root(ncert_root: Path):
    pdf = _write_pdf(ncert_root / "Class 11" / "Physics" / "keph101.pdf")
    assert is_allowed_ncert_source(pdf, root=ncert_root) is True
    validated = validate_ncert_generation_source(pdf, root=ncert_root)
    assert validated.resolved_path == pdf.resolve()
    assert validated.relative_posix.endswith("keph101.pdf")


def test_rejects_pdf_outside_root(ncert_root: Path, tmp_path: Path):
    outside = _write_pdf(tmp_path / "elsewhere" / "chapter.pdf")
    assert is_allowed_ncert_source(outside, root=ncert_root) is False
    with pytest.raises(NcertSourceError) as exc:
        validate_ncert_generation_source(outside, root=ncert_root)
    assert exc.value.code == NCERT_SOURCE_NOT_ALLOWED


def test_rejects_similar_prefix_path(tmp_path: Path):
    """String-prefix bypass: 'NCERT Books2' must not match 'NCERT Books'."""
    root = tmp_path / "NCERT Books"
    decoy = tmp_path / "NCERT Books2"
    root.mkdir()
    decoy.mkdir()
    outside = _write_pdf(decoy / "Class 11" / "Physics" / "keph101.pdf")
    assert is_allowed_ncert_source(outside, root=root) is False
    with pytest.raises(NcertSourceError) as exc:
        validate_ncert_generation_source(outside, root=root)
    assert exc.value.code == NCERT_SOURCE_NOT_ALLOWED


def test_rejects_missing_pdf(ncert_root: Path):
    missing = ncert_root / "Class 11" / "Physics" / "missing.pdf"
    with pytest.raises(NcertSourceError) as exc:
        validate_ncert_generation_source(missing, root=ncert_root)
    assert exc.value.code == NCERT_SOURCE_MISSING


def test_rejects_non_pdf(ncert_root: Path):
    txt = ncert_root / "Class 11" / "Physics" / "notes.txt"
    txt.parent.mkdir(parents=True)
    txt.write_text("not a pdf", encoding="utf-8")
    with pytest.raises(NcertSourceError) as exc:
        validate_ncert_generation_source(txt, root=ncert_root)
    assert exc.value.code == NCERT_SOURCE_NOT_PDF


def test_rejects_path_traversal(ncert_root: Path, tmp_path: Path):
    outside = _write_pdf(tmp_path / "secret.pdf")
    # Relative escape from inside root
    with pytest.raises(NcertSourceError) as exc:
        validate_ncert_generation_source("../secret.pdf", root=ncert_root)
    assert exc.value.code == NCERT_SOURCE_NOT_ALLOWED
    assert outside.exists()


def test_windows_path_normalization(ncert_root: Path):
    pdf = _write_pdf(ncert_root / "Class 12" / "Biology" / "lebo101.pdf")
    mixed = str(pdf).replace("/", "\\") if "\\" not in str(pdf) else str(pdf)
    validated = validate_ncert_generation_source(mixed, root=ncert_root)
    assert validated.resolved_path == pdf.resolve()


def test_blueprint_with_canonical_source_accepts(ncert_root: Path):
    pdf = _write_pdf(ncert_root / "Class 11" / "Chemistry" / "kech101.pdf")
    result = assert_blueprint_ncert_source(
        {"ncert_derived": True, "ncert_source_path": str(pdf)},
        provenance_tier="authoritative",
        root=ncert_root,
    )
    assert result is not None
    assert result.resolved_path == pdf.resolve()


def test_blueprint_with_study_material_source_rejects(ncert_root: Path, tmp_path: Path):
    legacy = _write_pdf(tmp_path / "StudyMaterial" / "Physics" / "Class 11-Physics" / "ch1.pdf")
    with pytest.raises(NcertSourceError) as exc:
        assert_blueprint_ncert_source(
            {"ncert_derived": True, "ncert_source_path": str(legacy)},
            provenance_tier="authoritative",
            root=ncert_root,
        )
    assert exc.value.code == NCERT_SOURCE_NOT_ALLOWED


def test_generation_cannot_proceed_without_approved_source(ncert_root: Path):
    with pytest.raises(NcertSourceError) as exc:
        assert_blueprint_ncert_source(
            {"ncert_derived": True},
            provenance_tier="authoritative",
            root=ncert_root,
        )
    assert exc.value.code == NCERT_SOURCE_MISSING


def test_non_ncert_blueprint_skips_source_requirement(ncert_root: Path):
    assert assert_blueprint_ncert_source({"question_format": "mcq"}, provenance_tier="ai", root=ncert_root) is None


def test_inventory_detects_duplicate_chapter(ncert_root: Path):
    _write_pdf(ncert_root / "Class 11" / "Physics" / "a" / "keph101.pdf")
    _write_pdf(ncert_root / "Class 11" / "Physics" / "b" / "keph101.pdf")
    report = scan_ncert_books(root=ncert_root, compute_hashes=False)
    dups = [e for e in report.entries if e.status == "duplicate_chapter"]
    assert len(dups) == 2


def test_inventory_part_volumes_are_not_false_duplicates(ncert_root: Path):
    """Part I Ch1 and Part II Ch1 are distinct NCERT identities."""
    _write_pdf(ncert_root / "Class 11" / "Physics" / "p1" / "keph101.pdf")
    _write_pdf(ncert_root / "Class 11" / "Physics" / "p2" / "keph201.pdf")
    report = scan_ncert_books(root=ncert_root, compute_hashes=False)
    assert all(e.status != "duplicate_chapter" for e in report.entries)
    assert {e.part_number for e in report.entries if e.kind == "chapter"} == {1, 2}

def test_inventory_deterministic(ncert_root: Path):
    _write_pdf(ncert_root / "Class 11" / "Biology" / "kebo105.pdf")
    a = scan_ncert_books(root=ncert_root, compute_hashes=True).to_dict()
    b = scan_ncert_books(root=ncert_root, compute_hashes=True).to_dict()
    assert a["total_pdfs"] == b["total_pdfs"]
    assert [e["relative_path"] for e in a["matrix"]["Class 11/Biology"]["entries"]] == [
        e["relative_path"] for e in b["matrix"]["Class 11/Biology"]["entries"]
    ]


def test_assert_generation_root_blocks_study_material(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    ncert = tmp_path / "NCERT Books"
    study = tmp_path / "StudyMaterial"
    ncert.mkdir()
    study.mkdir()
    monkeypatch.setenv("NCERT_SOURCE_ROOT", str(ncert))
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(NcertSourceError) as exc:
            assert_ncert_generation_root(study)
        assert exc.value.code == NCERT_SOURCE_NOT_ALLOWED
        assert assert_ncert_generation_root(ncert) == ncert.resolve()
    finally:
        get_settings.cache_clear()


def test_real_ncert_books_directory_scan():
    """Live scan of the project's canonical NCERT Books tree (read-only)."""
    from app.core.config import get_settings
    from app.modules.ingestion.services.ncert_canonical_source import get_ncert_source_root

    get_settings.cache_clear()
    root = get_ncert_source_root()
    if not root.is_dir():
        pytest.skip(f"NCERT Books root not present: {root}")
    report = scan_ncert_books(root=root, compute_hashes=False)
    payload = report.to_dict()
    assert payload["total_pdfs"] >= 1
    # All six subject cells should have at least one PDF in the current corpus.
    for key in (
        "Class 11/Physics",
        "Class 11/Chemistry",
        "Class 11/Biology",
        "Class 12/Physics",
        "Class 12/Chemistry",
        "Class 12/Biology",
    ):
        assert payload["matrix"][key]["total_pdfs"] >= 1, key
    # Guard: every inventoried PDF must be under the canonical root.
    for entry in report.entries:
        assert is_allowed_ncert_source(entry.resolved_path, root=root)