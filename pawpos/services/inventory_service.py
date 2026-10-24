"""Owner inventory operations and read-only stock history."""

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pawpos.core.errors import BusinessRuleError, NotFoundError, ValidationError
from pawpos.core.money import D, DecimalInput
from pawpos.db.base import session_scope
from pawpos.models import Product, Sale, StockMovement
from pawpos.services.auth_service import _require_owner
from pawpos.services.catalog_validation import quantity, text
from pawpos.services.product_service import ProductDetails, _details

MOVEMENT_TYPES = ("stock_received", "sale", "refund", "adjustment")
ADJUSTMENT_REASONS = ("Damage", "Loss", "Correction", "Other")


@dataclass(frozen=True)
class MovementDetails:
    id: int
    created_at: datetime
    product_id: int
    product_name: str
    unit_type: str
    movement_type: str
    quantity_change: Decimal
    stock_after: Decimal
    reference: str
    user_name: str
    note: str


def stock_overview(search: str = "") -> list[ProductDetails]:
    """List all products, including inactive ones, for owner stock management."""
    with session_scope() as session:
        _require_owner(session)
        search = text(search, "Search", 120, required=False)
        query = select(Product).options(joinedload(Product.category))
        if search:
            query = query.where(Product.name.icontains(search, autoescape=True))
        return [
            _details(product)
            for product in session.scalars(query.order_by(Product.name, Product.id))
        ]


def receive_stock(
    product_id: int,
    amount: DecimalInput,
    *,
    supplier: str = "",
    note: str = "",
    received_date: date | None = None,
) -> Decimal:
    """Record a delivery and its movement atomically; supplier applies to this delivery."""
    supplier = text(supplier, "Supplier", 120, required=False)
    note = text(note, "Note", 255, required=False)
    # The existing movement note stores delivery details; no supplier schema is needed.
    combined = text(
        "; ".join(
            part for part in (f"Supplier: {supplier}" if supplier else "", note) if part
        ),
        "Supplier and note together",
        255,
        required=False,
    )
    return _change_stock(product_id, amount, "stock_received", combined, received_date)


def adjust_stock(
    product_id: int, change: DecimalInput, *, reason: str, note: str
) -> Decimal:
    """Apply a signed correction without permitting negative stock."""
    if reason not in ADJUSTMENT_REASONS:
        raise ValidationError("Choose Damage, Loss, Correction, or Other.")
    combined = text(f"{reason}: {text(note, 'Note', 255)}", "Reason and note", 255)
    return _change_stock(product_id, change, "adjustment", combined)


def _change_stock(
    product_id: int,
    change: DecimalInput,
    movement_type: str,
    note: str,
    received_date: date | None = None,
) -> Decimal:
    with session_scope() as session:
        owner = _require_owner(session)
        product = session.scalar(
            select(Product).where(Product.id == product_id).with_for_update()
        )
        if product is None:
            raise NotFoundError("Product not found.")
        delta = D(change)
        quantity(abs(delta), "Quantity", product.unit_type)
        if delta == 0 or (movement_type == "stock_received" and delta < 0):
            raise ValidationError(
                "Receive quantity must be positive."
                if movement_type == "stock_received"
                else "Adjustment must not be zero."
            )
        stock = product.stock_quantity + delta
        if stock < 0:
            raise BusinessRuleError("Adjustment would make stock negative.")
        quantity(stock, "Resulting stock", product.unit_type)
        created_at = datetime.now()
        if received_date is not None:
            _validate_date(received_date)
            if received_date > date.today():
                raise ValidationError("Delivery date cannot be in the future.")
            if received_date != date.today():
                created_at = datetime.combine(received_date, time.min)
        product.stock_quantity = stock
        session.add(
            StockMovement(
                product_id=product.id,
                user_id=owner.id,
                movement_type=movement_type,
                quantity_change=delta,
                stock_after=stock,
                note=note or None,
                created_at=created_at,
            )
        )
    return stock


def _validate_date(value: date) -> None:
    if type(value) is not date:
        raise ValidationError("Dates must be calendar dates.")


def list_movements(
    *,
    product_id: int | None = None,
    movement_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[MovementDetails]:
    """Return immutable movement rows; calendar date bounds are inclusive."""
    with session_scope() as session:
        _require_owner(session)
        if movement_type is not None and movement_type not in MOVEMENT_TYPES:
            raise ValidationError("Choose a valid movement type.")
        for bound in (date_from, date_to):
            if bound is not None:
                _validate_date(bound)
        if date_from and date_to and date_from > date_to:
            raise ValidationError("From date must not be after To date.")
        query = (
            select(StockMovement, Sale.receipt_number)
            .outerjoin(
                Sale,
                (StockMovement.reference_type == "sale")
                & (StockMovement.reference_id == Sale.id),
            )
            .options(joinedload(StockMovement.product), joinedload(StockMovement.user))
            .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        )
        if product_id is not None:
            query = query.where(StockMovement.product_id == product_id)
        if movement_type is not None:
            query = query.where(StockMovement.movement_type == movement_type)
        if date_from:
            query = query.where(
                StockMovement.created_at >= datetime.combine(date_from, time.min)
            )
        if date_to:
            query = query.where(
                StockMovement.created_at <= datetime.combine(date_to, time.max)
            )
        return [
            MovementDetails(
                row.id,
                row.created_at,
                row.product_id,
                row.product.name,
                row.product.unit_type,
                row.movement_type,
                row.quantity_change,
                row.stock_after,
                receipt
                or (
                    f"{row.reference_type} #{row.reference_id}"
                    if row.reference_type and row.reference_id is not None
                    else ""
                ),
                row.user.full_name,
                row.note or "",
            )
            for row, receipt in session.execute(query)
        ]
