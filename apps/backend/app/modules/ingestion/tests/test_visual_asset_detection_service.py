"""Unit tests for the two detection methods in ADR-0026, against synthetic
PDFs built in-memory with PyMuPDF itself — self-contained and portable,
rather than depending on an external publisher's PDF outside the repo. Each
fixture reproduces one of the three real cases this session's manual work
actually encountered before this service existed."""
import fitz
import pytest

from app.modules.ingestion.services.visual_asset_detection_service import (
    NOISE_REGIONS,
    detect_embedded_images,
    detect_vector_clusters,
    detect_visual_assets,
)


def _blank_page(width: int = 600, height: int = 800) -> fitz.Page:
    doc = fitz.open()
    return doc.new_page(width=width, height=height)


def _draw_rect(page: fitz.Page, rect: fitz.Rect) -> None:
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(color=(0, 0, 0))
    shape.commit()


def test_embedded_image_is_auto_detected_with_pixel_exact_bbox():
    # Case 1: a clean embedded raster figure (e.g. the Botany seed diagram).
    page = _blank_page()
    pix = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, 50, 50))
    pix.set_rect(pix.irect, (128,))
    target = fitz.Rect(120, 150, 220, 250)
    page.insert_image(target, pixmap=pix)

    assets = detect_embedded_images(page)

    assert len(assets) == 1
    assert assets[0].detection_method == "embedded_image"
    assert assets[0].review_status == "AUTO_DETECTED"
    assert assets[0].asset_type == "image"
    x0, y0, x1, y1 = assets[0].bounding_box
    assert (x0, y0, x1, y1) == pytest.approx((target.x0, target.y0, target.x1, target.y1))


def test_isolated_multi_option_grid_is_cleanly_clustered():
    # Case 2: a 4-way option grid with real gaps (e.g. Physics Q28's four
    # graphs) — each option must become its own AUTO_DETECTED cluster, not
    # merge into one blob or disappear.
    page = _blank_page()
    # Placed in the one band a 600x800 page's NOISE_REGIONS leave clear
    # (below the top banner at y<210, above the "PW" watermark at y>=260,
    # and above the footer at y>=770): y in [630, 760].
    boxes = [
        fitz.Rect(100, 630, 160, 690),
        fitz.Rect(250, 630, 310, 690),
        fitz.Rect(100, 700, 160, 760),
        fitz.Rect(250, 700, 310, 760),
    ]
    for box in boxes:
        _draw_rect(page, box)

    assets = detect_vector_clusters(page)

    assert len(assets) == 4
    assert all(a.detection_method == "vector_cluster" for a in assets)
    assert all(a.review_status == "AUTO_DETECTED" for a in assets)


def test_diagram_entangled_with_a_noise_region_needs_manual_bbox():
    # Case 3: a lone vector diagram whose merged cluster partially overlaps
    # a known noise region (e.g. Chemistry Q8's structures, which shared
    # geometry with the page watermark) — flagged for review, not trusted
    # blindly and not silently dropped.
    page = _blank_page()
    noise_x0, noise_y0, noise_x1, noise_y1 = NOISE_REGIONS[0]
    # straddles the noise region's left edge: half in, half out
    straddling = fitz.Rect(noise_x0 - 40, noise_y0 + 20, noise_x0 + 40, noise_y0 + 100)
    _draw_rect(page, straddling)

    assets = detect_vector_clusters(page)

    assert len(assets) == 1
    assert assets[0].review_status == "NEEDS_MANUAL_BBOX"
    assert assets[0].bounding_box is not None  # a best-guess candidate, not null


def test_cluster_fully_inside_a_noise_region_is_dropped_as_pure_decoration():
    # A rect entirely within the watermark/table-border noise zone (e.g. the
    # page's own translucent logo) shouldn't produce a row at all — there's
    # nothing real to review.
    page = _blank_page()
    noise_x0, noise_y0, noise_x1, noise_y1 = NOISE_REGIONS[0]
    fully_inside = fitz.Rect(noise_x0 + 50, noise_y0 + 50, noise_x0 + 150, noise_y0 + 150)
    _draw_rect(page, fully_inside)

    assets = detect_vector_clusters(page)

    assert assets == []


def test_small_corner_marks_are_excluded():
    # Page-number circles / small logo marks pinned to a page corner are not
    # educational content.
    page = _blank_page()
    _draw_rect(page, fitz.Rect(10, 10, 40, 35))  # top-left corner, small

    assets = detect_vector_clusters(page)

    assert assets == []


def test_page_with_no_visual_content_yields_nothing():
    page = _blank_page()
    assert detect_embedded_images(page) == []
    assert detect_vector_clusters(page) == []


def test_running_header_repeated_across_pages_is_rejected_not_auto_detected(tmp_path):
    # Reproduces the real gap found running this service against the NCERT
    # pilot chapter: a chapter-name banner repeated identically on every
    # page isn't in NOISE_REGIONS (tuned to a different publisher's PDF),
    # so per-page detection alone marks it AUTO_DETECTED. The cross-page
    # check must catch it regardless of which publisher's layout it is.
    doc = fitz.open()
    header_rect = fitz.Rect(400, 700, 580, 760)  # clear of every hardcoded NOISE_REGIONS box
    for page_index in range(5):
        page = doc.new_page(width=600, height=800)
        _draw_rect(page, header_rect)
        if page_index == 2:
            # one genuine, unique diagram on only one page, clear of every
            # hardcoded NOISE_REGIONS box (same safe band as the grid test)
            _draw_rect(page, fitz.Rect(100, 630, 200, 690))

    pdf_path = tmp_path / "synthetic_multipage.pdf"
    doc.save(str(pdf_path))
    doc.close()

    assets = detect_visual_assets(str(pdf_path))

    header_assets = [a for a in assets if a.bounding_box[:2] == pytest.approx((400.0, 700.0))]
    unique_assets = [a for a in assets if a.bounding_box[:2] == pytest.approx((100.0, 630.0))]

    assert len(header_assets) == 1  # deduped to one representative row, not five
    assert header_assets[0].review_status == "REJECTED"
    assert len(unique_assets) == 1
    assert unique_assets[0].review_status == "AUTO_DETECTED"
