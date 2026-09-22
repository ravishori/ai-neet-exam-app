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


async def create_razorpay_order_paise(*, amount_paise: int, receipt: str, key_id: str, key_secret: str) -> dict:
    """Same as create_razorpay_order but takes the amount already in paise
    (Razorpay's own unit) — no float multiplication, per the no-floating-point
    rule for money. Preferred entry point for all new code; the *_inr variant
    above is kept only for its existing (untouched) test coverage."""
    if not key_id or not key_secret:
        raise RazorpayNotConfiguredError("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not configured")

    async with httpx.AsyncClient(auth=(key_id, key_secret), timeout=15.0) as client:
        response = await client.post(
            f"{RAZORPAY_API_BASE}/orders",
            json={"amount": amount_paise, "currency": "INR", "receipt": receipt},
        )
    if response.status_code >= 400:
        raise RazorpayApiError(f"Razorpay order creation failed: {response.status_code} {response.text}")
    return response.json()
