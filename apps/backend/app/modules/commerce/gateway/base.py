"""Payment provider abstraction. Orders/Payments/Entitlements code depends only
on this interface, never on a specific gateway — swapping/adding Cashfree,
PayU, or a direct-UPI provider later requires no change above this layer.

Only RazorpayProvider is implemented today (per explicit scope decision:
"do not implement Cashfree, PayU or DirectUPI now, only establish the
abstraction"). Every method mirrors what CommerceService actually needs for
the Razorpay checkout flow.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderOrder:
    provider_order_id: str
    raw: dict


class PaymentProviderError(Exception):
    pass


class PaymentProviderNotConfiguredError(PaymentProviderError):
    pass


class PaymentProvider(ABC):
    @abstractmethod
    async def create_order(self, *, amount_paise: int, receipt: str) -> ProviderOrder: ...

    @abstractmethod
    def verify_payment(self, *, provider_order_id: str, provider_payment_id: str, signature: str) -> bool: ...

    def initiate_payment(self, *, provider_order: ProviderOrder) -> dict:
        """Client-facing data needed to open the provider's checkout. Default
        implementation is a no-op passthrough of the raw order — providers
        that need more (e.g. a hosted checkout URL) override this."""
        return provider_order.raw

    async def get_payment_status(self, *, provider_payment_id: str) -> str:  # pragma: no cover - not needed yet
        raise NotImplementedError

    async def refund_payment(self, *, provider_payment_id: str, amount_paise: int) -> None:  # pragma: no cover
        raise NotImplementedError
