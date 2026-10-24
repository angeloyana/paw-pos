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
    from pawpos.models.category import Category
    from pawpos.models.sale import SaleItem
    from pawpos.models.stock_movement import StockMovement


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="product_price_nonnegative"),
        CheckConstraint("stock_quantity >= 0", name="product_stock_nonnegative"),
        CheckConstraint(
            "low_stock_threshold >= 0", name="product_threshold_nonnegative"
        ),
        Base.__table_args__,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit_type: Mapped[str] = mapped_column(
        Enum(
            "piece",
            "kg",
            name="product_unit",
            create_constraint=True,
            validate_strings=True,
        )
    )
    stock_quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), default=Decimal("0")
    )
    low_stock_threshold: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), default=Decimal("0")
    )
    supplier: Mapped[str | None] = mapped_column(String(120))
    image_path: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )
    category: Mapped["Category"] = relationship(back_populates="products")
    sale_items: Mapped[list["SaleItem"]] = relationship(back_populates="product")
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="product"
    )
