from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pawpos.db.base import Base

if TYPE_CHECKING:
    from pawpos.models.sale import Sale, SaleItem
    from pawpos.models.user import User


class RefundRequest(Base):
    __tablename__ = "refund_requests"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="refund_total_nonnegative"),
        Base.__table_args__,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"))
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "approved",
            "rejected",
            name="refund_status",
            create_constraint=True,
            validate_strings=True,
        ),
        default="pending",
    )
    reason: Mapped[str] = mapped_column(String(255))
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_note: Mapped[str | None] = mapped_column(String(255))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    sale: Mapped["Sale"] = relationship(back_populates="refund_requests")
    requester: Mapped["User"] = relationship(foreign_keys=[requested_by])
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by])
    items: Mapped[list["RefundItem"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class RefundItem(Base):
    __tablename__ = "refund_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="refund_item_quantity_positive"),
        CheckConstraint("amount >= 0", name="refund_item_amount_nonnegative"),
        Base.__table_args__,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    refund_request_id: Mapped[int] = mapped_column(
        ForeignKey("refund_requests.id", ondelete="CASCADE")
    )
    sale_item_id: Mapped[int] = mapped_column(ForeignKey("sale_items.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    is_opened: Mapped[bool] = mapped_column(Boolean, default=False)
    resellable: Mapped[bool | None] = mapped_column(Boolean)
    request: Mapped["RefundRequest"] = relationship(back_populates="items")
    sale_item: Mapped["SaleItem"] = relationship(back_populates="refund_items")
