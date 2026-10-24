from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from pawpos.core import session as login_session
from pawpos.core.errors import (
    AuthError,
    BusinessRuleError,
    NotFoundError,
    ValidationError,
)
from pawpos.core.session import CurrentUser
from pawpos.db import base
from pawpos.models import (
    Category,
    Customer,
    Product,
    Sale,
    SaleItem,
    StockMovement,
    User,
    VoidLog,
)
from pawpos.services import sale_service
from pawpos.services.cart import Cart
from pawpos.services.sale_service import Payment


def populate(factory):
    with factory.begin() as session:
        user = User(
            username="cashier",
            full_name="Cashier One",
            role="cashier",
            password_hash="unused",
        )
        category = Category(name="Food")
        session.add_all(
            [user, category, Customer(name="Test Customer", contact="Test contact")]
        )
        session.flush()
        session.add_all(
            [
                Product(
                    name="Pouch",
                    category_id=category.id,
                    unit_type="piece",
                    unit_price=28,
                    stock_quantity=3,
                ),
                Product(
                    name="Loose food",
                    category_id=category.id,
                    unit_type="kg",
                    unit_price=95,
                    stock_quantity=2,
                ),
            ]
        )
    login_session.set_current_user(CurrentUser(1, "cashier", "Cashier One", "cashier"))
    cart = Cart()
    cart.add_piece(1, "Pouch", 28, 2, stock_quantity=3)
    cart.add_weight(2, "Loose food", 95, "1.375", stock_quantity=2)
    return cart


@pytest.fixture
def draft(session_factory):
    return session_factory, populate(session_factory)


def assert_stock_unchanged(factory):
    with factory() as session:
        assert session.get(Product, 1).stock_quantity == 3
        assert session.get(Product, 2).stock_quantity == 2
        assert session.scalar(select(func.count()).select_from(StockMovement)) == 0


def test_hold_list_and_resume_keep_snapshots_customer_and_stock(draft):
    factory, cart = draft
    held = sale_service.hold_cart(cart, customer_id=1)
    assert held.item_count == 2 and held.total == Decimal("186.63")
    assert held.customer_name == "Test Customer" and held.cashier_name == "Cashier One"
    assert sale_service.list_held() == [held]
    assert len(cart.lines) == 2
    with factory() as session:
        sale = session.get(Sale, held.id)
        assert sale.status == "held" and sale.receipt_number is None
        assert sale.payment_method is None and sale.completed_at is None
    resumed = sale_service.resume_held(held.id)
    assert resumed.cart.lines == cart.lines
    assert resumed.customer.id == 1 and resumed.customer.contact == "Test contact"
    assert sale_service.list_held() == []
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SaleItem)) == 0
        assert session.scalar(select(func.count()).select_from(VoidLog)) == 0
    with pytest.raises(NotFoundError):
        sale_service.resume_held(held.id)
    assert_stock_unchanged(factory)


def test_held_cart_survives_disposed_engine_and_recreated_sessions(
    tmp_path, monkeypatch
):
    url = f"sqlite+pysqlite:///{tmp_path / 'restart.db'}"
    first = create_engine(url)
    base.init_db(first)
    factory = sessionmaker(bind=first, expire_on_commit=False)
    monkeypatch.setattr(base, "SessionLocal", factory)
    cart = populate(factory)
    held = sale_service.hold_cart(cart, customer_id=1)
    first.dispose()
    login_session.logout()
    second = create_engine(url)
    reopened = sessionmaker(bind=second, expire_on_commit=False)
    monkeypatch.setattr(base, "SessionLocal", reopened)
    login_session.set_current_user(CurrentUser(1, "cashier", "Cashier One", "cashier"))
    try:
        assert sale_service.list_held()[0].id == held.id
        assert sale_service.resume_held(held.id).cart.lines == cart.lines
        assert_stock_unchanged(reopened)
    finally:
        login_session.logout()
        second.dispose()


def test_stale_stock_or_inactive_product_does_not_prevent_resume(draft):
    factory, cart = draft
    held = sale_service.hold_cart(cart)
    with factory.begin() as session:
        product = session.get(Product, 2)
        product.name = "Renamed"
        product.unit_price = 120
        product.stock_quantity = 0
    resumed = sale_service.resume_held(held.id)
    assert resumed.cart.lines == cart.lines
    assert resumed.customer is None
    with pytest.raises(BusinessRuleError, match="Loose food"):
        sale_service.complete_sale(resumed.cart, Payment("cash", 200))
    # A draft can be held again while stock is short; nothing is reserved.
    again = sale_service.hold_cart(resumed.cart)
    with factory.begin() as session:
        session.get(Product, 2).is_active = False
    assert sale_service.resume_held(again.id).cart.lines == cart.lines


def test_void_line_then_all_log_reason_user_quantity_and_amount(draft):
    factory, cart = draft
    sale_service.void_line(cart, 2, " Wrong weight ")
    assert len(cart.lines) == 1 and cart.total == 56
    sale_service.void_all(cart, "Customer changed mind")
    assert cart.lines == ()
    with factory() as session:
        logs = session.scalars(select(VoidLog).order_by(VoidLog.id)).all()
        assert [
            (row.product_name, row.quantity, row.amount, row.void_scope, row.reason)
            for row in logs
        ] == [
            ("Loose food", Decimal("1.375"), Decimal("130.63"), "line", "Wrong weight"),
            (
                "Pouch",
                Decimal("2"),
                Decimal("56"),
                "transaction",
                "Customer changed mind",
            ),
        ]
        assert all(row.user_id == 1 and row.created_at for row in logs)
    assert_stock_unchanged(factory)


def test_cancel_held_logs_each_line_and_deletes_items_without_affecting_draft(draft):
    factory, cart = draft
    held = sale_service.hold_cart(cart, customer_id=1)
    before = cart.lines
    sale_service.cancel_held(held.id, "Customer left")
    assert sale_service.list_held() == [] and cart.lines == before
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(SaleItem)) == 0
        logs = session.scalars(select(VoidLog).order_by(VoidLog.id)).all()
        assert [row.amount for row in logs] == [Decimal("56"), Decimal("130.63")]
        assert all(
            row.void_scope == "transaction" and row.reason == "Customer left"
            for row in logs
        )
    assert_stock_unchanged(factory)


@pytest.mark.parametrize("operation", ["line", "all", "held"])
@pytest.mark.parametrize("reason", ["", "   ", None, "x" * 256])
def test_invalid_reason_changes_nothing(draft, operation, reason):
    factory, cart = draft
    held = sale_service.hold_cart(cart)
    before = cart.lines
    with pytest.raises(ValidationError):
        if operation == "line":
            sale_service.void_line(cart, 1, reason)
        elif operation == "all":
            sale_service.void_all(cart, reason)
        else:
            sale_service.cancel_held(held.id, reason)
    assert cart.lines == before and sale_service.list_held() == [held]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(VoidLog)) == 0
    assert_stock_unchanged(factory)


@pytest.mark.parametrize("operation", ["all", "held"])
def test_mid_void_write_failure_preserves_everything(draft, operation):
    factory, cart = draft
    held = sale_service.hold_cart(cart)
    before = cart.lines
    inserted = 0

    def fail_on_second(_mapper, _connection, _target):
        nonlocal inserted
        inserted += 1
        if inserted == 2:
            raise RuntimeError("simulated void write failure")

    event.listen(VoidLog, "before_insert", fail_on_second)
    try:
        with pytest.raises(RuntimeError, match="void write"):
            if operation == "all":
                sale_service.void_all(cart, "Customer left")
            else:
                sale_service.cancel_held(held.id, "Customer left")
    finally:
        event.remove(VoidLog, "before_insert", fail_on_second)
    assert cart.lines == before and sale_service.list_held() == [held]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(VoidLog)) == 0
        assert session.scalar(select(func.count()).select_from(SaleItem)) == 2
    assert_stock_unchanged(factory)


def test_hold_failure_and_resume_delete_failure_are_atomic(draft):
    factory, cart = draft

    def fail(_mapper, _connection, _target):
        raise RuntimeError("simulated write failure")

    event.listen(SaleItem, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError):
            sale_service.hold_cart(cart)
    finally:
        event.remove(SaleItem, "before_insert", fail)
    assert sale_service.list_held() == [] and len(cart.lines) == 2
    held = sale_service.hold_cart(cart)
    event.listen(Sale, "before_delete", fail)
    try:
        with pytest.raises(RuntimeError):
            sale_service.resume_held(held.id)
    finally:
        event.remove(Sale, "before_delete", fail)
    assert sale_service.list_held() == [held]
    assert_stock_unchanged(factory)


def test_completed_sales_cannot_resume_or_cancel_and_missing_line_is_rejected(draft):
    factory, cart = draft
    completed = sale_service.complete_sale(cart, Payment("cash", 200))
    with pytest.raises(NotFoundError):
        sale_service.resume_held(completed.id)
    with pytest.raises(NotFoundError):
        sale_service.cancel_held(completed.id, "Wrong item")
    with pytest.raises(NotFoundError):
        sale_service.void_line(cart, 999, "Wrong item")
    with pytest.raises(ValidationError):
        sale_service.resume_held(True)
    assert len(cart.lines) == 2
    with factory() as session:
        assert session.get(Sale, completed.id).status == "completed"
        assert session.scalar(select(func.count()).select_from(VoidLog)) == 0


def test_empty_draft_and_invalid_customer(draft):
    factory, cart = draft
    for action in (
        lambda: sale_service.hold_cart(Cart()),
        lambda: sale_service.void_all(Cart(), "Wrong item"),
        lambda: sale_service.void_line(Cart(), 1, "Wrong item"),
        lambda: sale_service.hold_cart(cart, customer_id=999),
    ):
        with pytest.raises(ValidationError):
            action()
    assert sale_service.list_held() == []
    assert_stock_unchanged(factory)


def test_shared_held_carts_and_current_actor_authentication(draft):
    factory, cart = draft
    held = sale_service.hold_cart(cart)
    with factory.begin() as session:
        session.add(
            User(
                username="other",
                full_name="Other cashier",
                role="cashier",
                password_hash="unused",
            )
        )
    login_session.set_current_user(CurrentUser(2, "other", "Other cashier", "cashier"))
    assert sale_service.list_held() == [held]
    sale_service.cancel_held(held.id, "Customer left")
    with factory() as session:
        assert all(row.user_id == 2 for row in session.scalars(select(VoidLog)))
    with factory.begin() as session:
        session.get(User, 2).is_active = False
    for action in (
        sale_service.list_held,
        lambda: sale_service.hold_cart(cart),
        lambda: sale_service.resume_held(held.id),
        lambda: sale_service.cancel_held(held.id, "Wrong item"),
        lambda: sale_service.void_all(cart, "Wrong item"),
        lambda: sale_service.void_line(cart, 1, "Wrong item"),
    ):
        with pytest.raises(AuthError):
            action()
    assert len(cart.lines) == 2
    assert_stock_unchanged(factory)
