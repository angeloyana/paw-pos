"""Owner completed-sale history, filters, and immutable item details."""

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from pawpos.core.errors import NotFoundError, ValidationError
from pawpos.db.base import session_scope
from pawpos.models import RefundRequest, Sale
from pawpos.services.auth_service import _require_owner
from pawpos.services.catalog_validation import text
from pawpos.services.receipt_service import ReceiptLine


@dataclass(frozen=True)
class SaleSummary:
    id: int
    receipt_number: str
    completed_at: datetime
    cashier_id: int
    cashier_name: str
    customer_name: str
    payment_method: str
    total: Decimal
    refunded_amount: Decimal


@dataclass(frozen=True)
class SaleDetails:
    summary: SaleSummary
    items: tuple[ReceiptLine, ...]
    amount_received: Decimal | None
    change_amount: Decimal | None
    gcash_reference: str | None


def _query():
    # Aggregate refunds before joining so multiple requests cannot duplicate sales.
    refunded = (
        select(
            RefundRequest.sale_id, func.sum(RefundRequest.total_amount).label("amount")
        )
        .where(RefundRequest.status == "approved")
        .group_by(RefundRequest.sale_id)
        .subquery()
    )
    return (
        select(Sale, func.coalesce(refunded.c.amount, 0))
        .outerjoin(refunded, refunded.c.sale_id == Sale.id)
        .where(Sale.status == "completed")
        .options(joinedload(Sale.cashier), joinedload(Sale.customer))
    )


def _summary(sale: Sale, refunded: Decimal) -> SaleSummary:
    return SaleSummary(
        sale.id,
        sale.receipt_number,
        sale.completed_at,
        sale.cashier_id,
        sale.cashier.full_name,
        sale.customer.name if sale.customer else "Walk-in",
        sale.payment_method,
        sale.total,
        refunded,
    )


def list_sales(
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    receipt_number: str = "",
    cashier_id: int | None = None,
    payment_method: str | None = None,
    customer_id: int | None = None,
) -> list[SaleSummary]:
    """Filter completed sales; dates include both bounds and refunds include approved only."""
    with session_scope() as session:
        _require_owner(session)
        receipt_number = text(receipt_number, "Receipt number", 30, required=False)
        for bound in (date_from, date_to):
            if bound is not None and type(bound) is not date:
                raise ValidationError("Dates must be calendar dates.")
        if date_from and date_to and date_from > date_to:
            raise ValidationError("From date must not be after To date.")
        if payment_method is not None and payment_method not in ("cash", "gcash"):
            raise ValidationError("Choose Cash or GCash.")
        for value in (cashier_id, customer_id):
            if value is not None and (type(value) is not int or value <= 0):
                raise ValidationError("Choose a valid cashier or customer.")
        query = _query().order_by(Sale.completed_at.desc(), Sale.id.desc())
        if date_from:
            query = query.where(
                Sale.completed_at >= datetime.combine(date_from, time.min)
            )
        if date_to:
            query = query.where(
                Sale.completed_at <= datetime.combine(date_to, time.max)
            )
        if receipt_number:
            query = query.where(
                Sale.receipt_number.icontains(receipt_number, autoescape=True)
            )
        if cashier_id is not None:
            query = query.where(Sale.cashier_id == cashier_id)
        if customer_id is not None:
            query = query.where(Sale.customer_id == customer_id)
        if payment_method is not None:
            query = query.where(Sale.payment_method == payment_method)
        return [_summary(sale, refunded) for sale, refunded in session.execute(query)]


def get_sale(sale_id: int) -> SaleDetails:
    """Return original item/payment snapshots with the current approved refund total."""
    with session_scope() as session:
        _require_owner(session)
        if type(sale_id) is not int or sale_id <= 0:
            raise ValidationError("Choose a valid sale.")
        row = session.execute(_query().where(Sale.id == sale_id)).one_or_none()
        if row is None:
            raise NotFoundError("Completed sale not found.")
        sale, refunded = row
        return SaleDetails(
            _summary(sale, refunded),
            tuple(
                ReceiptLine(
                    item.product_name,
                    item.quantity,
                    item.unit_type,
                    item.unit_price,
                    item.line_total,
                )
                for item in sorted(sale.items, key=lambda row: row.id)
            ),
            sale.amount_received,
            sale.change_amount,
            sale.gcash_reference,
        )
