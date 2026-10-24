"""Validation shared by category and product services."""

from decimal import Decimal

from pawpos.core.errors import ValidationError
from pawpos.core.money import D, DecimalInput


def text(value: str, label: str, limit: int, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be text.")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"{label} is required.")
    if len(value) > limit:
        raise ValidationError(f"{label} must be at most {limit} characters.")
    return value


def flag(value: bool, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{label} must be yes or no.")
    return value


def number(value: DecimalInput, label: str, places: int, maximum: str) -> Decimal:
    result = D(value)
    if result < 0 or result > D(maximum):
        raise ValidationError(f"{label} must be between 0 and {maximum}.")
    if result != result.quantize(Decimal(1).scaleb(-places)):
        raise ValidationError(f"{label} allows at most {places} decimal places.")
    return result


def quantity(value: DecimalInput, label: str, unit_type: str) -> Decimal:
    if unit_type not in ("piece", "kg"):
        raise ValidationError("Unit type must be piece or kg.")
    return number(value, label, 0 if unit_type == "piece" else 3, "9999999.999")
