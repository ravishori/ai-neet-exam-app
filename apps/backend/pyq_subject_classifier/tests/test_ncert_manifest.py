from pyq_subject_classifier.config import NCERT_ROOT


def test_ncert_root_exists():
    assert NCERT_ROOT.exists(), f"NCERT_ROOT not found: {NCERT_ROOT}"


def test_ncert_root_has_pdfs():
    pdfs = list(NCERT_ROOT.rglob("*.pdf"))
    assert len(pdfs) > 0


def test_manifest_subject_class_from_directory_structure(tmp_path, monkeypatch):
    from pyq_subject_classifier import ncert_manifest

    # Build a tiny fake NCERT tree to test the directory-based mapping logic
    # in isolation, without depending on the real 100-file corpus.
    fake_root = tmp_path / "NCERT Books"
    physics_dir = fake_root / "Class 11" / "Physics" / "keph1dd"
    physics_dir.mkdir(parents=True)
    fake_pdf = physics_dir / "keph101.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4\n%%EOF")  # minimal, not fitz-openable

    monkeypatch.setattr(ncert_manifest, "NCERT_ROOT", fake_root)
    manifest = ncert_manifest.build_manifest()
    assert manifest["file_count"] == 1
    entry = manifest["files"][0]
    assert entry["subject"] == "Physics"
    assert entry["class"] == "11"
    assert entry["verified"] is True
    assert len(entry["checksum_sha256"]) == 64
