import hashlib
import hmac

from app.modules.commerce.gateway.razorpay_client import verify_payment_signature


def _sign(order_id: str, payment_id: str, secret: str) -> str:
    payload = f"{order_id}|{payment_id}".encode()
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def test_valid_signature_verifies():
    secret = "test_secret_key"
    order_id, payment_id = "order_ABC123", "pay_XYZ789"
    signature = _sign(order_id, payment_id, secret)

    assert verify_payment_signature(
        razorpay_order_id=order_id, razorpay_payment_id=payment_id, razorpay_signature=signature, key_secret=secret
    )


def test_tampered_payment_id_fails_verification():
    secret = "test_secret_key"
    order_id = "order_ABC123"
    signature = _sign(order_id, "pay_XYZ789", secret)

    assert not verify_payment_signature(
        razorpay_order_id=order_id, razorpay_payment_id="pay_DIFFERENT", razorpay_signature=signature, key_secret=secret
    )


def test_wrong_secret_fails_verification():
    order_id, payment_id = "order_ABC123", "pay_XYZ789"
    signature = _sign(order_id, payment_id, "correct_secret")

    assert not verify_payment_signature(
        razorpay_order_id=order_id,
        razorpay_payment_id=payment_id,
        razorpay_signature=signature,
        key_secret="wrong_secret",
    )


def test_garbage_signature_fails():
    assert not verify_payment_signature(
        razorpay_order_id="order_ABC123",
        razorpay_payment_id="pay_XYZ789",
        razorpay_signature="not-a-real-signature",
        key_secret="test_secret_key",
    )
