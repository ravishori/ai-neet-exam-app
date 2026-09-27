"""Regression test: auth cookies must carry the shared parent Domain when the
web app and API live on different subdomains, or a successful backend login
can never be observed by the frontend (session cookie never reaches the web
app's own origin). No DB needed — set_auth_cookies only touches a Response.
"""

from starlette.responses import Response

from app.modules.identity import cookies as cookies_mod
from app.modules.identity.cookies import clear_auth_cookies, set_auth_cookies


def _set_cookie_headers(response: Response) -> list[str]:
    return [v for k, v in response.raw_headers if k.decode().lower() == "set-cookie"]


def test_set_auth_cookies_carries_configured_domain(monkeypatch):
    monkeypatch.setattr(cookies_mod.settings, "cookie_domain", ".example.com")

    response = Response()
    set_auth_cookies(response, access_token="a", refresh_token="r", csrf_token="c")

    headers = [h.decode() for h in _set_cookie_headers(response)]
    assert len(headers) == 3
    for header in headers:
        assert "Domain=.example.com" in header, header


def test_set_auth_cookies_omits_domain_when_unset(monkeypatch):
    """Dev default: no cookie_domain configured => scoped to the exact host,
    matching today's local-dev behavior (frontend/backend on localhost)."""
    monkeypatch.setattr(cookies_mod.settings, "cookie_domain", "")

    response = Response()
    set_auth_cookies(response, access_token="a", refresh_token="r", csrf_token="c")

    headers = [h.decode() for h in _set_cookie_headers(response)]
    assert len(headers) == 3
    for header in headers:
        assert "Domain=" not in header, header


def test_clear_auth_cookies_matches_configured_domain(monkeypatch):
    """Deleting a cookie with a mismatched Domain is a no-op in real browsers
    — the delete must use the same Domain the cookie was set with."""
    monkeypatch.setattr(cookies_mod.settings, "cookie_domain", ".example.com")

    response = Response()
    clear_auth_cookies(response)

    headers = [h.decode() for h in _set_cookie_headers(response)]
    assert len(headers) == 3
    for header in headers:
        assert "Domain=.example.com" in header, header
