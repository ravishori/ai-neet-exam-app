"""Admin rich-content editor image uploads (POST/GET /api/v1/cms/images):
signature validation, size limit, re-encoding, path-traversal safety,
permission gating."""

from __future__ import annotations

import io

import pytest

from conftest import csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _tiny_png(*, alpha: bool) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    mode = "RGBA" if alpha else "RGB"
    color = (200, 50, 50, 128) if alpha else (200, 50, 50)
    Image.new(mode, (4, 4), color=color).save(buf, format="PNG")
    return buf.getvalue()


async def test_upload_transparent_png_round_trips_as_png(client, db_session, register_user):
    """An image with an alpha channel must stay PNG (JPEG has no
    transparency) -- proves the format decision is content-driven, not
    just a blind pass-through of the original bytes."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.post(
        "/api/v1/cms/images",
        files={"file": ("photo.png", _tiny_png(alpha=True), "image/png")},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["url"].startswith("/api/v1/cms/images/")
    assert data["filename"] != "photo.png"  # UUID-prefixed, never the original filename verbatim
    assert data["filename"].endswith(".png")

    fetched = await client.get(data["url"])
    assert fetched.status_code == 200, fetched.text
    assert fetched.headers["content-type"] == "image/png"
    from PIL import Image

    reloaded = Image.open(io.BytesIO(fetched.content))
    reloaded.verify()
    assert reloaded.format == "PNG"


async def test_upload_opaque_image_is_reencoded_to_jpeg(client, db_session, register_user):
    """An opaque image (no alpha) is re-compressed to JPEG -- proves this
    is a genuine re-encode, not a verbatim pass-through of the uploaded
    bytes (the original was PNG; the stored/served file is a different
    format and a different byte sequence)."""
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    original = _tiny_png(alpha=False)
    resp = await client.post(
        "/api/v1/cms/images",
        files={"file": ("photo.png", original, "image/png")},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["filename"].endswith(".jpeg")

    fetched = await client.get(data["url"])
    assert fetched.status_code == 200, fetched.text
    assert fetched.headers["content-type"] == "image/jpeg"
    assert fetched.content != original
    from PIL import Image

    reloaded = Image.open(io.BytesIO(fetched.content))
    reloaded.verify()
    assert reloaded.format == "JPEG"


async def test_upload_rejects_non_image_bytes(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.post(
        "/api/v1/cms/images",
        files={"file": ("not-an-image.png", b"this is plainly not an image file", "image/png")},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["errors"][0]["code"] == "INVALID_FILE_TYPE"


async def test_upload_rejects_file_over_size_limit(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    oversized = b"\x00" * (5 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/v1/cms/images",
        files={"file": ("big.png", oversized, "image/png")},
        headers=csrf_headers(client),
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["errors"][0]["code"] == "FILE_TOO_LARGE"


async def test_upload_requires_authentication(client):
    resp = await client.post("/api/v1/cms/images", files={"file": ("x.png", _tiny_png(alpha=True), "image/png")})
    assert resp.status_code == 401


async def test_image_fetch_rejects_path_traversal(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get("/api/v1/cms/images/..%2F..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code == 404


async def test_image_fetch_404s_for_unknown_filename(client, db_session, register_user):
    await register_user(client, role_codes=["CONTENT_MANAGER"], db_session=db_session)
    resp = await client.get("/api/v1/cms/images/does-not-exist.png")
    assert resp.status_code == 404
