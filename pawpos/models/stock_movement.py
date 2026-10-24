from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pawpos.db.base import Base

if TYPE_CHECKING:
    from pawpos.models.product import Product
    from pawpos.models.user import User


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("stock_after >= 0", name="movement_stock_nonnegative"),
        Base.__table_args__,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    movement_type: Mapped[str] = mapped_column(
        Enum(
            "stock_received",
            "sale",
            "refund",
            "adjustment",
            name="movement_type",
            create_constraint=True,
            validate_strings=True,
        )
    )
    quantity_change: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    stock_after: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    reference_type: Mapped[str | None] = mapped_column(String(20))
    reference_id: Mapped[int | None]
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, index=True
    )
    product: Mapped["Product"] = relationship(back_populates="stock_movements")
    user: Mapped["User"] = relationship()
