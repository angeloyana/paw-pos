"""Owner reports using local calendar dates and Decimal database aggregates."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import Numeric, func, literal, select, union_all
from sqlalchemy.orm import Session, joinedload

from pawpos.core.errors import ValidationError
from pawpos.db.base import session_scope
from pawpos.models import Category, Product, RefundItem, RefundRequest, Sale, SaleItem
from pawpos.services.auth_service import _require_owner
from pawpos.services.product_service import ProductDetails, _details


@dataclass(frozen=True)
class DailySales:
    day: date
    gross_sales: Decimal
    approved_refunds: Decimal
    net_sales: Decimal
    transactions: int


@dataclass(frozen=True)
class TodaySummary:
    day: date
    net_sales: Decimal
    transactions: int
    low_stock_count: int
    pending_refunds: int


@dataclass(frozen=True)
class BestSeller:
    product_id: int
    product_name: str
    unit_type: str
    quantity: Decimal
    net_revenue: Decimal


def _window(days: int) -> tuple[date, datetime, datetime]:
    today = datetime.now().date()
    start = datetime.combine(today - timedelta(days=days - 1), time.min)
    end = datetime.combine(today + timedelta(days=1), time.min)
    return today, start, end


def _daily(session: Session, days: int) -> list[DailySales]:
    today, start, end = _window(days)
    sale_day = func.date(Sale.completed_at)
    sales = session.execute(
        select(sale_day, func.sum(Sale.total), func.count(Sale.id))
        .where(
            Sale.status == "completed",
            Sale.completed_at >= start,
            Sale.completed_at < end,
        )
        .group_by(sale_day)
    )
    # SQLite returns date strings; MySQL returns date objects.
    gross = {
        date.fromisoformat(str(day)): (amount, count) for day, amount, count in sales
    }
    refund_day = func.date(RefundRequest.reviewed_at)
    refunds = session.execute(
        select(refund_day, func.sum(RefundRequest.total_amount))
        .join(RefundRequest.sale)
        .where(
            Sale.status == "completed",
            RefundRequest.status == "approved",
            RefundRequest.reviewed_at >= start,
            RefundRequest.reviewed_at < end,
        )
        .group_by(refund_day)
    )
    returned = {date.fromisoformat(str(day)): amount for day, amount in refunds}
    rows = []
    for offset in range(days):
        day = today - timedelta(days=days - offset - 1)
        amount, count = gross.get(day, (Decimal("0.00"), 0))
        refund = returned.get(day, Decimal("0.00"))
        rows.append(DailySales(day, amount, refund, amount - refund, count))
    return rows


def _low_stock_query():
    # Inactive catalog entries stay in Inventory but are not restocking alerts.
    return (
        select(Product)
        .join(Product.category)
        .where(
            Product.is_active.is_(True),
            Category.is_active.is_(True),
            Product.stock_quantity <= Product.low_stock_threshold,
        )
    )


def _pending_count(session: Session) -> int:
    return session.scalar(
        select(func.count())
        .select_from(RefundRequest)
        .where(RefundRequest.status == "pending")
    )


def today_summary() -> TodaySummary:
    """Return today's net sales/counts; refunds are charged on their approval date."""
    with session_scope() as session:
        _require_owner(session)
        row = _daily(session, 1)[0]
        low_count = session.scalar(
            select(func.count()).select_from(_low_stock_query().subquery())
        )
        return TodaySummary(
            row.day, row.net_sales, row.transactions, low_count, _pending_count(session)
        )


def daily_sales(days: int = 7) -> list[DailySales]:
    """Return seven or thirty calendar days, oldest first, filling empty dates with zero."""
    with session_scope() as session:
        _require_owner(session)
        if type(days) is not int or days not in (7, 30):
            raise ValidationError("Choose a 7-day or 30-day sales range.")
        return _daily(session, days)


def best_sellers(days: int = 7, limit: int = 5) -> list[BestSeller]:
    """Rank net revenue, deducting refunds on approval; retain historical products."""
    with session_scope() as session:
        _require_owner(session)
        if type(days) is not int or days not in (1, 7, 30):
            raise ValidationError("Choose today, 7 days, or 30 days.")
        if type(limit) is not int or limit <= 0:
            raise ValidationError("Best-seller limit must be a positive whole number.")
        _, start, end = _window(days)
        sales = (
            select(
                SaleItem.product_id,
                SaleItem.unit_type,
                func.sum(SaleItem.quantity).label("quantity"),
                func.sum(SaleItem.line_total).label("revenue"),
            )
            .join(SaleItem.sale)
            .where(
                Sale.status == "completed",
                Sale.completed_at >= start,
                Sale.completed_at < end,
            )
            .group_by(SaleItem.product_id, SaleItem.unit_type)
        )
        refunds = (
            select(
                SaleItem.product_id,
                SaleItem.unit_type,
                literal(Decimal("0.000"), type_=Numeric(10, 3)).label("quantity"),
                (-func.sum(RefundItem.amount)).label("revenue"),
            )
            .select_from(RefundItem)
            .join(RefundItem.sale_item)
            .join(RefundItem.request)
            .join(SaleItem.sale)
            .where(
                Sale.status == "completed",
                RefundRequest.status == "approved",
                RefundRequest.reviewed_at >= start,
                RefundRequest.reviewed_at < end,
            )
            .group_by(SaleItem.product_id, SaleItem.unit_type)
        )
        # Aggregate each source before combining, avoiding sale/refund multiplication.
        activity = union_all(sales, refunds).subquery()
        revenue = func.sum(activity.c.revenue)
        query = (
            select(
                Product.id,
                Product.name,
                activity.c.unit_type,
                func.sum(activity.c.quantity),
                revenue,
            )
            .join(activity, activity.c.product_id == Product.id)
            .group_by(Product.id, Product.name, activity.c.unit_type)
            .order_by(revenue.desc(), Product.name, Product.id, activity.c.unit_type)
            .limit(limit)
        )
        return [BestSeller(*row) for row in session.execute(query)]


def low_stock() -> list[ProductDetails]:
    """List active products/categories at or below threshold, including zero stock."""
    with session_scope() as session:
        _require_owner(session)
        query = (
            _low_stock_query()
            .options(joinedload(Product.category))
            .order_by(Product.stock_quantity, Product.name, Product.id)
        )
        return [_details(product) for product in session.scalars(query)]


def pending_refund_count() -> int:
    """Return requests awaiting owner review, matching the dashboard and sidebar."""
    with session_scope() as session:
        _require_owner(session)
        return _pending_count(session)
