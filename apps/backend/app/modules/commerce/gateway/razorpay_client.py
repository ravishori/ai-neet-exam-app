import hashlib
import hmac

import httpx

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


class RazorpayNotConfiguredError(Exception):
    pass


class RazorpayApiError(Exception):
    pass


def verify_payment_signature(*, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str, key_secret: str) -> bool:
    """Matches Razorpay's checkout verification: HMAC-SHA256(order_id|payment_id, key_secret)."""
    payload = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    expected = hmac.new(key_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)


def verify_webhook_signature(*, raw_body: bytes, signature: str, webhook_secret: str) -> bool:
    """Matches Razorpay's webhook verification: HMAC-SHA256(raw request body,
    webhook secret), sent in the X-Razorpay-Signature header. Distinct from
    verify_payment_signature above (different secret, different payload —
    raw bytes here, not an order_id|payment_id string) per Razorpay's
    webhook docs."""
    if not webhook_secret or not signature:
        return False
    expected = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def create_razorpay_order(*, amount_inr: float, receipt: str, key_id: str, key_secret: str) -> dict:
    if not key_id or not key_secret:
        raise RazorpayNotConfiguredError("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not configured")

    async with httpx.AsyncClient(auth=(key_id, key_secret), timeout=15.0) as client:
        response = await client.post(
            f"{RAZORPAY_API_BASE}/orders",
            json={"amount": int(amount_inr * 100), "currency": "INR", "receipt": receipt},
        )
    if response.status_code >= 400:
        raise RazorpayApiError(f"Razorpay order creation failed: {response.status_code} {response.text}")
    return response.json()
