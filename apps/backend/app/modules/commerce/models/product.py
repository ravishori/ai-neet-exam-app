from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.mixins import AuditedBase


class Product(Base, AuditedBase):
    """A purchasable product/access tier (e.g. ALL_ACCESS). Distinct from
    PricingPlan: a product can have multiple pricing plans over time
    (founding vs standard) without changing what access it grants."""

    __tablename__ = "products"
    __table_args__ = {"schema": "commerce"}

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
