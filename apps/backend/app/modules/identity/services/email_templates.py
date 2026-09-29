"""Centralized transactional-email templates: shared layout + one render
function per event, each returning (subject, html, text). No network I/O
here — email_service.py owns sending. Never pass a plaintext OTP/token into
anything logged; these functions only build message bodies.

support@trinetralab.net is the public-facing student support/contact
address — an existing forwarding alias onto the real mailbox, not a
separate dedicated inbox. It is used as Reply-To and in the footer; the
real underlying mailbox is never exposed to students.
"""

from __future__ import annotations

from html import escape

COMPANY_NAME = "Trinetra Digital Lab"
WEBSITE_URL = "https://trinetralab.net/"
SENDER_DISPLAY_NAME = "NEET Preparation"


def _layout(*, preheader: str, heading: str, body_html: str, cta_url: str | None, cta_label: str | None, support_email: str) -> str:
    cta_html = ""
    if cta_url and cta_label:
        cta_html = f"""
        <tr><td style="padding:24px 0;">
          <a href="{escape(cta_url)}" style="background:#0f766e;color:#ffffff;text-decoration:none;
             padding:12px 24px;border-radius:6px;font-weight:600;display:inline-block;">
            {escape(cta_label)}
          </a>
        </td></tr>"""
    return f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(heading)}</title></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
  <span style="display:none;max-height:0;overflow:hidden;">{escape(preheader)}</span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:560px;background:#ffffff;border-radius:8px;overflow:hidden;">
        <tr><td style="background:#0f172a;padding:20px 32px;">
          <span style="color:#ffffff;font-size:18px;font-weight:700;">NEET Preparation</span>
        </td></tr>
        <tr><td style="padding:32px;">
          <h1 style="margin:0 0 16px;font-size:20px;color:#0f172a;">{escape(heading)}</h1>
          <div style="font-size:15px;line-height:1.6;color:#374151;">{body_html}</div>
          {cta_html}
        </td></tr>
        <tr><td style="background:#f9fafb;padding:20px 32px;font-size:12px;color:#6b7280;border-top:1px solid #e5e7eb;">
          {escape(COMPANY_NAME)}<br>
          Website: <a href="{escape(WEBSITE_URL)}" style="color:#0f766e;">{escape(WEBSITE_URL)}</a><br>
          Support: <a href="mailto:{escape(support_email)}" style="color:#0f766e;">{escape(support_email)}</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _plain_footer(support_email: str) -> str:
    return f"\n\n---\n{COMPANY_NAME}\nWebsite: {WEBSITE_URL}\nSupport: {support_email}\n"


def welcome_email(*, first_name: str, dashboard_url: str, email_verified: bool, support_email: str) -> tuple[str, str, str]:
    subject = "Welcome to NEET Preparation — Your Learning Journey Starts Here"
    name = escape(first_name or "there")
    verify_note_html = (
        ""
        if email_verified
        else "<p>Please verify your email address to secure your account — check your inbox for a separate verification message.</p>"
    )
    body_html = f"""
      <p>Hi {name},</p>
      <p>Your NEET Preparation account is ready. You can start practicing questions, tracking progress, and
      following your personalized study plan right away.</p>
      {verify_note_html}
    """
    html = _layout(
        preheader="Your NEET Preparation account is ready.",
        heading=f"Welcome, {first_name or 'Student'}!",
        body_html=body_html,
        cta_url=dashboard_url,
        cta_label="Go to Dashboard",
        support_email=support_email,
    )
    verify_note_text = "" if email_verified else "\nPlease verify your email address — check your inbox for a verification message.\n"
    text = (
        f"Hi {first_name or 'there'},\n\n"
        "Your NEET Preparation account is ready. Start practicing here:\n"
        f"{dashboard_url}\n"
        f"{verify_note_text}"
        f"{_plain_footer(support_email)}"
    )
    return subject, html, text


def email_verification_email(*, verify_url: str, expires_in_hours: int, support_email: str) -> tuple[str, str, str]:
    subject = "Verify Your Email Address — NEET Preparation"
    body_html = f"""
      <p>Please confirm this is your email address to finish securing your account.</p>
      <p>This link expires in {expires_in_hours} hours.</p>
      <p style="color:#6b7280;font-size:13px;">If you did not create this account, you can safely ignore this email.</p>
    """
    html = _layout(
        preheader="Confirm your email address.",
        heading="Verify Your Email Address",
        body_html=body_html,
        cta_url=verify_url,
        cta_label="Verify Email",
        support_email=support_email,
    )
    text = (
        "Please confirm your email address by opening this link "
        f"(expires in {expires_in_hours} hours):\n\n{verify_url}\n\n"
        "If you did not create this account, ignore this message."
        f"{_plain_footer(support_email)}"
    )
    return subject, html, text


def email_verification_otp_email(*, code: str, expires_in_minutes: int, support_email: str) -> tuple[str, str, str]:
    subject = "Your Email Verification Code — NEET Preparation"
    return _otp_email(
        subject=subject,
        heading="Your Verification Code",
        intro="Use this code to verify your email address.",
        code=code,
        expires_in_minutes=expires_in_minutes,
        support_email=support_email,
    )


def login_otp_email(*, code: str, expires_in_minutes: int, support_email: str) -> tuple[str, str, str]:
    subject = "Your Login Code — NEET Preparation"
    return _otp_email(
        subject=subject,
        heading="Your Login Code",
        intro="Use this code to log in to your account.",
        code=code,
        expires_in_minutes=expires_in_minutes,
        support_email=support_email,
    )


def _otp_email(*, subject: str, heading: str, intro: str, code: str, expires_in_minutes: int, support_email: str) -> tuple[str, str, str]:
    body_html = f"""
      <p>{escape(intro)}</p>
      <p style="font-size:32px;font-weight:700;letter-spacing:6px;color:#0f172a;
         background:#f3f4f6;padding:16px 0;text-align:center;border-radius:6px;">{escape(code)}</p>
      <p>This code expires in {expires_in_minutes} minutes.</p>
      <p style="color:#6b7280;font-size:13px;">If you did not request this code, you can safely ignore this email —
      no action is needed and your account remains secure.</p>
    """
    html = _layout(preheader=intro, heading=heading, body_html=body_html, cta_url=None, cta_label=None, support_email=support_email)
    text = (
        f"{intro}\n\nYour code: {code}\n\nIt expires in {expires_in_minutes} minutes.\n\n"
        "If you did not request this code, you can ignore this email."
        f"{_plain_footer(support_email)}"
    )
    return subject, html, text


def password_reset_email(*, reset_url: str, expires_in_hours: int, support_email: str) -> tuple[str, str, str]:
    subject = "Reset Your NEET Preparation Password"
    body_html = f"""
      <p>We received a request to reset your password.</p>
      <p>This link expires in {expires_in_hours} hours.</p>
      <p style="color:#6b7280;font-size:13px;">If you did not request a password reset, you can safely ignore this email —
      your password will not be changed.</p>
    """
    html = _layout(
        preheader="Reset your password.",
        heading="Reset Your Password",
        body_html=body_html,
        cta_url=reset_url,
        cta_label="Reset Password",
        support_email=support_email,
    )
    text = (
        "We received a request to reset your password. Open this link "
        f"(expires in {expires_in_hours} hours):\n\n{reset_url}\n\n"
        "If you did not request this, ignore this message."
        f"{_plain_footer(support_email)}"
    )
    return subject, html, text


def password_changed_email(*, when_text: str, support_email: str) -> tuple[str, str, str]:
    subject = "Your Password Was Changed — NEET Preparation"
    body_html = f"""
      <p>Your NEET Preparation account password was changed on {escape(when_text)}.</p>
      <p style="color:#6b7280;font-size:13px;">If you did not make this change, please review your account security immediately —
      it may be at risk.</p>
    """
    html = _layout(
        preheader="Your password was changed.",
        heading="Password Changed",
        body_html=body_html,
        cta_url=None,
        cta_label=None,
        support_email=support_email,
    )
    text = (
        f"Your account password was changed on {when_text}.\n\n"
        "If you did not make this change, review your account security immediately."
        f"{_plain_footer(support_email)}"
    )
    return subject, html, text


def new_login_alert_email(*, when_text: str, ip_address: str | None, device_text: str | None, support_email: str) -> tuple[str, str, str]:
    subject = "New Login to Your NEET Preparation Account"
    details = []
    if when_text:
        details.append(f"Time: {escape(when_text)}")
    if ip_address:
        details.append(f"IP address: {escape(ip_address)}")
    if device_text:
        details.append(f"Device/Browser: {escape(device_text)}")
    details_html = "<br>".join(details) if details else "Details unavailable."
    body_html = f"""
      <p>We noticed a new login to your account.</p>
      <p style="background:#f3f4f6;padding:12px;border-radius:6px;">{details_html}</p>
      <p style="color:#6b7280;font-size:13px;">If this was not you, change your password immediately.</p>
    """
    html = _layout(
        preheader="New login detected on your account.",
        heading="New Login Detected",
        body_html=body_html,
        cta_url=None,
        cta_label=None,
        support_email=support_email,
    )
    plain_details = "\n".join(d.replace("<br>", "") for d in details) if details else "Details unavailable."
    text = (
        f"We noticed a new login to your account.\n\n{plain_details}\n\n"
        "If this was not you, change your password immediately."
        f"{_plain_footer(support_email)}"
    )
    return subject, html, text


def email_changed_email(*, new_email_masked: str, when_text: str, support_email: str) -> tuple[str, str, str]:
    subject = "Your Email Address Was Changed — NEET Preparation"
    body_html = f"""
      <p>Your account email address was changed to {escape(new_email_masked)} on {escape(when_text)}.</p>
      <p style="color:#6b7280;font-size:13px;">If you did not make this change, please review your account security immediately.</p>
    """
    html = _layout(
        preheader="Your email address was changed.",
        heading="Email Address Changed",
        body_html=body_html,
        cta_url=None,
        cta_label=None,
        support_email=support_email,
    )
    text = (
        f"Your account email address was changed to {new_email_masked} on {when_text}.\n\n"
        "If you did not make this change, review your account security immediately."
        f"{_plain_footer(support_email)}"
    )
    return subject, html, text


def mobile_changed_email(*, new_mobile_masked: str, when_text: str, support_email: str) -> tuple[str, str, str]:
    subject = "Your Mobile Number Was Changed — NEET Preparation"
    body_html = f"""
      <p>Your account mobile number was changed to {escape(new_mobile_masked)} on {escape(when_text)}.</p>
      <p style="color:#6b7280;font-size:13px;">If you did not make this change, please review your account security immediately.</p>
    """
    html = _layout(
        preheader="Your mobile number was changed.",
        heading="Mobile Number Changed",
        body_html=body_html,
        cta_url=None,
        cta_label=None,
        support_email=support_email,
    )
    text = (
        f"Your account mobile number was changed to {new_mobile_masked} on {when_text}.\n\n"
        "If you did not make this change, review your account security immediately."
        f"{_plain_footer(support_email)}"
    )
    return subject, html, text
