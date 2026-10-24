from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError, BusinessRuleError, ValidationError
from pawpos.core.session import CurrentUser
from pawpos.models import (
    Category,
    Customer,
    Product,
    Sale,
    SaleItem,
    StockMovement,
    User,
)
from pawpos.services import sale_service
from pawpos.services.cart import Cart
from pawpos.services.sale_service import Payment


@pytest.fixture
def checkout(session_factory):
    with session_factory.begin() as session:
        user = User(
            username="cashier",
            full_name="Cashier One",
            role="cashier",
            password_hash="unused",
        )
        category = Category(name="Food", is_food=True)
        customer = Customer(name="Test Customer", contact="Test contact")
        session.add_all([user, category, customer])
        session.flush()
        session.add_all(
            [
                Product(
                    name="Pouch",
                    category_id=category.id,
                    unit_type="piece",
                    unit_price=Decimal("28"),
                    stock_quantity=Decimal("3"),
                ),
                Product(
                    name="Loose food",
                    category_id=category.id,
                    unit_type="kg",
                    unit_price=Decimal("95"),
                    stock_quantity=Decimal("2"),
                ),
            ]
        )
        login_session.set_current_user(
            CurrentUser(user.id, user.username, user.full_name, user.role)
        )
    cart = Cart()
    cart.add_piece(1, "Pouch", "28", 2, stock_quantity=3)
    cart.add_weight(2, "Loose food", "95", "1.375", stock_quantity=2)
    return session_factory, cart


def assert_no_sale(factory):
    with factory() as session:
        for model in (Sale, SaleItem, StockMovement):
            assert session.scalar(select(func.count()).select_from(model)) == 0
        assert session.get(Product, 1).stock_quantity == 3
        assert session.get(Product, 2).stock_quantity == 2


def test_cash_sale_snapshots_stock_movements_and_customer(checkout):
    factory, cart = checkout
    with factory.begin() as session:
        session.get(Product, 1).unit_price = Decimal("30")
        session.get(Product, 1).name = "New name"
    result = sale_service.complete_sale(cart, Payment("cash", "200"), customer_id=1)
    assert result.total == Decimal("186.63")
    assert result.receipt_number.startswith(f"PAW-{datetime.now():%Y%m%d}-")
    assert len(cart.lines) == 2
    with factory() as session:
        sale = session.get(Sale, result.id)
        assert (
            sale.status == "completed"
            and sale.cashier_id == 1
            and sale.customer_id == 1
        )
        assert sale.amount_received == 200 and sale.change_amount == Decimal("13.37")
        assert sale.gcash_reference is None and sale.completed_at is not None
        assert [item.product_name for item in sale.items] == ["Pouch", "Loose food"]
        assert sale.items[0].unit_price == 28
        assert sale.items[1].line_total == Decimal("130.63")
        movements = session.scalars(
            select(StockMovement).order_by(StockMovement.product_id)
        ).all()
        assert [row.quantity_change for row in movements] == [
            Decimal("-2"),
            Decimal("-1.375"),
        ]
        assert [row.stock_after for row in movements] == [
            Decimal("1"),
            Decimal("0.625"),
        ]
        assert all(
            row.reference_type == "sale"
            and row.reference_id == sale.id
            and row.user_id == 1
            and row.movement_type == "sale"
            for row in movements
        )
        assert session.get(Product, 1).stock_quantity == 1
        assert session.get(Product, 2).stock_quantity == Decimal("0.625")


def test_gcash_reference_and_no_cash_fields(checkout):
    factory, cart = checkout
    result = sale_service.complete_sale(
        cart, Payment("gcash", gcash_reference=" REF-001 ")
    )
    with factory() as session:
        sale = session.get(Sale, result.id)
        assert sale.gcash_reference == "REF-001" and sale.payment_method == "gcash"
        assert sale.amount_received is None and sale.change_amount is None
        assert sale.customer_id is None


@pytest.mark.parametrize(
    "payment",
    [
        Payment("cash", "186.62"),
        Payment("cash"),
        Payment("cash", 200.0),
        Payment("cash", "200.001"),
        Payment("cash", "NaN"),
        Payment("cash", "100000000"),
        Payment("gcash"),
        Payment("gcash", gcash_reference=" "),
        Payment("gcash", gcash_reference="x" * 51),
        Payment("card"),
        None,
    ],
)
def test_payment_errors_rollback_and_preserve_cart(checkout, payment):
    factory, cart = checkout
    before = cart.lines
    with pytest.raises(ValidationError):
        sale_service.complete_sale(cart, payment)
    assert cart.lines == before
    assert_no_sale(factory)


def test_insufficient_stock_on_later_line_changes_nothing(checkout):
    factory, cart = checkout
    cart.set_quantity(2, "2.001", stock_quantity=3)
    before = cart.lines
    with pytest.raises(BusinessRuleError, match="Loose food"):
        sale_service.complete_sale(cart, Payment("cash", "500"))
    assert cart.lines == before
    assert_no_sale(factory)


def test_failure_during_flush_rolls_back_everything(checkout):
    factory, cart = checkout

    def fail(_mapper, _connection, _target):
        raise RuntimeError("simulated movement failure")

    event.listen(StockMovement, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="movement failure"):
            sale_service.complete_sale(cart, Payment("cash", "200"))
    finally:
        event.remove(StockMovement, "before_insert", fail)
    assert_no_sale(factory)
    assert len(cart.lines) == 2


@pytest.mark.parametrize("change", ["inactive", "category", "units", "missing"])
def test_unavailable_or_changed_product_blocks_sale(checkout, change):
    factory, cart = checkout
    with factory.begin() as session:
        product = session.get(Product, 2)
        if change == "inactive":
            product.is_active = False
        elif change == "category":
            product.category.is_active = False
        elif change == "units":
            product.unit_type = "piece"
        else:
            session.delete(product)
    with pytest.raises(BusinessRuleError):
        sale_service.complete_sale(cart, Payment("cash", "200"))
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Sale)) == 0
        assert session.get(Product, 1).stock_quantity == 3


@pytest.mark.parametrize("customer_id", [999, True, "1", -1])
def test_invalid_customer(checkout, customer_id):
    factory, cart = checkout
    with pytest.raises(ValidationError):
        sale_service.complete_sale(
            cart, Payment("cash", "200"), customer_id=customer_id
        )
    assert_no_sale(factory)


def test_empty_cart_and_inactive_or_missing_login(checkout):
    factory, cart = checkout
    with pytest.raises(ValidationError, match="empty"):
        sale_service.complete_sale(Cart(), Payment("cash", "200"))
    with factory.begin() as session:
        session.get(User, 1).is_active = False
    with pytest.raises(AuthError):
        sale_service.complete_sale(cart, Payment("cash", "200"))
    login_session.logout()
    with pytest.raises(AuthError):
        sale_service.complete_sale(cart, Payment("cash", "200"))
    assert_no_sale(factory)


def test_receipt_sequence_resets_by_day_and_ignores_held(checkout):
    factory, _cart = checkout
    cart = Cart()
    cart.add_piece(1, "Pouch", 28, stock_quantity=3)
    with factory.begin() as session:
        session.add(Sale(status="held", cashier_id=1, total=0))
    with patch.object(sale_service, "datetime") as clock:
        clock.now.return_value = datetime(2026, 10, 24, 12)
        first = sale_service.complete_sale(cart, Payment("cash", "28"))
        second = sale_service.complete_sale(cart, Payment("cash", "28"))
        clock.now.return_value = datetime(2026, 10, 25, 12)
        third = sale_service.complete_sale(cart, Payment("cash", "28"))
    assert first.receipt_number == "PAW-20261024-0001"
    assert second.receipt_number == "PAW-20261024-0002"
    assert third.receipt_number == "PAW-20261025-0001"


def test_free_sale_exact_cash_and_receipt_limit(checkout):
    factory, _cart = checkout
    cart = Cart()
    cart.add_piece(1, "Sample", 0, stock_quantity=3)
    result = sale_service.complete_sale(cart, Payment("cash", 0))
    assert result.total == 0
    with factory.begin() as session:
        session.get(
            Sale, result.id
        ).receipt_number = f"PAW-{datetime.now():%Y%m%d}-9999"
    with pytest.raises(BusinessRuleError, match="limit"):
        sale_service.complete_sale(cart, Payment("cash", 0))
    with factory() as session:
        assert session.get(Product, 1).stock_quantity == 2
        assert session.scalar(select(func.count()).select_from(Sale)) == 1
