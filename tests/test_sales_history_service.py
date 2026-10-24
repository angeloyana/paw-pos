from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import event, select

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError, NotFoundError, ValidationError
from pawpos.core.session import CurrentUser
from pawpos.models import Category, Customer, Product, Sale, User
from pawpos.services import customer_service, refund_service, sale_service
from pawpos.services import sales_history_service as history
from pawpos.services.cart import Cart
from pawpos.services.refund_service import RefundLineInput
from pawpos.services.sale_service import Payment


def sign_in(role="owner"):
    login_session.set_current_user(
        CurrentUser(1 if role == "owner" else 2, role, role.title(), role)
    )


@pytest.fixture
def sales(session_factory):
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
        category = Category(name="Toys")
        customer = Customer(name="Ana", contact="0917")
        session.add_all([category, customer])
        session.flush()
        session.add(
            Product(
                id=1,
                name="Ball",
                category_id=category.id,
                unit_type="piece",
                unit_price=10,
                stock_quantity=20,
            )
        )
    cart = Cart()
    cart.add_piece(1, "Original ball", 10, 3, stock_quantity=20)
    sign_in()
    with patch.object(sale_service, "datetime") as clock:
        clock.now.return_value = datetime(2026, 10, 24, 0, 0)
        first = sale_service.complete_sale(cart, Payment("cash", 50), customer_id=1)
        sign_in("cashier")
        clock.now.return_value = datetime(2026, 10, 24, 23, 59, 59, 999999)
        second = sale_service.complete_sale(
            cart, Payment("gcash", gcash_reference="REF-1")
        )
        clock.now.return_value = datetime(2026, 10, 25, 0, 0)
        third = sale_service.complete_sale(cart, Payment("cash", 30))
    sale_service.hold_cart(cart)
    sign_in()
    return session_factory, first, second, third


def test_completed_only_order_and_detached_payment_snapshots(sales):
    factory, first, second, third = sales
    rows = history.list_sales()
    assert [row.id for row in rows] == [third.id, second.id, first.id]
    assert rows[-1].customer_name == "Ana" and rows[0].customer_name == "Walk-in"
    assert rows[1].cashier_name == "Cashier" and rows[1].payment_method == "gcash"
    assert all(row.refunded_amount == Decimal("0.00") for row in rows)
    with factory.begin() as session:
        session.get(Product, 1).name = "Renamed ball"
        session.get(Product, 1).unit_price = 999
    detail = history.get_sale(first.id)
    assert (
        detail.items[0].product_name == "Original ball"
        and detail.items[0].unit_price == 10
    )
    assert detail.items[0].quantity == 3 and detail.items[0].line_total == 30
    assert detail.amount_received == 50 and detail.change_amount == 20
    assert history.get_sale(second.id).gcash_reference == "REF-1"


def test_inclusive_dates_receipt_cashier_method_and_customer_filters(sales):
    _, first, second, third = sales
    assert [
        row.id
        for row in history.list_sales(
            date_from=date(2026, 10, 24), date_to=date(2026, 10, 24)
        )
    ] == [second.id, first.id]
    assert [
        row.id
        for row in history.list_sales(receipt_number=first.receipt_number.lower())
    ] == [first.id]
    assert history.list_sales(receipt_number="%") == []
    assert history.list_sales(receipt_number="_") == []
    assert [
        row.id for row in history.list_sales(cashier_id=2, payment_method="cash")
    ] == [third.id]
    assert [row.id for row in history.list_sales(customer_id=1)] == [first.id]
    assert history.list_sales(customer_id=999) == []


def test_refund_sum_approved_only_without_duplicate_sales(sales):
    _, first, _, _ = sales
    with patch.object(refund_service, "datetime") as clock:
        clock.now.return_value = datetime(2026, 10, 24, 12)
        item = refund_service.lookup_receipt(first.receipt_number).items[0]
        approved = refund_service.create_request(
            first.receipt_number, [RefundLineInput(item.id, 1)], "Return"
        )
        refund_service.approve(approved.id, {approved.items[0].id: False})
        rejected = refund_service.create_request(
            first.receipt_number, [RefundLineInput(item.id, 1)], "Return"
        )
        refund_service.reject(rejected.id, "No")
        refund_service.create_request(
            first.receipt_number, [RefundLineInput(item.id, 1)], "Pending"
        )
    rows = history.list_sales(customer_id=1)
    assert len(rows) == 1 and rows[0].refunded_amount == Decimal("10.00")
    assert history.get_sale(first.id).summary == rows[0]


@pytest.mark.parametrize(
    "filters",
    [
        {"date_from": "2026-10-24"},
        {"date_to": datetime(2026, 10, 24)},
        {"date_from": date(2026, 10, 25), "date_to": date(2026, 10, 24)},
        {"payment_method": "card"},
        {"cashier_id": True},
        {"customer_id": -1},
        {"receipt_number": "x" * 31},
    ],
)
def test_invalid_filters(sales, filters):
    with pytest.raises(ValidationError):
        history.list_sales(**filters)


def test_missing_held_and_invalid_sale(sales):
    factory, _, _, _ = sales
    with factory() as session:
        held_id = session.scalar(select(Sale.id).where(Sale.status == "held"))
    for sale_id in (999, held_id):
        with pytest.raises(NotFoundError):
            history.get_sale(sale_id)
    with pytest.raises(ValidationError):
        history.get_sale(True)


def test_owner_customer_edit_preserves_sales_and_validates(sales):
    factory, first, _, _ = sales
    updated = customer_service.update_customer(1, " Ana Cruz ", " ")
    assert updated.name == "Ana Cruz" and updated.contact == ""
    assert history.get_sale(first.id).summary.customer_name == "Ana Cruz"
    with factory() as session:
        assert session.get(Sale, first.id).customer_id == 1
        assert session.get(Customer, 1).contact is None
    for changes in (
        (1, " ", ""),
        (1, "x" * 121, ""),
        (1, "Ana", "x" * 121),
        (True, "Ana", ""),
    ):
        with pytest.raises(ValidationError):
            customer_service.update_customer(*changes)
    with pytest.raises(NotFoundError):
        customer_service.update_customer(999, "Missing")


def test_customer_edit_rollback_on_failed_commit(sales):
    factory, _, _, _ = sales

    def fail(_session):
        raise RuntimeError("Commit failed")

    event.listen(factory, "before_commit", fail)
    try:
        with pytest.raises(RuntimeError):
            customer_service.update_customer(1, "Changed")
    finally:
        event.remove(factory, "before_commit", fail)
    assert customer_service.list_customers()[0].name == "Ana"


@pytest.mark.parametrize("actor", ["cashier", "disabled-owner", None])
def test_history_and_customer_edits_require_active_owner(sales, actor):
    factory, first, _, _ = sales
    if actor is None:
        login_session.logout()
    elif actor == "disabled-owner":
        with factory.begin() as session:
            session.get(User, 1).is_active = False
    else:
        sign_in(actor)
    for operation in (
        history.list_sales,
        lambda: history.get_sale(first.id),
        lambda: customer_service.update_customer(1, "Forbidden"),
    ):
        with pytest.raises(AuthError):
            operation()
