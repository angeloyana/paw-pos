from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select

from pawpos.core import session as login_session
from pawpos.core.errors import (
    AuthError,
    BusinessRuleError,
    NotFoundError,
    ValidationError,
)
from pawpos.core.session import CurrentUser
from pawpos.models import (
    Category,
    Product,
    RefundItem,
    RefundRequest,
    Sale,
    StockMovement,
    User,
)
from pawpos.services import refund_service as refunds
from pawpos.services import sale_service
from pawpos.services.cart import Cart
from pawpos.services.refund_service import RefundLineInput as Line
from pawpos.services.sale_service import Payment

NOW = datetime(2026, 10, 24, 12)


def sign_in(role="cashier"):
    login_session.set_current_user(
        CurrentUser(1 if role == "cashier" else 2, role, role.title(), role)
    )


@pytest.fixture
def sold(session_factory):
    with session_factory.begin() as session:
        session.add_all(
            [
                User(
                    id=1,
                    username="cashier",
                    full_name="Cashier",
                    role="cashier",
                    password_hash="unused",
                ),
                User(
                    id=2,
                    username="owner",
                    full_name="Owner",
                    role="owner",
                    password_hash="unused",
                ),
            ]
        )
        toys = Category(name="Toys", is_food=False)
        food = Category(name="Food", is_food=True)
        session.add_all([toys, food])
        session.flush()
        session.add_all(
            [
                Product(
                    id=1,
                    name="Ball",
                    category_id=toys.id,
                    unit_type="piece",
                    unit_price=10,
                    stock_quantity=10,
                ),
                Product(
                    id=2,
                    name="Loose food",
                    category_id=food.id,
                    unit_type="kg",
                    unit_price=95,
                    stock_quantity=10,
                ),
            ]
        )
    sign_in()
    cart = Cart()
    cart.add_piece(1, "Ball", "10", 3, stock_quantity=10)
    cart.add_weight(2, "Loose food", "95", "1.375", stock_quantity=10)
    sale = sale_service.complete_sale(cart, Payment("cash", "200"))
    with session_factory.begin() as session:
        session.get(Sale, sale.id).completed_at = NOW
    with patch.object(refunds, "datetime") as clock:
        clock.now.return_value = NOW
        yield session_factory, sale, refunds.lookup_receipt(sale.receipt_number)


def request(sold, index=0, amount="1", opened=False):
    _, sale, details = sold
    return refunds.create_request(
        sale.receipt_number, [Line(details.items[index].id, amount, opened)], "Return"
    )


def test_request_snapshots_and_pending_reserve_without_stock_change(sold):
    factory, sale, details = sold
    result = request(sold)
    assert result.status == "pending" and result.total_amount == Decimal("10.00")
    assert (
        result.receipt_number == sale.receipt_number and result.requester == "Cashier"
    )
    assert result.reviewer is None and result.items[0].resellable is None
    assert refunds.remaining_refundable(details.items[0].id) == 2
    assert refunds.lookup_receipt(sale.receipt_number).items[0].remaining == 2
    with factory() as session:
        assert session.get(Product, 1).stock_quantity == 7
        assert session.scalar(select(func.count()).select_from(StockMovement)) == 2


@pytest.mark.parametrize(
    "age,allowed",
    [
        (timedelta(days=7), True),
        (timedelta(days=7, microseconds=1), False),
        (timedelta(seconds=-1), False),
    ],
)
def test_window_exact_boundary_and_future_sale(sold, age, allowed):
    factory, sale, _ = sold
    with factory.begin() as session:
        session.get(Sale, sale.id).completed_at = NOW - age
    if allowed:
        assert request(sold).status == "pending"
    else:
        with pytest.raises(BusinessRuleError, match="7 days"):
            request(sold)


@pytest.mark.parametrize("receipt", ["", " ", "missing", "x" * 31, None])
def test_valid_completed_receipt_required(sold, receipt):
    _, _, details = sold
    with pytest.raises((ValidationError, NotFoundError)):
        refunds.create_request(receipt, [Line(details.items[0].id, 1)], "Return")


def test_held_or_uncompleted_receipt_cannot_refund(sold):
    factory, sale, _ = sold
    for status, completed in (("held", NOW), ("completed", None)):
        with factory.begin() as session:
            row = session.get(Sale, sale.id)
            row.status, row.completed_at = status, completed
        with pytest.raises(NotFoundError):
            request(sold)


def test_opened_food_blocked_opened_nonfood_allowed(sold):
    with pytest.raises(BusinessRuleError, match="Opened food"):
        request(sold, 1, "0.5", True)
    result = request(sold, opened=True)
    assert result.items[0].is_opened


@pytest.mark.parametrize(
    "index,amount",
    [
        (0, "1.5"),
        (0, "0"),
        (0, "-1"),
        (0, "4"),
        (1, "0.0001"),
        (1, "1.376"),
        (1, "NaN"),
        (1, 0.5),
    ],
)
def test_quantity_precision_positive_and_remaining(sold, index, amount):
    with pytest.raises((ValidationError, BusinessRuleError)):
        request(sold, index, amount)
    factory, _, _ = sold
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RefundRequest)) == 0


def test_pending_approved_overrefund_and_rejection_release(sold):
    _, _, details = sold
    first = request(sold, amount="2")
    with pytest.raises(BusinessRuleError, match="remaining"):
        request(sold, amount="2")
    sign_in("owner")
    refunds.reject(first.id, "Wrong return")
    assert refunds.remaining_refundable(details.items[0].id) == 3
    second = request(sold, amount="2")
    refunds.approve(second.id, {second.items[0].id: False})
    assert refunds.remaining_refundable(details.items[0].id) == 1
    with pytest.raises(BusinessRuleError):
        request(sold, amount="2")
    assert refunds.pending_refund_count() == 0
    assert len(refunds.list_history()) == 2


def test_approval_mixed_resellable_flags_stock_history_and_actor(sold):
    factory, sale, details = sold
    result = refunds.create_request(
        sale.receipt_number,
        [Line(details.items[0].id, 2), Line(details.items[1].id, "1.375")],
        "Return",
    )
    assert result.total_amount == Decimal("150.63")
    sign_in("owner")
    assert refunds.pending_refund_count() == 1
    assert refunds.list_pending()[0] == result
    # Waiting for review does not invalidate a timely request.
    with patch.object(refunds, "datetime") as clock:
        clock.now.return_value = NOW + timedelta(days=9)
        approved = refunds.approve(
            result.id, {result.items[0].id: False, result.items[1].id: True}
        )
    assert approved.status == "approved" and approved.reviewer == "Owner"
    assert approved.reviewed_at == NOW + timedelta(days=9)
    assert refunds.list_pending() == []
    with factory() as session:
        assert session.get(Product, 1).stock_quantity == 7
        assert session.get(Product, 2).stock_quantity == 10
        movement = session.scalar(
            select(StockMovement).where(StockMovement.movement_type == "refund")
        )
        assert (
            movement.quantity_change == Decimal("1.375") and movement.stock_after == 10
        )
        assert (
            movement.reference_id == result.id and movement.reference_type == "refund"
        )
        assert movement.user_id == 2 and movement.note == "Return"
    with pytest.raises(BusinessRuleError, match="already"):
        refunds.approve(
            result.id, {result.items[0].id: False, result.items[1].id: True}
        )
    with pytest.raises(BusinessRuleError):
        refunds.reject(result.id, "Again")


def test_rejection_requires_note_and_does_not_restore_stock(sold):
    factory, _, details = sold
    result = request(sold)
    sign_in("owner")
    with pytest.raises(ValidationError):
        refunds.reject(result.id, " ")
    rejected = refunds.reject(result.id, " Not eligible ")
    assert rejected.status == "rejected" and rejected.review_note == "Not eligible"
    assert refunds.remaining_refundable(details.items[0].id) == 3
    with factory() as session:
        assert session.get(Product, 1).stock_quantity == 7
        assert session.scalar(select(func.count()).select_from(StockMovement)) == 2


@pytest.mark.parametrize("mapping", [{}, {999: True}, {1: "yes"}, {True: True}])
def test_approval_requires_explicit_boolean_for_every_line(sold, mapping):
    result = request(sold)
    sign_in("owner")
    with pytest.raises(ValidationError):
        refunds.approve(result.id, mapping)
    assert refunds.list_pending()[0].items[0].resellable is None


def test_duplicate_foreign_missing_lines_reason_and_opened_validation(sold):
    _, sale, details = sold
    line = Line(details.items[0].id, 1)
    for lines, reason in (
        ([], "Return"),
        ([line, line], "Return"),
        ([Line(999, 1)], "Return"),
        ([Line(True, 1)], "Return"),
        ([line], " "),
        ([line], "x" * 256),
        ([Line(line.sale_item_id, 1, "false")], "Return"),
        ([None], "Return"),
    ):
        with pytest.raises(ValidationError):
            refunds.create_request(sale.receipt_number, lines, reason)


def test_missing_refund_and_sale_item(sold):
    with pytest.raises(NotFoundError):
        refunds.remaining_refundable(999)
    sign_in("owner")
    with pytest.raises(NotFoundError):
        refunds.approve(999, {})
    with pytest.raises(NotFoundError):
        refunds.reject(999, "Missing")


def test_owner_only_review_and_reads_and_disabled_user(sold):
    factory, _, details = sold
    result = request(sold)
    for operation in (
        refunds.list_pending,
        refunds.list_history,
        refunds.pending_refund_count,
        lambda: refunds.approve(result.id, {result.items[0].id: True}),
        lambda: refunds.reject(result.id, "No"),
    ):
        with pytest.raises(AuthError):
            operation()
    for disabled in (False, True):
        if disabled:
            sign_in()
            with factory.begin() as session:
                session.get(User, 1).is_active = False
        else:
            login_session.logout()
        with pytest.raises(AuthError):
            request(sold)
        with pytest.raises(AuthError):
            refunds.remaining_refundable(details.items[0].id)
        with pytest.raises(AuthError):
            refunds.lookup_receipt(sold[1].receipt_number)


def test_request_and_approval_rollback_on_database_failure(sold):
    factory, _, details = sold

    def fail(_session):
        raise RuntimeError("Commit failed")

    event.listen(factory, "before_commit", fail)
    try:
        with pytest.raises(RuntimeError):
            request(sold)
    finally:
        event.remove(factory, "before_commit", fail)
    assert refunds.remaining_refundable(details.items[0].id) == 3
    result = request(sold)
    sign_in("owner")
    event.listen(factory, "before_commit", fail)
    try:
        with pytest.raises(RuntimeError):
            refunds.approve(result.id, {result.items[0].id: True})
    finally:
        event.remove(factory, "before_commit", fail)
    assert refunds.list_pending()[0].items[0].resellable is None
    with factory() as session:
        assert session.get(Product, 1).stock_quantity == 7
        assert session.scalar(select(func.count()).select_from(StockMovement)) == 2


def test_stock_overflow_rolls_back_entire_approval(sold):
    factory, _, _ = sold
    result = request(sold)
    sign_in("owner")
    with factory.begin() as session:
        session.get(Product, 1).stock_quantity = Decimal("9999999")
    with pytest.raises(ValidationError):
        refunds.approve(result.id, {result.items[0].id: True})
    assert refunds.list_pending()[0].status == "pending"


def test_refund_uses_sale_price_despite_catalog_changes_and_inactive_product(sold):
    factory, _, _ = sold
    with factory.begin() as session:
        product = session.get(Product, 2)
        product.name, product.unit_price, product.is_active = "Renamed", 500, False
    result = request(sold, 1, "1.375")
    assert result.items[0].product_name == "Loose food"
    assert result.items[0].amount == Decimal("130.63")
    sign_in("owner")
    refunds.approve(result.id, {result.items[0].id: True})
    with factory() as session:
        assert session.get(Product, 2).stock_quantity == 10


def test_insert_failure_on_later_line_rolls_back_request(sold):
    factory, sale, details = sold

    def fail(_mapper, _connection, target):
        if target.sale_item_id == details.items[1].id:
            raise RuntimeError("Item insert failed")

    event.listen(RefundItem, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            refunds.create_request(
                sale.receipt_number,
                [Line(item.id, 1) for item in details.items],
                "Return",
            )
    finally:
        event.remove(RefundItem, "before_insert", fail)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RefundRequest)) == 0
        assert session.scalar(select(func.count()).select_from(RefundItem)) == 0
