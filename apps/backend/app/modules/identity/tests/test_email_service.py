import pytest
import structlog

from app.core.config import get_settings
from app.modules.identity.services import email_service

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _set_environment(monkeypatch, value: str):
    monkeypatch.setenv("ENVIRONMENT", value)
    if value == "production":
        # A real-looking secret so this test exercises email_service's own
        # production gate, not the separate fail-fast check in test_config.py.
        monkeypatch.setenv("JWT_SECRET", "a-real-random-secret-that-is-long-enough-1234")
    get_settings.cache_clear()


async def test_dev_mode_logs_the_link_for_testability(monkeypatch):
    _set_environment(monkeypatch, "development")
    with structlog.testing.capture_logs() as logs:
        await email_service.send_password_reset_email(to="user@example.com", token="secret-token-123")

    assert any("secret-token-123" in str(entry) for entry in logs)
    get_settings.cache_clear()


async def test_production_never_logs_the_raw_token(monkeypatch):
    _set_environment(monkeypatch, "production")
    with structlog.testing.capture_logs() as logs:
        await email_service.send_password_reset_email(to="user@example.com", token="secret-token-123")
        await email_service.send_verification_email(to="user@example.com", token="another-secret-456")

    combined = str(logs)
    assert "secret-token-123" not in combined
    assert "another-secret-456" not in combined
    get_settings.cache_clear()


async def test_production_never_logs_otp_codes(monkeypatch):
    _set_environment(monkeypatch, "production")
    with structlog.testing.capture_logs() as logs:
        await email_service.send_email_verification_otp_email(to="user@example.com", code="123456")
        await email_service.send_login_otp_email(to="user@example.com", code="654321")

    combined = str(logs)
    assert "123456" not in combined
    assert "654321" not in combined
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("sender", "kwargs", "expected_subject"),
    [
        (
            email_service.send_welcome_email,
            {"to": "user@example.com", "first_name": "Asha", "email_verified": False},
            "Welcome to NEET Preparation — Your Learning Journey Starts Here",
        ),
        (
            email_service.send_verification_email,
            {"to": "user@example.com", "token": "tok"},
            "Verify Your Email Address — NEET Preparation",
        ),
        (
            email_service.send_email_verification_otp_email,
            {"to": "user@example.com", "code": "111111"},
            "Your Email Verification Code — NEET Preparation",
        ),
        (
            email_service.send_login_otp_email,
            {"to": "user@example.com", "code": "222222"},
            "Your Login Code — NEET Preparation",
        ),
        (
            email_service.send_password_reset_email,
            {"to": "user@example.com", "token": "tok"},
            "Reset Your NEET Preparation Password",
        ),
        (
            email_service.send_password_changed_email,
            {"to": "user@example.com", "when_text": "01 Jan 2026, 00:00 UTC"},
            "Your Password Was Changed — NEET Preparation",
        ),
        (
            email_service.send_new_login_alert_email,
            {"to": "user@example.com", "when_text": "01 Jan 2026, 00:00 UTC", "ip_address": "1.2.3.4", "device_text": "Chrome"},
            "New Login to Your NEET Preparation Account",
        ),
        (
            email_service.send_email_changed_email,
            {"to": "user@example.com", "new_email_masked": "a***@example.com", "when_text": "01 Jan 2026, 00:00 UTC"},
            "Your Email Address Was Changed — NEET Preparation",
        ),
        (
            email_service.send_mobile_changed_email,
            {"to": "user@example.com", "new_mobile_masked": "******1234", "when_text": "01 Jan 2026, 00:00 UTC"},
            "Your Mobile Number Was Changed — NEET Preparation",
        ),
    ],
)
async def test_exact_subject_per_template(monkeypatch, sender, kwargs, expected_subject):
    """Every template must use the exact subject line specified — a
    mismatch here is a spec violation, not a style nit."""
    _set_environment(monkeypatch, "development")
    with structlog.testing.capture_logs() as logs:
        await sender(**kwargs)
    get_settings.cache_clear()
    assert any(entry.get("subject") == expected_subject for entry in logs), logs


async def test_html_and_plaintext_both_render_and_contain_no_html_in_text(monkeypatch):
    from app.modules.identity.services import email_templates as tpl

    subject, html, text = tpl.login_otp_email(code="424242", expires_in_minutes=10, support_email="support@trinetralab.net")
    assert subject == "Your Login Code — NEET Preparation"
    assert "<html" in html.lower()
    assert "424242" in html
    assert "424242" in text
    assert "<" not in text  # plain-text fallback must not leak markup
    assert "support@trinetralab.net" in html
    assert "support@trinetralab.net" in text


async def test_support_contact_present_but_real_mailbox_never_exposed():
    """support@trinetralab.net is the public-facing contact address and must
    appear in every template's footer / Reply-To — but the real underlying
    mailbox it forwards to (smtp_from) must never be exposed to students."""
    from app.core.config import get_settings
    from app.modules.identity.services import email_templates as tpl

    settings = get_settings()
    assert settings.support_email == "support@trinetralab.net"

    for _subject, html, text in (
        tpl.welcome_email(first_name="A", dashboard_url="https://x/y", email_verified=True, support_email=settings.support_email),
        tpl.password_changed_email(when_text="now", support_email=settings.support_email),
        tpl.new_login_alert_email(
            when_text="now", ip_address="1.2.3.4", device_text="Chrome", support_email=settings.support_email
        ),
    ):
        assert "support@trinetralab.net" in html
        assert "support@trinetralab.net" in text
        if settings.smtp_from:
            assert settings.smtp_from not in html
            assert settings.smtp_from not in text


def test_real_smtp_connection_class_is_replaced_under_pytest():
    """Direct proof the conftest.py autouse guard is active in this process:
    smtplib.SMTP itself must be the interception stub, not the real class —
    this is what makes an actual network connection impossible regardless of
    what any test, debug script, or verification helper does afterward."""
    import smtplib

    from conftest import RealSmtpAttemptedError

    with pytest.raises(RealSmtpAttemptedError):
        smtplib.SMTP("smtp.gmail.com", 587)
    with pytest.raises(RealSmtpAttemptedError):
        smtplib.SMTP_SSL("smtp.gmail.com", 465)


async def test_email_send_goes_through_the_blocked_path_when_smtp_configured(monkeypatch):
    """Regression test for the accidental-real-send incident: even with
    SMTP_* looking fully configured (as it would from a real .env), sending
    must hit the interception guard — proven by asserting on the caught
    exception's type, not merely "some" failure log."""
    monkeypatch.setattr(get_settings(), "smtp_host", "smtp.gmail.com", raising=False)
    monkeypatch.setattr(get_settings(), "smtp_from", "someone@example.com", raising=False)

    from conftest import RealSmtpAttemptedError

    captured: list[BaseException] = []
    original_error = email_service.logger.error

    def _capture_and_delegate(event, **kwargs):
        exc = kwargs.get("exc_info")
        if exc is True:
            import sys

            captured.append(sys.exc_info()[1])
        return original_error(event, **kwargs)

    monkeypatch.setattr(email_service.logger, "error", _capture_and_delegate)

    await email_service.send_password_reset_email(to="victim@example.com", token="tok")

    assert captured and isinstance(captured[0], RealSmtpAttemptedError), captured
    get_settings.cache_clear()


async def test_email_send_failure_is_caught_and_logged_not_raised(monkeypatch):
    # SMTP is a development-only fallback (never attempted in production —
    # see email_service.py's module docstring on Railway's outbound-SMTP
    # block), so this exercises the failure path via that fallback in a
    # non-production environment, not in production.
    _set_environment(monkeypatch, "development")
    monkeypatch.setattr(get_settings(), "smtp_host", "localhost", raising=False)
    monkeypatch.setattr(get_settings(), "smtp_from", "no-reply@example.com", raising=False)

    def _boom(*args, **kwargs):
        raise ConnectionRefusedError("no smtp server here")

    monkeypatch.setattr(email_service.smtplib, "SMTP", _boom)

    with structlog.testing.capture_logs() as logs:
        # Must not raise — callers (register/login/etc.) never fail the HTTP
        # request just because the notification email couldn't be sent.
        await email_service.send_password_changed_email(to="user@example.com", when_text="now")

    assert any(entry.get("event") == "email_send_failed" for entry in logs)
    get_settings.cache_clear()


async def test_production_never_attempts_smtp_even_when_configured(monkeypatch):
    """The whole point of the Resend migration: production must never touch
    SMTP, even if SMTP_* looks fully configured (e.g. a stale .env value) —
    Railway blocks outbound SMTP ports and this used to cause an ~8s hang
    per request. With no provider configured either, production must log
    email_not_configured and attempt the admin alert, and never touch
    smtplib at all."""
    _set_environment(monkeypatch, "production")
    monkeypatch.setattr(get_settings(), "smtp_host", "smtp.gmail.com", raising=False)
    monkeypatch.setattr(get_settings(), "smtp_from", "someone@example.com", raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("smtplib.SMTP must never be reached in production")

    monkeypatch.setattr(email_service.smtplib, "SMTP", _boom)

    with structlog.testing.capture_logs() as logs:
        await email_service.send_password_changed_email(to="user@example.com", when_text="now")

    assert any(entry.get("event") == "email_not_configured" for entry in logs)
    get_settings.cache_clear()
