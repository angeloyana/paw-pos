"""Atomic completed sales and shared Decimal payment validation."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from pawpos.core.errors import BusinessRuleError, ValidationError
from pawpos.core.money import DecimalInput
from pawpos.db.base import session_scope
from pawpos.models import Customer, Product, Sale, SaleItem, StockMovement
from pawpos.services.auth_service import _require_user
from pawpos.services.cart import Cart
from pawpos.services.catalog_validation import number, text


@dataclass(frozen=True)
class Payment:
    method: str
    amount_received: DecimalInput | None = None
    gcash_reference: str = ""


@dataclass(frozen=True)
class PaymentDetails:
    method: str
    amount_received: Decimal | None
    change_amount: Decimal | None
    gcash_reference: str | None


@dataclass(frozen=True)
class CompletedSale:
    id: int
    receipt_number: str
    total: Decimal


def validate_payment(total: DecimalInput, payment: Payment) -> PaymentDetails:
    """Validate tender without DB access, for both live UI feedback and checkout."""
    total = number(total, "Total", 2, "99999999.99")
    if not isinstance(payment, Payment):
        raise ValidationError("Choose cash or GCash payment.")
    if payment.method == "cash":
        received = number(payment.amount_received, "Amount received", 2, "99999999.99")
        if received < total:
            raise ValidationError("Amount received must cover the total.")
        return PaymentDetails("cash", received, received - total, None)
    if payment.method == "gcash":
        reference = text(payment.gcash_reference, "GCash reference", 50)
        return PaymentDetails("gcash", None, None, reference)
    raise ValidationError("Choose cash or GCash payment.")


def _next_receipt_number(session, completed_at: datetime) -> str:
    prefix = f"PAW-{completed_at:%Y%m%d}-"
    previous = session.scalar(
        select(Sale.receipt_number)
        .where(Sale.receipt_number.startswith(prefix))
        .order_by(Sale.receipt_number.desc())
        .limit(1)
    )
    sequence = int(previous.rsplit("-", 1)[1]) + 1 if previous else 1
    if sequence > 9999:
        raise BusinessRuleError("Today's receipt number limit has been reached.")
    return f"{prefix}{sequence:04d}"


def complete_sale(
    cart: Cart, payment: Payment, *, customer_id: int | None = None
) -> CompletedSale:
    """Commit sale, item snapshots, stock deductions, and movements together.

    The authenticated account supplies cashier identity. The caller clears the
    cart only after this function returns, so validation/rollback preserves it.
    """
    if not isinstance(cart, Cart) or not cart.lines:
        raise ValidationError("The cart is empty.")
    lines = cart.lines
    with session_scope() as session:
        cashier = _require_user(session)
        if customer_id is not None:
            if type(customer_id) is not int or customer_id <= 0:
                raise ValidationError("Choose a valid customer.")
            if session.get(Customer, customer_id) is None:
                raise ValidationError(
                    "Customer no longer exists. Select another customer."
                )
        products = {
            row.id: row
            for row in session.scalars(
                select(Product)
                .where(Product.id.in_([line.product_id for line in lines]))
                .order_by(Product.id)
                .with_for_update()
            )
        }
        checked = Cart()
        for line in lines:
            product = products.get(line.product_id)
            if (
                product is None
                or not product.is_active
                or not product.category.is_active
            ):
                raise BusinessRuleError(f"{line.product_name} is no longer available.")
            if product.unit_type != line.unit_type:
                raise BusinessRuleError(
                    f"Units changed for {line.product_name}. Remove and add it again."
                )
            add = checked.add_piece if line.unit_type == "piece" else checked.add_weight
            add(
                line.product_id,
                line.product_name,
                line.unit_price,
                line.quantity,
                stock_quantity=product.stock_quantity,
            )
        tender = validate_payment(checked.total, payment)
        completed_at = datetime.now()
        sale = Sale(
            status="completed",
            cashier_id=cashier.id,
            customer_id=customer_id,
            total=checked.total,
            payment_method=tender.method,
            amount_received=tender.amount_received,
            change_amount=tender.change_amount,
            gcash_reference=tender.gcash_reference,
            receipt_number=_next_receipt_number(session, completed_at),
            created_at=completed_at,
            completed_at=completed_at,
        )
        session.add(sale)
        session.flush()
        for line in checked.lines:
            product = products[line.product_id]
            sale.items.append(
                SaleItem(
                    product_id=line.product_id,
                    product_name=line.product_name,
                    unit_type=line.unit_type,
                    unit_price=line.unit_price,
                    quantity=line.quantity,
                    line_total=line.line_total,
                )
            )
            product.stock_quantity -= line.quantity
            session.add(
                StockMovement(
                    product_id=product.id,
                    movement_type="sale",
                    quantity_change=-line.quantity,
                    stock_after=product.stock_quantity,
                    reference_type="sale",
                    reference_id=sale.id,
                    user_id=cashier.id,
                    created_at=completed_at,
                )
            )
        result = CompletedSale(sale.id, sale.receipt_number, sale.total)
    return result
