from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pawpos.db.base import Base

if TYPE_CHECKING:
    from pawpos.models.customer import Customer
    from pawpos.models.product import Product
    from pawpos.models.refund import RefundItem, RefundRequest
    from pawpos.models.user import User


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("total >= 0", name="sale_total_nonnegative"),
        Base.__table_args__,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_number: Mapped[str | None] = mapped_column(String(30), unique=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "held",
            "completed",
            name="sale_status",
            create_constraint=True,
            validate_strings=True,
        )
    )
    cashier_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    payment_method: Mapped[str | None] = mapped_column(
        Enum(
            "cash",
            "gcash",
            name="payment_method",
            create_constraint=True,
            validate_strings=True,
        )
    )
    amount_received: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    change_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    gcash_reference: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    cashier: Mapped["User"] = relationship()
    customer: Mapped["Customer | None"] = relationship(back_populates="sales")
    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan"
    )
    refund_requests: Mapped[list["RefundRequest"]] = relationship(back_populates="sale")


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="sale_item_quantity_positive"),
        CheckConstraint(
            "unit_price >= 0 AND line_total >= 0", name="sale_item_amounts_nonnegative"
        ),
        Base.__table_args__,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(120))
    unit_type: Mapped[str] = mapped_column(
        Enum(
            "piece",
            "kg",
            name="sale_item_unit",
            create_constraint=True,
            validate_strings=True,
        )
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    sale: Mapped["Sale"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="sale_items")
    refund_items: Mapped[list["RefundItem"]] = relationship(back_populates="sale_item")


class VoidLog(Base):
    __tablename__ = "void_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    void_scope: Mapped[str] = mapped_column(
        Enum(
            "line",
            "transaction",
            name="void_scope",
            create_constraint=True,
            validate_strings=True,
        )
    )
    reason: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    user: Mapped["User"] = relationship()
