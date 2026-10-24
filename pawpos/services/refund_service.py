"""Receipt-based refund requests and atomic owner review."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from pawpos.config import REFUND_WINDOW_DAYS
from pawpos.core.errors import BusinessRuleError, NotFoundError, ValidationError
from pawpos.core.money import DecimalInput, round_money
from pawpos.db.base import session_scope
from pawpos.models import (
    Product,
    RefundItem,
    RefundRequest,
    Sale,
    SaleItem,
    StockMovement,
)
from pawpos.services import report_service
from pawpos.services.auth_service import _require_owner, _require_user
from pawpos.services.catalog_validation import flag, number, quantity, text


@dataclass(frozen=True)
class RefundLineInput:
    sale_item_id: int
    quantity: DecimalInput
    is_opened: bool = False


@dataclass(frozen=True)
class RefundableLine:
    id: int
    product_name: str
    unit_type: str
    unit_price: Decimal
    quantity: Decimal
    remaining: Decimal
    is_food: bool


@dataclass(frozen=True)
class RefundableSale:
    id: int
    receipt_number: str
    completed_at: datetime
    items: tuple[RefundableLine, ...]


@dataclass(frozen=True)
class RefundLineDetails:
    id: int
    sale_item_id: int
    product_name: str
    unit_type: str
    quantity: Decimal
    amount: Decimal
    is_opened: bool
    resellable: bool | None


@dataclass(frozen=True)
class RefundDetails:
    id: int
    sale_id: int
    receipt_number: str
    status: str
    reason: str
    requester: str
    requested_at: datetime
    reviewer: str | None
    reviewed_at: datetime | None
    review_note: str
    total_amount: Decimal
    items: tuple[RefundLineDetails, ...]


def _id(value: int) -> int:
    if type(value) is not int or value <= 0:
        raise ValidationError("Choose a valid refund or sale item.")
    return value


def _remaining(session: Session, item: SaleItem) -> Decimal:
    reserved = session.scalar(
        select(func.coalesce(func.sum(RefundItem.quantity), 0))
        .join(RefundItem.request)
        .where(
            RefundItem.sale_item_id == item.id,
            RefundRequest.status.in_(("pending", "approved")),
        )
    )
    return item.quantity - reserved


def remaining_refundable(sale_item_id: int) -> Decimal:
    """Return quantity left after pending and approved requests; rejected ones release it."""
    with session_scope() as session:
        _require_user(session)
        item = session.get(SaleItem, _id(sale_item_id))
        if item is None or item.sale.status != "completed":
            raise NotFoundError("Completed sale item not found.")
        return _remaining(session, item)


def _sale(session: Session, receipt_number: str) -> Sale:
    receipt_number = text(receipt_number, "Receipt number", 30)
    sale = session.scalar(
        select(Sale)
        .where(Sale.receipt_number == receipt_number, Sale.status == "completed")
        .with_for_update()
    )
    if sale is None or sale.completed_at is None:
        raise NotFoundError("Completed receipt not found.")
    return sale


def lookup_receipt(receipt_number: str) -> RefundableSale:
    """Load completed sale snapshots and available quantities, including older receipts."""
    with session_scope() as session:
        _require_user(session)
        sale = _sale(session, receipt_number)
        return RefundableSale(
            sale.id,
            sale.receipt_number,
            sale.completed_at,
            tuple(
                RefundableLine(
                    item.id,
                    item.product_name,
                    item.unit_type,
                    item.unit_price,
                    item.quantity,
                    _remaining(session, item),
                    item.product.category.is_food,
                )
                for item in sorted(sale.items, key=lambda row: row.id)
            ),
        )


def _details(request: RefundRequest) -> RefundDetails:
    return RefundDetails(
        request.id,
        request.sale_id,
        request.sale.receipt_number,
        request.status,
        request.reason,
        request.requester.full_name,
        request.requested_at,
        request.reviewer.full_name if request.reviewer else None,
        request.reviewed_at,
        request.review_note or "",
        request.total_amount,
        tuple(
            RefundLineDetails(
                item.id,
                item.sale_item_id,
                item.sale_item.product_name,
                item.sale_item.unit_type,
                item.quantity,
                item.amount,
                item.is_opened,
                item.resellable,
            )
            for item in sorted(request.items, key=lambda row: row.id)
        ),
    )


def create_request(
    receipt_number: str, items: list[RefundLineInput], reason: str
) -> RefundDetails:
    """Reserve refundable quantities without changing stock; validate all lines before saving."""
    with session_scope() as session:
        user = _require_user(session)
        reason = text(reason, "Reason", 255)
        sale = _sale(session, receipt_number)
        now = datetime.now()
        if (
            not sale.completed_at
            <= now
            <= sale.completed_at + timedelta(days=REFUND_WINDOW_DAYS)
        ):
            raise BusinessRuleError(
                f"Refund requests must be made within {REFUND_WINDOW_DAYS} days of sale completion."
            )
        if not isinstance(items, (list, tuple)) or not items:
            raise ValidationError("Select at least one item to refund.")
        sale_items = {item.id: item for item in sale.items}
        seen = set()
        refund_items = []
        for line in items:
            if not isinstance(line, RefundLineInput):
                raise ValidationError("Choose valid refund items.")
            item = sale_items.get(_id(line.sale_item_id))
            if item is None:
                raise ValidationError("Every item must belong to the loaded receipt.")
            if item.id in seen:
                raise ValidationError("Select each sale item only once.")
            seen.add(item.id)
            amount = quantity(line.quantity, "Refund quantity", item.unit_type)
            if amount <= 0:
                raise ValidationError("Refund quantity must be positive.")
            opened = flag(line.is_opened, "Opened/used")
            if opened and item.product.category.is_food:
                raise BusinessRuleError(
                    f"Opened food cannot be refunded: {item.product_name}."
                )
            if amount > _remaining(session, item):
                raise BusinessRuleError(
                    f"Quantity exceeds remaining refundable stock for {item.product_name}."
                )
            refund_items.append(
                RefundItem(
                    sale_item_id=item.id,
                    quantity=amount,
                    amount=round_money(item.unit_price * amount),
                    is_opened=opened,
                )
            )
        total = number(
            sum((item.amount for item in refund_items), Decimal(0)),
            "Refund total",
            2,
            "99999999.99",
        )
        request = RefundRequest(
            sale_id=sale.id,
            reason=reason,
            requested_by=user.id,
            requested_at=now,
            status="pending",
            total_amount=total,
            items=refund_items,
        )
        session.add(request)
        session.flush()
        result = _details(request)
    return result


def _list(processed: bool) -> list[RefundDetails]:
    with session_scope() as session:
        _require_owner(session)
        query = (
            select(RefundRequest)
            .where(
                RefundRequest.status != "pending"
                if processed
                else RefundRequest.status == "pending"
            )
            .options(
                joinedload(RefundRequest.sale),
                joinedload(RefundRequest.requester),
                joinedload(RefundRequest.reviewer),
                selectinload(RefundRequest.items).joinedload(RefundItem.sale_item),
            )
            .order_by(RefundRequest.requested_at.desc(), RefundRequest.id.desc())
        )
        return [_details(request) for request in session.scalars(query)]


def list_pending() -> list[RefundDetails]:
    """List requests awaiting owner review."""
    return _list(False)


def list_history() -> list[RefundDetails]:
    """List approved/rejected requests with reviewer, decisions, and notes."""
    return _list(True)


def pending_refund_count() -> int:
    """Keep the existing refund badge API backed by the report count."""
    return report_service.pending_refund_count()


def _pending(session: Session, request_id: int) -> RefundRequest:
    request = session.scalar(
        select(RefundRequest)
        .where(RefundRequest.id == _id(request_id))
        .with_for_update()
    )
    if request is None:
        raise NotFoundError("Refund request not found.")
    if request.status != "pending":
        raise BusinessRuleError("This refund has already been reviewed.")
    return request


def approve(request_id: int, resellable_map: dict[int, bool]) -> RefundDetails:
    """Approve once and restore only explicitly resellable lines, atomically."""
    with session_scope() as session:
        owner = _require_owner(session)
        request = _pending(session, request_id)
        if (
            not isinstance(resellable_map, dict)
            or any(type(key) is not int for key in resellable_map)
            or set(resellable_map) != {item.id for item in request.items}
        ):
            raise ValidationError("Mark every refund line resellable yes or no.")
        for value in resellable_map.values():
            flag(value, "Resellable")
        # Pending requests reserve quantities; review may occur after the request window.
        products = {
            p.id: p
            for p in session.scalars(
                select(Product)
                .where(
                    Product.id.in_(
                        {item.sale_item.product_id for item in request.items}
                    )
                )
                .order_by(Product.id)
                .with_for_update()
            )
        }
        now = datetime.now()
        for item in request.items:
            item.resellable = resellable_map[item.id]
            if not item.resellable:
                continue
            product = products[item.sale_item.product_id]
            stock = quantity(
                product.stock_quantity + item.quantity,
                "Resulting stock",
                product.unit_type,
            )
            product.stock_quantity = stock
            session.add(
                StockMovement(
                    product_id=product.id,
                    movement_type="refund",
                    quantity_change=item.quantity,
                    stock_after=stock,
                    reference_type="refund",
                    reference_id=request.id,
                    user_id=owner.id,
                    note=request.reason,
                    created_at=now,
                )
            )
        request.status = "approved"
        request.reviewed_by = owner.id
        request.reviewed_at = now
        session.flush()
        result = _details(request)
    return result


def reject(request_id: int, note: str) -> RefundDetails:
    """Reject a pending request with a note; release quantities and leave stock unchanged."""
    with session_scope() as session:
        owner = _require_owner(session)
        note = text(note, "Rejection note", 255)
        request = _pending(session, request_id)
        request.status = "rejected"
        request.reviewed_by = owner.id
        request.reviewed_at = datetime.now()
        request.review_note = note
        session.flush()
        result = _details(request)
    return result
