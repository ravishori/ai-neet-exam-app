"""Unit tests for NEET StudyMaterial path parsing (ADR-0030)."""

from pathlib import Path

import pytest

from app.modules.ingestion.services.pdf_extraction_service import compute_checksum
from app.modules.ingestion.services.study_material_path_parser import (
    StudyMaterialPathError,
    is_under_excluded_root,
    parse_study_material_path,
    resolve_under_root,
)


@pytest.mark.parametrize(
    ("path", "subject", "class_level"),
    [
        ("Physics/Class 11-Physics/foo.pdf", "PHYSICS", "11"),
        ("Physics/Class 12-Physics/foo.pdf", "PHYSICS", "12"),
        ("Chemistry/Class 11- Chemistry/foo.pdf", "CHEMISTRY", "11"),
        ("Chemistry/Class 12- Chemistry/foo.pdf", "CHEMISTRY", "12"),
        ("Biology/Class 11-Biology/foo.pdf", "BIOLOGY", "11"),
        ("Biology/Class 12-Biology/foo.pdf", "BIOLOGY", "12"),
    ],
)
def test_parse_neet_subject_class_paths(path: str, subject: str, class_level: str):
    parsed = parse_study_material_path(path)
    assert parsed.subject_code == subject
    assert parsed.class_level == class_level
    assert parsed.file_name == "foo.pdf"
    assert parsed.relative_source_path == path.replace("\\", "/")


def test_parse_normalizes_chemistry_hyphen_spacing():
    """Real tree uses 'Class 11- Chemistry' (space after hyphen)."""
    parsed = parse_study_material_path("Chemistry/Class 11- Chemistry/ncert-chapter.pdf")
    assert parsed.subject_code == "CHEMISTRY"
    assert parsed.class_level == "11"
    assert parsed.file_name == "ncert-chapter.pdf"


def test_parse_is_case_insensitive_for_subject_root():
    parsed = parse_study_material_path("physics/Class 12-Physics/foo.pdf")
    assert parsed.subject_code == "PHYSICS"
    assert parsed.class_level == "12"


def test_maths_paths_rejected():
    with pytest.raises(StudyMaterialPathError, match="excluded"):
        parse_study_material_path("Maths/foo.pdf")
    with pytest.raises(StudyMaterialPathError, match="excluded"):
        parse_study_material_path("Maths/chapter/foo.pdf")
    assert is_under_excluded_root("Maths/foo.pdf") is True


def test_uploads_paths_rejected():
    with pytest.raises(StudyMaterialPathError, match="excluded"):
        parse_study_material_path("Uploads/foo.pdf")
    with pytest.raises(StudyMaterialPathError, match="excluded"):
        parse_study_material_path("Uploads/nested/foo.pdf")
    assert is_under_excluded_root("Uploads/nested/foo.pdf") is True


def test_path_traversal_rejected():
    with pytest.raises(StudyMaterialPathError, match="traversal"):
        parse_study_material_path("Physics/../Maths/foo.pdf")
    with pytest.raises(StudyMaterialPathError, match="traversal"):
        parse_study_material_path("Physics/Class 11-Physics/../../etc/passwd.pdf")


def test_resolve_under_root_rejects_escape(tmp_path: Path):
    root = tmp_path / "StudyMaterial"
    root.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4")
    with pytest.raises(StudyMaterialPathError, match="escapes"):
        resolve_under_root(root, outside)
    with pytest.raises(StudyMaterialPathError):
        resolve_under_root(root, Path("../outside.pdf"))


def test_resolve_under_root_accepts_nested(tmp_path: Path):
    root = tmp_path / "StudyMaterial"
    nested = root / "Physics" / "Class 11-Physics"
    nested.mkdir(parents=True)
    pdf = nested / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    resolved = resolve_under_root(root, pdf)
    assert resolved == pdf.resolve()


def test_checksum_same_and_different(tmp_path: Path):
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    c = tmp_path / "c.pdf"
    a.write_bytes(b"%PDF-same")
    b.write_bytes(b"%PDF-same")
    c.write_bytes(b"%PDF-other")
    assert compute_checksum(str(a)) == compute_checksum(str(b))
    assert compute_checksum(str(a)) != compute_checksum(str(c))


def test_unsupported_extension_rejected():
    with pytest.raises(StudyMaterialPathError, match="unsupported file type"):
        parse_study_material_path("Physics/Class 11-Physics/notes.docx")


def test_unknown_subject_root_rejected():
    with pytest.raises(StudyMaterialPathError, match="unsupported subject"):
        parse_study_material_path("Geography/Class 11-Geography/foo.pdf")
