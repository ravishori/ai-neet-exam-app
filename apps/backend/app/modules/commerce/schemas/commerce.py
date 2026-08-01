from pydantic import BaseModel, Field


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str = Field(min_length=1)
    razorpay_signature: str = Field(min_length=1)
