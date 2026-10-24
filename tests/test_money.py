import unittest
from decimal import Decimal

from pawpos.core.errors import ValidationError
from pawpos.core.money import D, format_peso, format_qty, round_money


class MoneyTests(unittest.TestCase):
    def test_decimal_inputs(self):
        self.assertEqual(D("1.375"), Decimal("1.375"))
        self.assertEqual(D(2), Decimal("2"))
        self.assertEqual(D(Decimal("95.00")), Decimal("95.00"))

    def test_rejects_inexact_invalid_and_nonfinite_inputs(self):
        for value in (
            1.1,
            True,
            None,
            "",
            "abc",
            "NaN",
            "sNaN",
            "Infinity",
            "-Infinity",
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                D(value)

    def test_weight_price_rounds_half_up(self):
        self.assertEqual(round_money(D("1.375") * D("95.00")), Decimal("130.63"))
        self.assertEqual(round_money("-1.005"), Decimal("-1.01"))

    def test_large_amount_has_a_validation_error(self):
        with self.assertRaises(ValidationError):
            round_money("1e100")

    def test_peso_display(self):
        self.assertEqual(format_peso("1234.5"), "₱1,234.50")
        self.assertEqual(format_peso(0), "₱0.00")

    def test_piece_display(self):
        self.assertEqual(format_qty("12.000"), "12")
        with self.assertRaises(ValidationError):
            format_qty("1.5")

    def test_kg_display(self):
        for value, expected in (
            ("1.500", "1.5 kg"),
            ("0.001", "0.001 kg"),
            ("10", "10 kg"),
            ("0", "0 kg"),
            ("1.0000", "1 kg"),
        ):
            with self.subTest(value=value):
                self.assertEqual(format_qty(value, "kg"), expected)

    def test_quantity_precision_and_unit_are_validated(self):
        for value, unit in (("1.0001", "kg"), ("1", "bag")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                format_qty(value, unit)
