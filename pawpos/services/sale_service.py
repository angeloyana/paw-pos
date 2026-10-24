"""Atomic sales, held carts, void logging, and Decimal payment validation."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from pawpos.core.errors import BusinessRuleError, NotFoundError, ValidationError
from pawpos.core.money import DecimalInput
from pawpos.db.base import session_scope
from pawpos.models import Customer, Product, Sale, SaleItem, StockMovement, VoidLog
from pawpos.services.auth_service import _require_user
from pawpos.services.cart import Cart, CartLine
from pawpos.services.catalog_validation import number, text
from pawpos.services.customer_service import CustomerDetails


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


@dataclass(frozen=True)
class HeldSummary:
    id: int
    created_at: datetime
    item_count: int
    total: Decimal
    customer_name: str | None
    cashier_name: str


@dataclass(frozen=True)
class ResumedCart:
    cart: Cart
    customer: CustomerDetails | None


def _customer(session: Session, customer_id: int | None) -> Customer | None:
    if customer_id is None:
        return None
    if type(customer_id) is not int or customer_id <= 0:
        raise ValidationError("Choose a valid customer.")
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise ValidationError("Customer no longer exists. Select another customer.")
    return customer


def _snapshot_cart(lines: tuple[CartLine, ...]) -> Cart:
    cart = Cart()
    for line in lines:
        add = cart.add_piece if line.unit_type == "piece" else cart.add_weight
        if line.unit_type not in ("piece", "kg"):
            raise ValidationError("Unit type must be piece or kg.")
        # Holding/restoring does not reserve stock; payment checks live availability.
        add(
            line.product_id,
            line.product_name,
            line.unit_price,
            line.quantity,
            stock_quantity=line.quantity,
        )
    return cart


def _draft(cart: Cart) -> Cart:
    if not isinstance(cart, Cart) or not cart.lines:
        raise ValidationError("The cart is empty.")
    return _snapshot_cart(cart.lines)


def _held_summary(sale: Sale) -> HeldSummary:
    return HeldSummary(
        sale.id,
        sale.created_at,
        len(sale.items),
        sale.total,
        sale.customer.name if sale.customer else None,
        sale.cashier.full_name,
    )


def hold_cart(cart: Cart, *, customer_id: int | None = None) -> HeldSummary:
    """Save an unpaid snapshot atomically; the caller clears the cart after success."""
    with session_scope() as session:
        user = _require_user(session)
        checked = _draft(cart)
        customer = _customer(session, customer_id)
        for line in checked.lines:
            product = session.get(Product, line.product_id)
            if product is None:
                raise BusinessRuleError(f"{line.product_name} no longer exists.")
            if product.unit_type != line.unit_type:
                raise BusinessRuleError(
                    f"Units changed for {line.product_name}. Remove and add it again."
                )
        sale = Sale(
            status="held",
            cashier_id=user.id,
            customer_id=customer.id if customer else None,
            total=checked.total,
        )
        sale.items = [
            SaleItem(
                product_id=line.product_id,
                product_name=line.product_name,
                unit_type=line.unit_type,
                unit_price=line.unit_price,
                quantity=line.quantity,
                line_total=line.line_total,
            )
            for line in checked.lines
        ]
        session.add(sale)
        session.flush()
        result = _held_summary(sale)
    return result


def list_held() -> list[HeldSummary]:
    """List the shop's held carts for any active cashier or owner, oldest first."""
    with session_scope() as session:
        _require_user(session)
        sales = session.scalars(
            select(Sale)
            .where(Sale.status == "held")
            .options(
                joinedload(Sale.customer),
                joinedload(Sale.cashier),
                selectinload(Sale.items),
            )
            .order_by(Sale.created_at, Sale.id)
        )
        return [_held_summary(sale) for sale in sales]


def _held(session: Session, sale_id: int) -> Sale:
    if type(sale_id) is not int or sale_id <= 0:
        raise ValidationError("Choose a valid held transaction.")
    sale = session.scalar(
        select(Sale).where(Sale.id == sale_id, Sale.status == "held").with_for_update()
    )
    if sale is None:
        raise NotFoundError("Held transaction not found or already resumed/cancelled.")
    return sale


def _held_cart(sale: Sale) -> Cart:
    lines = tuple(
        CartLine(
            item.product_id,
            item.product_name,
            item.unit_type,
            item.unit_price,
            item.quantity,
        )
        for item in sorted(sale.items, key=lambda row: row.id)
    )
    if not lines:
        raise BusinessRuleError("This held transaction has no items.")
    return _snapshot_cart(lines)


def resume_held(sale_id: int) -> ResumedCart:
    """Restore original snapshots/customer and remove the held record atomically."""
    with session_scope() as session:
        _require_user(session)
        sale = _held(session, sale_id)
        cart = _held_cart(sale)
        customer = sale.customer
        result = ResumedCart(
            cart,
            CustomerDetails(customer.id, customer.name, customer.contact or "")
            if customer
            else None,
        )
        session.delete(sale)
    return result


def _write_voids(
    session: Session, cart: Cart, reason: str, scope: str, user_id: int
) -> None:
    for line in cart.lines:
        product = session.get(Product, line.product_id)
        session.add(
            VoidLog(
                user_id=user_id,
                product_id=product.id if product else None,
                product_name=line.product_name,
                quantity=line.quantity,
                amount=line.line_total,
                void_scope=scope,
                reason=reason,
            )
        )


def cancel_held(sale_id: int, reason: str) -> None:
    """Delete a held cart and preserve its item/reason audit in the same transaction."""
    with session_scope() as session:
        user = _require_user(session)
        reason = text(reason, "Reason", 255)
        sale = _held(session, sale_id)
        _write_voids(session, _held_cart(sale), reason, "transaction", user.id)
        # The schema has held/completed states; cancellation history lives in void_logs.
        session.delete(sale)


def void_line(cart: Cart, product_id: int, reason: str) -> None:
    """Commit a reasoned void first, then remove the line; rollback preserves the cart."""
    with session_scope() as session:
        user = _require_user(session)
        reason = text(reason, "Reason", 255)
        checked = _draft(cart)
        if type(product_id) is not int or product_id <= 0:
            raise ValidationError("Choose a valid cart line.")
        line = next(
            (line for line in checked.lines if line.product_id == product_id), None
        )
        if line is None:
            raise NotFoundError("Cart line not found.")
        _write_voids(session, _snapshot_cart((line,)), reason, "line", user.id)
    cart.remove_line(product_id)


def void_all(cart: Cart, reason: str) -> None:
    """Log every line atomically and clear the in-memory cart only after commit."""
    with session_scope() as session:
        user = _require_user(session)
        reason = text(reason, "Reason", 255)
        _write_voids(session, _draft(cart), reason, "transaction", user.id)
    cart.clear()


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
        _customer(session, customer_id)
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
