"""Decimal conversion and display helpers for money and quantities."""

from decimal import ROUND_HALF_UP, Decimal, DecimalException

from pawpos.core.errors import ValidationError

DecimalInput = Decimal | str | int


def D(value: DecimalInput) -> Decimal:
    """Reject floats and non-finite numbers before they reach calculations."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
        raise ValidationError("Enter a number as text, an integer, or a Decimal.")
    try:
        result = Decimal(value)
    except (DecimalException, ValueError):
        raise ValidationError("Enter a valid number.") from None
    if not result.is_finite():
        raise ValidationError("Enter a finite number.")
    return result


def round_money(value: DecimalInput) -> Decimal:
    """Round to centavos using the shop's half-up rule."""
    try:
        return D(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except DecimalException:
        raise ValidationError("Amount is too large.") from None


def format_peso(value: DecimalInput) -> str:
    return f"₱{round_money(value):,.2f}"


def format_qty(value: DecimalInput, unit_type: str = "piece") -> str:
    """Display whole pieces or up to three kg decimals without rounding stock."""
    quantity = D(value)
    if unit_type == "piece":
        if quantity != quantity.to_integral_value():
            raise ValidationError("Per-piece quantities must be whole numbers.")
        return f"{quantity:.0f}"
    if unit_type != "kg":
        raise ValidationError("Unit type must be piece or kg.")
    if (
        quantity.as_tuple().exponent < -3
        and quantity.normalize().as_tuple().exponent < -3
    ):
        raise ValidationError("Kilogram quantities allow at most 3 decimals.")
    return f"{quantity:.3f}".rstrip("0").rstrip(".") + " kg"
