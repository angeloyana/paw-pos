from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from pawpos.core.errors import BusinessRuleError, NotFoundError, ValidationError
from pawpos.services.cart import Cart


def test_empty_cart_and_independent_instances():
    cart = Cart()
    assert cart.lines == ()
    assert cart.total == Decimal("0.00")
    assert isinstance(cart.total, Decimal)
    cart.add_piece(1, "Toy", "150.00", stock_quantity=12)
    assert Cart().lines == ()


def test_piece_merge_order_and_totals():
    cart = Cart()
    cart.add_piece(1, "Toy", "150.00", stock_quantity=12)
    cart.add_piece(2, "Pouch", "28.00", 2, stock_quantity=60)
    line = cart.add_piece(1, "Toy", "150.00", 2, stock_quantity=12)
    assert [line.product_id for line in cart.lines] == [1, 2]
    assert line.quantity == Decimal("3")
    assert line.line_total == Decimal("450.00")
    assert cart.total == Decimal("506.00")


def test_edit_remove_clear_and_readd():
    cart = Cart()
    original = cart.add_piece(1, "Toy", "150.00", stock_quantity=12)
    edited = cart.set_quantity(1, "4.000", stock_quantity=12)
    assert original.quantity == 1
    assert edited.quantity == 4
    assert cart.total == Decimal("600.00")
    cart.remove_line(1)
    assert cart.lines == ()
    assert cart.total == 0
    cart.add_piece(1, "New toy", "160.00", stock_quantity=12)
    assert cart.total == Decimal("160.00")
    cart.clear()
    cart.clear()
    assert cart.lines == ()
    assert cart.total == 0


@pytest.mark.parametrize("operation", ["add", "merge", "edit"])
def test_stock_checks_leave_cart_unchanged(operation):
    cart = Cart()
    cart.add_piece(1, "Toy", "150.00", 2, stock_quantity=3)
    before = cart.lines
    with pytest.raises(BusinessRuleError, match="Not enough stock for Toy"):
        if operation == "add":
            cart.add_piece(2, "Toy", "150.00", stock_quantity=0)
        elif operation == "merge":
            cart.add_piece(1, "Toy", "150.00", 2, stock_quantity=3)
        else:
            cart.set_quantity(1, 2, stock_quantity=1)
    assert cart.lines == before


def test_stock_boundary_is_allowed():
    cart = Cart()
    cart.add_piece(1, "Toy", "150.00", 3, stock_quantity=3)
    assert cart.set_quantity(1, 2, stock_quantity=2).quantity == 2


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        "1.5",
        "0.001",
        "",
        "oops",
        "NaN",
        "Infinity",
        True,
        1.0,
        None,
        "10000000",
        "1e100",
        "1e-100",
    ],
)
def test_invalid_piece_quantities_do_not_change_cart(value):
    cart = Cart()
    cart.add_piece(1, "Toy", "150", stock_quantity=12)
    before = cart.lines
    with pytest.raises(ValidationError):
        cart.add_piece(1, "Toy", "150", value, stock_quantity=12)
    with pytest.raises(ValidationError):
        cart.set_quantity(1, value, stock_quantity=12)
    assert cart.lines == before


@pytest.mark.parametrize("stock", [-1, "1.5", "NaN", 3.0, True, "10000000"])
def test_invalid_stock_is_rejected(stock):
    cart = Cart()
    with pytest.raises(ValidationError):
        cart.add_piece(1, "Toy", "150", stock_quantity=stock)
    assert cart.lines == ()


@pytest.mark.parametrize("price", [-1, "1.001", "NaN", 1.0, True, "100000000"])
def test_invalid_price_is_rejected(price):
    cart = Cart()
    with pytest.raises(ValidationError):
        cart.add_piece(1, "Toy", price, stock_quantity=12)
    assert cart.lines == ()


@pytest.mark.parametrize("product_id", [0, -1, True, "1", 1.0, None])
def test_invalid_product_identity_is_rejected(product_id):
    cart = Cart()
    with pytest.raises(ValidationError):
        cart.add_piece(product_id, "Toy", "150", stock_quantity=12)
    with pytest.raises(ValidationError):
        cart.remove_line(product_id)


@pytest.mark.parametrize("name", ["", "   ", "x" * 121, None])
def test_invalid_name_is_rejected(name):
    with pytest.raises(ValidationError):
        Cart().add_piece(1, name, "150", stock_quantity=12)


def test_missing_line_errors():
    cart = Cart()
    with pytest.raises(NotFoundError):
        cart.set_quantity(1, 2, stock_quantity=12)
    with pytest.raises(NotFoundError):
        cart.remove_line(1)


def test_cart_snapshots_cannot_bypass_validation():
    cart = Cart()
    line = cart.add_piece(1, "Toy", "150", stock_quantity=12)
    snapshot = cart.lines
    with pytest.raises(FrozenInstanceError):
        line.quantity = Decimal("100")
    cart.clear()
    assert snapshot == (line,)


def test_merge_retains_original_price_and_name_and_rejects_unit_change():
    cart = Cart()
    cart.add_piece(1, "Toy", "150", stock_quantity=12)
    merged = cart.add_piece(1, "Renamed toy", "200", stock_quantity=12)
    assert merged.product_name == "Toy"
    assert merged.unit_price == Decimal("150")
    assert merged.line_total == Decimal("300.00")
    with pytest.raises(BusinessRuleError, match="unit type"):
        cart.add_weight(1, "Toy", "150", "0.5", stock_quantity=12)
    assert cart.lines == (merged,)


def test_database_amount_limits_are_checked_before_mutating():
    cart = Cart()
    cart.add_piece(1, "Expensive", "99999999.99", stock_quantity=2)
    before = cart.lines
    with pytest.raises(ValidationError, match="Line total"):
        cart.add_piece(1, "Expensive", "99999999.99", stock_quantity=2)
    with pytest.raises(ValidationError, match="Cart total"):
        cart.add_piece(2, "Extra", "0.01", stock_quantity=1)
    assert cart.lines == before


def test_free_items_are_allowed():
    cart = Cart()
    cart.add_piece(1, "Sample", 0, stock_quantity=1)
    assert len(cart.lines) == 1
    assert cart.total == Decimal("0.00")
