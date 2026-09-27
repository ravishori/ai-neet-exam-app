from app.modules.commerce.gateway.base import (
    PaymentProvider,
    PaymentProviderError,
    PaymentProviderNotConfiguredError,
    ProviderOrder,
)
from app.modules.commerce.gateway.razorpay_client import (
    RazorpayApiError,
    RazorpayNotConfiguredError,
    create_razorpay_order_paise,
    verify_payment_signature,
)


class RazorpayProvider(PaymentProvider):
    """First concrete PaymentProvider. Wraps the pre-existing, unmodified
    razorpay_client functions (verify_payment_signature/create_razorpay_order*)
    — the real HMAC-SHA256 cryptographic verification logic is untouched."""

    def __init__(self, *, key_id: str, key_secret: str):
        self._key_id = key_id
        self._key_secret = key_secret

    async def create_order(self, *, amount_paise: int, receipt: str) -> ProviderOrder:
        try:
            raw = await create_razorpay_order_paise(
                amount_paise=amount_paise, receipt=receipt, key_id=self._key_id, key_secret=self._key_secret
            )
        except RazorpayNotConfiguredError as exc:
            raise PaymentProviderNotConfiguredError(str(exc)) from exc
        except RazorpayApiError as exc:
            raise PaymentProviderError(str(exc)) from exc
        return ProviderOrder(provider_order_id=raw["id"], raw=raw)

    def verify_payment(self, *, provider_order_id: str, provider_payment_id: str, signature: str) -> bool:
        return verify_payment_signature(
            razorpay_order_id=provider_order_id,
            razorpay_payment_id=provider_payment_id,
            razorpay_signature=signature,
            key_secret=self._key_secret,
        )

    def initiate_payment(self, *, provider_order: ProviderOrder) -> dict:
        return {"razorpay_order_id": provider_order.provider_order_id, "razorpay_key_id": self._key_id}
