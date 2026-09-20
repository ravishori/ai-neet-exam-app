from pyq_subject_classifier.ncert_manifest import load_or_build_manifest
from pyq_subject_classifier.phase2_index import build_phase2_index


def test_phase2_index_reuses_cached_page_text_not_pdfs(monkeypatch):
    """build_phase2_index must never call fitz.open — it only reads the
    already-cached Phase 1 page-text JSON files."""
    import fitz

    def _forbidden_open(*a, **kw):
        raise AssertionError("phase2 index rebuild must not re-open PDFs")

    monkeypatch.setattr(fitz, "open", _forbidden_open)

    manifest = load_or_build_manifest()  # cached — does not call fitz.open again
    idx = build_phase2_index(manifest)
    assert len(idx.chapters) > 0


def test_phase2_chapters_grouped_by_subject():
    manifest = load_or_build_manifest()
    idx = build_phase2_index(manifest)
    physics_chapters = idx.chapters_for_subject("Physics")
    chemistry_chapters = idx.chapters_for_subject("Chemistry")
    biology_chapters = idx.chapters_for_subject("Biology")
    assert len(physics_chapters) > 0
    assert len(chemistry_chapters) > 0
    assert len(biology_chapters) > 0
    assert all(c.subject == "Physics" for c in physics_chapters)
