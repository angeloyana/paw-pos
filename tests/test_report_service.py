from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError, ValidationError
from pawpos.core.session import CurrentUser
from pawpos.models import Category, Product, User
from pawpos.services import refund_service, sale_service
from pawpos.services import report_service as reports
from pawpos.services.cart import Cart
from pawpos.services.refund_service import RefundLineInput
from pawpos.services.sale_service import Payment

TODAY = datetime(2026, 10, 24)


def sell(factory, when, lines):
    cart = Cart()
    with factory() as session:
        for product_id, qty in lines:
            product = session.get(Product, product_id)
            add = cart.add_piece if product.unit_type == "piece" else cart.add_weight
            add(
                product.id,
                product.name,
                product.unit_price,
                qty,
                stock_quantity=product.stock_quantity,
            )
    with patch.object(sale_service, "datetime") as clock:
        clock.now.return_value = when
        return sale_service.complete_sale(cart, Payment("cash", 10000))


def refund(sale, product_name, qty, requested_at, status, reviewed_at=None):
    item = next(
        line
        for line in refund_service.lookup_receipt(sale.receipt_number).items
        if line.product_name == product_name
    )
    with patch.object(refund_service, "datetime") as clock:
        clock.now.return_value = requested_at
        result = refund_service.create_request(
            sale.receipt_number, [RefundLineInput(item.id, qty)], "Return"
        )
        clock.now.return_value = reviewed_at
        if status == "approved":
            refund_service.approve(result.id, {result.items[0].id: False})
        elif status == "rejected":
            refund_service.reject(result.id, "Rejected")
    return result


@pytest.fixture
def catalog(session_factory):
    with session_factory.begin() as session:
        session.add_all(
            [
                User(
                    id=1,
                    username="owner",
                    full_name="Owner",
                    role="owner",
                    password_hash="unused",
                ),
                User(
                    id=2,
                    username="cashier",
                    full_name="Cashier",
                    role="cashier",
                    password_hash="unused",
                ),
            ]
        )
        session.add_all(
            [
                Category(id=1, name="Toys"),
                Category(id=2, name="Hidden", is_active=False),
            ]
        )
        session.flush()
        session.add_all(
            [
                Product(
                    id=1,
                    name="Alpha",
                    category_id=1,
                    unit_type="piece",
                    unit_price=10,
                    stock_quantity=100,
                    low_stock_threshold=5,
                ),
                Product(
                    id=2,
                    name="Beta",
                    category_id=1,
                    unit_type="kg",
                    unit_price=95,
                    stock_quantity=10,
                    low_stock_threshold=2,
                ),
                Product(
                    id=3,
                    name="At threshold",
                    category_id=1,
                    unit_type="piece",
                    unit_price=2,
                    stock_quantity=5,
                    low_stock_threshold=5,
                ),
                Product(
                    id=4,
                    name="Zero",
                    category_id=1,
                    unit_type="piece",
                    unit_price=3,
                    stock_quantity=0,
                    low_stock_threshold=0,
                ),
                Product(
                    id=5,
                    name="Inactive",
                    category_id=1,
                    unit_type="piece",
                    unit_price=1,
                    stock_quantity=0,
                    low_stock_threshold=3,
                    is_active=False,
                ),
                Product(
                    id=6,
                    name="Hidden category",
                    category_id=2,
                    unit_type="piece",
                    unit_price=1,
                    stock_quantity=0,
                    low_stock_threshold=3,
                ),
            ]
        )
    login_session.set_current_user(CurrentUser(1, "owner", "Owner", "owner"))
    with patch.object(reports, "datetime", wraps=datetime) as clock:
        clock.now.return_value = TODAY + timedelta(hours=12)
        yield session_factory


@pytest.fixture
def activity(catalog):
    first = sell(catalog, TODAY, [(1, 3), (2, "1.375")])
    second = sell(catalog, TODAY + timedelta(days=1, microseconds=-1), [(1, 2)])
    yesterday = sell(catalog, TODAY - timedelta(days=1), [(1, 4)])
    sixth = sell(catalog, TODAY - timedelta(days=6), [(2, "0.5")])
    seventh = sell(catalog, TODAY - timedelta(days=7), [(1, 9)])
    sell(catalog, TODAY - timedelta(days=29), [(1, 1)])
    sell(catalog, TODAY - timedelta(days=30), [(1, 1)])
    sell(catalog, TODAY + timedelta(days=1), [(1, 1)])
    refund(
        yesterday,
        "Alpha",
        1,
        TODAY - timedelta(hours=20),
        "approved",
        TODAY + timedelta(hours=1),
    )
    refund(
        first,
        "Beta",
        "0.375",
        TODAY + timedelta(hours=1),
        "approved",
        TODAY + timedelta(hours=2),
    )
    refund(first, "Alpha", 1, TODAY + timedelta(hours=1), "pending")
    refund(
        second,
        "Alpha",
        1,
        TODAY + timedelta(days=1, microseconds=-1),
        "rejected",
        TODAY + timedelta(days=1, microseconds=-1),
    )
    refund(
        sixth,
        "Beta",
        "0.1",
        TODAY - timedelta(days=6, hours=-1),
        "approved",
        TODAY - timedelta(hours=1),
    )
    refund(
        seventh,
        "Alpha",
        1,
        TODAY - timedelta(days=6),
        "approved",
        TODAY - timedelta(days=2),
    )
    cart = Cart()
    cart.add_piece(1, "Alpha", 10, 20, stock_quantity=100)
    sale_service.hold_cart(cart)
    return catalog


def test_empty_reports_zero_fill_and_low_stock(catalog):
    summary = reports.today_summary()
    assert summary.day == TODAY.date() and summary.net_sales == Decimal("0.00")
    assert summary.transactions == summary.pending_refunds == 0
    assert summary.low_stock_count == 2
    rows = reports.daily_sales(7)
    assert len(rows) == 7 and rows[0].day == (TODAY - timedelta(days=6)).date()
    assert all(
        row.gross_sales == row.approved_refunds == row.net_sales == Decimal("0.00")
        and row.transactions == 0
        for row in rows
    )
    assert reports.best_sellers() == []
    assert reports.pending_refund_count() == 0


def test_today_uses_completion_and_approval_dates_without_join_multiplication(activity):
    summary = reports.today_summary()
    assert summary.net_sales == Decimal("135.00")
    assert summary.transactions == 2 and summary.pending_refunds == 1
    row = reports.daily_sales()[-1]
    assert row.gross_sales == Decimal("180.63")
    assert row.approved_refunds == Decimal("45.63")
    assert row.net_sales == summary.net_sales
    assert reports.pending_refund_count() == refund_service.pending_refund_count() == 1


def test_calendar_ranges_zero_dates_refund_only_negative_day_and_money_types(activity):
    rows = reports.daily_sales(7)
    assert [row.day for row in rows] == [
        (TODAY - timedelta(days=offset)).date() for offset in range(6, -1, -1)
    ]
    assert rows[-2].net_sales == Decimal("30.50")
    assert rows[-3].net_sales == Decimal("-10.00") and rows[-3].transactions == 0
    assert rows[1].net_sales == Decimal("0.00")
    assert sum(row.net_sales for row in rows) == Decimal("203.00")
    assert all(
        isinstance(row.net_sales, Decimal) and isinstance(row.approved_refunds, Decimal)
        for row in rows
    )
    month = reports.daily_sales(30)
    assert len(month) == 30 and month[0].gross_sales == Decimal("10.00")
    assert sum(row.gross_sales for row in month) == Decimal("368.13")


def test_best_sellers_gross_qty_units_limits_and_date_ranges(activity):
    today = reports.best_sellers(1)
    assert [(row.product_name, row.unit_type, row.quantity) for row in today] == [
        ("Alpha", "piece", Decimal("5.000")),
        ("Beta", "kg", Decimal("1.375")),
    ]
    week = reports.best_sellers(7)
    assert [row.quantity for row in week] == [Decimal("9.000"), Decimal("1.875")]
    assert reports.best_sellers(30, 1)[0].quantity == Decimal("19.000")
    assert len(reports.best_sellers(7, 1)) == 1


def test_best_seller_ties_and_inactive_historical_products(catalog):
    with catalog.begin() as session:
        for product_id, name in ((7, "Tie Z"), (8, "Tie A")):
            session.add(
                Product(
                    id=product_id,
                    name=name,
                    category_id=1,
                    unit_type="piece",
                    unit_price=1,
                    stock_quantity=20,
                )
            )
    sell(catalog, TODAY, [(7, 2), (8, 2)])
    with catalog.begin() as session:
        session.get(Product, 8).is_active = False
    assert [row.product_name for row in reports.best_sellers(1)] == ["Tie A", "Tie Z"]


def test_low_stock_equality_zero_active_filters_and_refresh(catalog):
    rows = reports.low_stock()
    assert [row.name for row in rows] == ["Zero", "At threshold"]
    assert reports.today_summary().low_stock_count == len(rows)
    from pawpos.services import inventory_service

    inventory_service.receive_stock(3, 1)
    assert [row.name for row in reports.low_stock()] == ["Zero"]
    assert reports.today_summary().low_stock_count == 1


@pytest.mark.parametrize("days", [True, 0, -1, 2, 31, "7", 7.0])
def test_invalid_daily_ranges(catalog, days):
    with pytest.raises(ValidationError):
        reports.daily_sales(days)


@pytest.mark.parametrize(
    "days,limit",
    [(True, 5), (0, 5), (2, 5), ("7", 5), (7, 0), (7, -1), (7, True), (7, 1.5)],
)
def test_invalid_best_seller_ranges_and_limits(catalog, days, limit):
    with pytest.raises(ValidationError):
        reports.best_sellers(days, limit)


@pytest.mark.parametrize("actor", [None, "cashier", "disabled-owner"])
def test_reports_require_active_owner(catalog, actor):
    if actor is None:
        login_session.logout()
    elif actor == "cashier":
        login_session.set_current_user(CurrentUser(2, "cashier", "Cashier", "cashier"))
    else:
        with catalog.begin() as session:
            session.get(User, 1).is_active = False
    for operation in (
        reports.today_summary,
        reports.daily_sales,
        reports.best_sellers,
        reports.low_stock,
        reports.pending_refund_count,
    ):
        with pytest.raises(AuthError):
            operation()
