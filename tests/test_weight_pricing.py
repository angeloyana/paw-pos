from decimal import Decimal

import pytest

from pawpos.core.errors import BusinessRuleError, ValidationError
from pawpos.services.cart import Cart


def test_required_weight_price_rounds_half_up():
    cart = Cart()
    line = cart.add_weight(1, "Dog food", "95.00", "1.375", stock_quantity=50)
    assert line.quantity == Decimal("1.375")
    assert line.unit_price == Decimal("95.00")
    assert line.line_total == Decimal("130.63")
    assert cart.total == Decimal("130.63")


def test_merged_weights_recompute_rounded_line_total():
    cart = Cart()
    cart.add_weight(1, "Food", "5", "0.001", stock_quantity=1)
    line = cart.add_weight(1, "Food", "5", "0.001", stock_quantity=1)
    assert len(cart.lines) == 1
    assert line.quantity == Decimal("0.002")
    assert line.line_total == Decimal("0.01")


def test_total_sums_rounded_lines_for_mixed_units():
    cart = Cart()
    cart.add_weight(1, "Dog food", "95", "1.375", stock_quantity=50)
    cart.add_weight(2, "Cat food", "5", "0.001", stock_quantity=40)
    cart.add_piece(3, "Pouch", "28", 2, stock_quantity=60)
    assert cart.total == Decimal("186.64")


def test_weight_edit_and_exact_stock_limit():
    cart = Cart()
    cart.add_weight(1, "Food", "95", "1.0000", stock_quantity="1.375")
    line = cart.set_quantity(1, "1.375", stock_quantity="1.375")
    assert line.line_total == Decimal("130.63")
    with pytest.raises(BusinessRuleError):
        cart.add_weight(1, "Food", "95", "0.001", stock_quantity="1.375")
    with pytest.raises(BusinessRuleError):
        cart.set_quantity(1, "1.376", stock_quantity="1.375")
    assert cart.lines == (line,)


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        "0.0001",
        "1.3751",
        "NaN",
        "Infinity",
        "abc",
        "",
        True,
        1.375,
        None,
        "10000000",
        "1e100",
        "1e-100",
    ],
)
def test_invalid_weights_are_rejected_on_add_and_edit(value):
    cart = Cart()
    cart.add_weight(1, "Food", "95", 1, stock_quantity=50)
    before = cart.lines
    with pytest.raises(ValidationError):
        cart.add_weight(1, "Food", "95", value, stock_quantity=50)
    with pytest.raises(ValidationError):
        cart.set_quantity(1, value, stock_quantity=50)
    assert cart.lines == before


def test_stock_precision_and_zero_stock():
    cart = Cart()
    with pytest.raises(ValidationError):
        cart.add_weight(1, "Food", "95", 1, stock_quantity="1.0001")
    with pytest.raises(BusinessRuleError):
        cart.add_weight(1, "Food", "95", "0.001", stock_quantity=0)
    assert cart.lines == ()


def test_merged_quantity_cannot_exceed_database_limit():
    cart = Cart()
    cart.add_weight(1, "Free sample", 0, "9999999.999", stock_quantity="9999999.999")
    before = cart.lines
    with pytest.raises(ValidationError):
        cart.add_weight(1, "Free sample", 0, "0.001", stock_quantity="9999999.999")
    assert cart.lines == before
