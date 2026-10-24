"""In-memory cart with Decimal pricing and no database or login dependency."""

from dataclasses import dataclass, replace
from decimal import Decimal

from pawpos.core.errors import BusinessRuleError, NotFoundError, ValidationError
from pawpos.core.money import DecimalInput, round_money
from pawpos.services.catalog_validation import number, quantity, text


@dataclass(frozen=True)
class CartLine:
    product_id: int
    product_name: str
    unit_type: str
    unit_price: Decimal
    quantity: Decimal

    @property
    def line_total(self) -> Decimal:
        return round_money(self.quantity * self.unit_price)


class Cart:
    """Merge by product, retaining its first name and price until removed."""

    def __init__(self) -> None:
        self._lines: dict[int, CartLine] = {}

    @property
    def lines(self) -> tuple[CartLine, ...]:
        """Return immutable lines in first-added order."""
        return tuple(self._lines.values())

    @property
    def total(self) -> Decimal:
        """Sum rounded line amounts, so the total matches displayed prices."""
        return sum((line.line_total for line in self._lines.values()), Decimal("0.00"))

    def add_piece(
        self,
        product_id: int,
        product_name: str,
        unit_price: DecimalInput,
        quantity: DecimalInput = 1,
        *,
        stock_quantity: DecimalInput,
    ) -> CartLine:
        """Add whole pieces, checking the merged quantity against current stock."""
        return self._add(
            product_id, product_name, unit_price, "piece", quantity, stock_quantity
        )

    def add_weight(
        self,
        product_id: int,
        product_name: str,
        unit_price: DecimalInput,
        quantity: DecimalInput,
        *,
        stock_quantity: DecimalInput,
    ) -> CartLine:
        """Add kg with up to three decimals, merging weights for the same product."""
        return self._add(
            product_id, product_name, unit_price, "kg", quantity, stock_quantity
        )

    def _add(
        self,
        product_id: int,
        product_name: str,
        unit_price: DecimalInput,
        unit_type: str,
        amount: DecimalInput,
        stock_quantity: DecimalInput,
    ) -> CartLine:
        if type(product_id) is not int or product_id <= 0:
            raise ValidationError("Product ID must be a positive integer.")
        name = text(product_name, "Product name", 120)
        price = number(unit_price, "Price", 2, "99999999.99")
        added = self._positive_quantity(amount, unit_type)
        existing = self._lines.get(product_id)
        if existing is not None:
            if existing.unit_type != unit_type:
                raise BusinessRuleError(
                    "Remove the product before changing its unit type."
                )
            line = replace(existing, quantity=existing.quantity + added)
        else:
            line = CartLine(product_id, name, unit_type, price, added)
        return self._store(line, stock_quantity)

    @staticmethod
    def _positive_quantity(value: DecimalInput, unit_type: str) -> Decimal:
        result = quantity(value, "Quantity", unit_type)
        if result <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        return result

    def _store(self, line: CartLine, stock_quantity: DecimalInput) -> CartLine:
        self._positive_quantity(line.quantity, line.unit_type)
        stock = quantity(stock_quantity, "Available stock", line.unit_type)
        if line.quantity > stock:
            raise BusinessRuleError(f"Not enough stock for {line.product_name}.")
        number(line.line_total, "Line total", 2, "99999999.99")
        new_total = line.line_total + sum(
            (
                other.line_total
                for other in self._lines.values()
                if other.product_id != line.product_id
            ),
            Decimal("0.00"),
        )
        number(new_total, "Cart total", 2, "99999999.99")
        # Validate the entire replacement before mutating the active cart.
        self._lines[line.product_id] = line
        return line

    def _get_line(self, product_id: int) -> CartLine:
        if type(product_id) is not int or product_id <= 0:
            raise ValidationError("Product ID must be a positive integer.")
        try:
            return self._lines[product_id]
        except KeyError:
            raise NotFoundError("Cart line not found.") from None

    def set_quantity(
        self,
        product_id: int,
        quantity: DecimalInput,
        *,
        stock_quantity: DecimalInput,
    ) -> CartLine:
        """Replace a quantity using current stock; zero must use remove_line instead."""
        line = self._get_line(product_id)
        amount = self._positive_quantity(quantity, line.unit_type)
        return self._store(replace(line, quantity=amount), stock_quantity)

    def remove_line(self, product_id: int) -> None:
        """Remove a product, raising NotFoundError when it is absent."""
        self._get_line(product_id)
        del self._lines[product_id]

    def clear(self) -> None:
        """Reset the cart for the next transaction."""
        self._lines.clear()
