"""Visual asset detection — see ADR-0026.

Two detection methods, both proven by direct manual verification against
real NEET PYQ papers before this module existed (not designed blind):

- ``embedded_image``: pixel-exact, via PyMuPDF's ``get_image_rects`` — every
  raster figure (photos, scanned diagrams) a PDF embeds as an image XObject.
- ``vector_cluster``: a proximity-merge over ``get_drawings()`` paths, for
  diagrams drawn as vector line-art (chemical structures, circuits, graphs).
  This reliably isolates *multi-option grids* (3-4 same-sized diagrams with
  real gaps between them) but a single vector diagram routinely merges with
  ``List-I``/``List-II`` table borders or a page watermark, because both are
  built from the same kind of vector path. Tuning the merge distance to fix
  one case breaks the other — a genuine geometric ambiguity, not a bug.

A cluster that overlaps a known noise region (watermark / footer / banner)
almost entirely is dropped as pure decoration. A cluster that overlaps one
*partially* is ambiguous — kept as a ``NEEDS_MANUAL_BBOX`` candidate (with
its best-guess rect, not a null one) rather than silently dropped or
silently trusted. Only a cluster with no noise overlap at all is
auto-accepted — subject to one more check, below.

``NOISE_REGIONS`` is hardcoded and publisher-specific (see its own
docstring); running this against a *different* publisher's PDF (the NCERT
pilot chapter, not the PW-branded PYQ book this session tuned it against)
confirmed exactly that limitation empirically: NCERT's own running
chapter-name header, repeated on every page, isn't in that list and was
wrongly marked ``AUTO_DETECTED``. Rather than hand-tuning a second
publisher's coordinates into the same hardcoded list (which wouldn't
generalize to a third), ``detect_visual_assets`` runs a cross-page check
instead: an element whose bounding box repeats near-identically across
several pages of the *same* document is decoration — a running
header/footer/watermark — regardless of which publisher's template
produced it. This is a strictly more general signal than any hardcoded
coordinate list and is what actually catches this case.
"""
import hashlib
import math
import os
import uuid
from dataclasses import dataclass

import fitz  # PyMuPDF

# Tuned against this publisher's specific template this session (the
# translucent "PW" watermark, the red "CLICK HERE" footer button, and the
# "Year / NEET Solved Paper" cover banner) — see ADR-0026. This will misfire
# on a different publisher's layout; that's exactly why review_status
# exists, not a general solution to "detect all decoration."
NOISE_REGIONS = [
    (0, 260, 620, 620),
    (150, 770, 350, 860),
    (0, 40, 700, 210),
]

MIN_CLUSTER_DIM = 20
MIN_CLUSTER_AREA = 1200
MAX_BACKGROUND_AREA_FRAC = 0.35
MERGE_GAP = 10
PURE_NOISE_OVERLAP_FRAC = 0.85

# A bounding box repeating at (near-)identical coordinates on at least this
# many pages, or on at least this fraction of the document's pages
# (whichever is smaller — so a 4-page document doesn't need 5 repeats to
# trigger this), is treated as a running header/footer/watermark, not
# unique content, regardless of publisher. "Near-identical" tolerance is
# ROUND_TOLERANCE_PT points, to absorb tiny sub-pixel rendering variance
# between pages.
REPEAT_MIN_PAGE_COUNT = 3
REPEAT_MIN_PAGE_FRACTION = 0.3
ROUND_TOLERANCE_PT = 3.0


@dataclass
class DetectedAsset:
    source_page: int
    bounding_box: tuple[float, float, float, float] | None  # x0, y0, x1, y1 in PDF points
    asset_type: str
    detection_method: str
    review_status: str


def _merge_rects(rects: list[fitz.Rect], gap: float) -> list[fitz.Rect]:
    n = len(rects)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        pi, pj = find(i), find(j)
        if pi != pj:
            parent[pi] = pj

    for i in range(n):
        expanded = fitz.Rect(rects[i].x0 - gap, rects[i].y0 - gap, rects[i].x1 + gap, rects[i].y1 + gap)
        for j in range(i + 1, n):
            if expanded.intersects(rects[j]):
                union(i, j)

    groups: dict[int, list[fitz.Rect]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(rects[i])

    merged = []
    for group in groups.values():
        r = fitz.Rect(group[0])
        for rr in group[1:]:
            r |= rr
        merged.append(r)
    return merged


def _noise_overlap_fraction(rect: fitz.Rect) -> float:
    """Fraction of `rect`'s area covered by any single known noise region."""
    rect_area = rect.width * rect.height
    if rect_area == 0:
        return 0.0
    best = 0.0
    for x0, y0, x1, y1 in NOISE_REGIONS:
        inter = rect & fitz.Rect(x0, y0, x1, y1)
        if inter.width > 0 and inter.height > 0:
            best = max(best, (inter.width * inter.height) / rect_area)
    return best


def detect_embedded_images(page: fitz.Page) -> list[DetectedAsset]:
    assets = []
    for img in page.get_images(full=True):
        xref = img[0]
        for rect in page.get_image_rects(xref):
            assets.append(
                DetectedAsset(
                    source_page=page.number + 1,
                    bounding_box=(rect.x0, rect.y0, rect.x1, rect.y1),
                    asset_type="image",
                    detection_method="embedded_image",
                    review_status="AUTO_DETECTED",
                )
            )
    return assets


def detect_vector_clusters(page: fitz.Page) -> list[DetectedAsset]:
    page_area = page.rect.width * page.rect.height
    paths = page.get_drawings()
    rects = []
    for p in paths:
        r = p["rect"]
        if r.width <= 0 or r.height <= 0:
            continue
        if r.width * r.height > MAX_BACKGROUND_AREA_FRAC * page_area:
            continue  # a background/border rect spanning most of the page, not an asset
        rects.append(r)

    merged = _merge_rects(rects, gap=MERGE_GAP)

    assets = []
    for r in merged:
        if r.width < MIN_CLUSTER_DIM or r.height < MIN_CLUSTER_DIM:
            continue
        if r.width * r.height < MIN_CLUSTER_AREA:
            continue
        near_corner = (
            (r.x0 < 100 or r.x1 > page.rect.width - 100)
            and (r.y0 < 60 or r.y1 > page.rect.height - 60)
            and r.width < 100
            and r.height < 60
        )
        if near_corner:
            continue  # page-number circle / small logo mark, not content

        overlap = _noise_overlap_fraction(r)
        if overlap >= PURE_NOISE_OVERLAP_FRAC:
            continue  # fully explained by a known noise region — nothing to review
        review_status = "NEEDS_MANUAL_BBOX" if overlap > 0 else "AUTO_DETECTED"
        assets.append(
            DetectedAsset(
                source_page=page.number + 1,
                bounding_box=(r.x0, r.y0, r.x1, r.y1),
                asset_type="diagram",
                detection_method="vector_cluster",
                review_status=review_status,
            )
        )
    return assets


def _rounded_bbox_key(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return tuple(round(v / ROUND_TOLERANCE_PT) * ROUND_TOLERANCE_PT for v in bbox)


def _drop_repeated_across_pages(assets: list[DetectedAsset], total_pages: int) -> list[DetectedAsset]:
    """Marks REJECTED (and dedupes to one row) any bounding box that recurs
    at (near-)identical coordinates across enough pages of this document to
    be a running header/footer/watermark rather than unique content — see
    module docstring. Assets from `detect_embedded_images` and
    `detect_vector_clusters` are both eligible; a repeated decorative
    element could be either."""
    if total_pages < 2:
        return assets

    threshold = max(2, min(REPEAT_MIN_PAGE_COUNT, math.ceil(total_pages * REPEAT_MIN_PAGE_FRACTION)))

    groups: dict[tuple, list[DetectedAsset]] = {}
    for asset in assets:
        if asset.bounding_box is None:
            continue
        groups.setdefault(_rounded_bbox_key(asset.bounding_box), []).append(asset)

    repeated_keys = {key for key, group in groups.items() if len({a.source_page for a in group}) >= threshold}
    if not repeated_keys:
        return assets

    kept = []
    seen_repeated_keys: set[tuple] = set()
    for asset in assets:
        key = _rounded_bbox_key(asset.bounding_box) if asset.bounding_box else None
        if key in repeated_keys:
            if key in seen_repeated_keys:
                continue  # one representative row per repeated element, not one per page
            seen_repeated_keys.add(key)
            kept.append(
                DetectedAsset(
                    source_page=asset.source_page,
                    bounding_box=asset.bounding_box,
                    asset_type=asset.asset_type,
                    detection_method=asset.detection_method,
                    review_status="REJECTED",
                )
            )
        else:
            kept.append(asset)
    return kept


def detect_visual_assets(pdf_path: str) -> list[DetectedAsset]:
    doc = fitz.open(pdf_path)
    try:
        assets = []
        for page in doc:
            assets.extend(detect_embedded_images(page))
            assets.extend(detect_vector_clusters(page))
        return _drop_repeated_across_pages(assets, total_pages=len(doc))
    finally:
        doc.close()


def crop_and_store(pdf_path: str, asset: DetectedAsset, out_dir: str, *, dpi: int = 300, pad: float = 6.0) -> dict:
    """Renders `asset`'s bounding box to a PNG under `out_dir` and returns the
    fields the caller (IngestionPipelineService) needs to fill in on the
    VisualAsset row: storage_path, content_hash, width_px, height_px.
    Never called for a NEEDS_MANUAL_BBOX row with no confirmed box — that's
    the caller's decision, not this function's."""
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        page = doc[asset.source_page - 1]
        x0, y0, x1, y1 = asset.bounding_box
        rect = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad) & page.rect
        pix = page.get_pixmap(dpi=dpi, clip=rect)
        filename = f"{uuid.uuid4().hex}.png"
        out_path = os.path.join(out_dir, filename)
        pix.save(out_path)
        with open(out_path, "rb") as f:
            content_hash = hashlib.sha256(f.read()).hexdigest()
        return {
            "storage_path": out_path,
            "content_hash": content_hash,
            "width_px": pix.width,
            "height_px": pix.height,
            "render_dpi": dpi,
        }
    finally:
        doc.close()
