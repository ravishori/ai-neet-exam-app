"""State / City master data (Cities-List.xlsx is the authoritative source).

Two normalized tables in the ``identity`` schema:

* ``states`` — one row per distinct State/UT literal present in the source.
  ``code`` is a deterministic uppercased slug of ``name`` (spaces → underscores,
  non-alnum stripped) so equal names produce equal codes across environments.
* ``cities`` — one row per (state_id, name) pair from the source. Foreign key
  RESTRICTs so a state with cities cannot be silently dropped.

Both tables carry ``is_active`` so the runtime validator can hide records
without physically deleting them (satisfies "inactive State cannot be
selected" from the spec without ever losing historical assignments).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.shared.mixins import AuditedBase


class State(Base, AuditedBase):
    __tablename__ = "states"
    __table_args__ = (
        UniqueConstraint("code", name="uq_identity_states_code"),
        UniqueConstraint("name", name="uq_identity_states_name"),
        {"schema": "identity"},
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    cities: Mapped[list[City]] = relationship(
        back_populates="state", cascade="all, delete-orphan"
    )


class City(Base, AuditedBase):
    __tablename__ = "cities"
    __table_args__ = (
        UniqueConstraint("state_id", "name", name="uq_identity_cities_state_name"),
        Index("ix_identity_cities_state_id", "state_id"),
        Index("ix_identity_cities_name", "name"),
        {"schema": "identity"},
    )

    state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("identity.states.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    state: Mapped[State] = relationship(back_populates="cities")


def slug_state_code(name: str) -> str:
    """Deterministic State/UT code derived from the source-supplied name.

    Deliberately not ISO 3166-2:IN — the authoritative source (Cities-List.xlsx)
    does not carry ISO codes and using name-derived slugs keeps import and
    lookup reversible from the same input the operator sees in the sheet.
    """
    keep = []
    for ch in (name or "").strip().upper():
        if ch.isalnum():
            keep.append(ch)
        elif ch in (" ", "-", "_", "."):
            keep.append("_")
    slug = "".join(keep).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug
