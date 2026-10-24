"""Weight entry and piece quantity editing with a live rounded price."""

import tkinter as tk

import ttkbootstrap as ttk

from pawpos.core.errors import BusinessRuleError, ValidationError
from pawpos.core.money import format_peso, format_qty, round_money
from pawpos.services.catalog_validation import quantity
from pawpos.ui.dialogs.base import ModalDialog


class WeightDialog(ModalDialog):
    def __init__(
        self,
        parent,
        product_name,
        unit_price,
        unit_type,
        stock_quantity,
        initial="",
        *,
        existing_quantity=0,
    ):
        super().__init__(parent, "Weight" if unit_type == "kg" else "Quantity")
        self.unit_price = unit_price
        self.unit_type = unit_type
        self.stock_quantity = stock_quantity
        self.existing_quantity = existing_quantity
        self.value = tk.StringVar(self, value=str(initial))
        self.preview = tk.StringVar(self)
        ttk.Label(self.body, text=product_name, font=("Segoe UI", 16, "bold")).pack()
        ttk.Label(
            self.body,
            text=f"{format_peso(unit_price)}"
            + ("/kg" if unit_type == "kg" else " each"),
        ).pack(pady=6)
        ttk.Label(
            self.body, text=f"Available: {format_qty(stock_quantity, unit_type)}"
        ).pack()
        ttk.Label(
            self.body, text="Weight (kg)" if unit_type == "kg" else "Pieces"
        ).pack(anchor="w", pady=(12, 4))
        self.first_input = ttk.Entry(self.body, textvariable=self.value)
        self.first_input.pack(fill="x")
        ttk.Label(self.body, textvariable=self.preview).pack(pady=12)
        ttk.Label(
            self.body, textvariable=self.error, bootstyle="danger", wraplength=360
        ).pack()
        self.confirm_button = ttk.Button(self.body, text="OK", command=self.confirm)
        self.confirm_button.pack(side="left", pady=12)
        ttk.Button(self.body, text="Cancel", command=self.destroy).pack(side="right")
        self.bind("<Return>", lambda _event: self.confirm())
        self.value.trace_add("write", self.update_preview)
        self.update_preview()

    def validated_quantity(self):
        amount = quantity(self.value.get(), "Quantity", self.unit_type)
        if amount <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        if amount + self.existing_quantity > self.stock_quantity:
            raise BusinessRuleError(
                "Quantity exceeds available stock, including the cart."
            )
        return amount

    def update_preview(self, *_args):
        def calculate():
            amount = self.validated_quantity()
            # A merged weight is priced as one rounded line.
            total = round_money((amount + self.existing_quantity) * self.unit_price)
            self.preview.set(f"Line total: {format_peso(total)}")

        valid = self.perform(calculate)
        self.confirm_button.configure(state="normal" if valid else "disabled")
        if not valid:
            self.preview.set("")

    def confirm(self):
        def accept():
            self.result = self.validated_quantity()

        if self.perform(accept):
            self.destroy()
