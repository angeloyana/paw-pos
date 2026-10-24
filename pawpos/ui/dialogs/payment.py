"""Cash/GCash tender entry and confirmation of an atomic sale."""

import tkinter as tk

import ttkbootstrap as ttk

from pawpos.core.money import format_peso
from pawpos.services import sale_service
from pawpos.services.sale_service import Payment
from pawpos.ui.dialogs.base import ModalDialog


class PaymentDialog(ModalDialog):
    def __init__(self, parent, cart, customer_id=None):
        super().__init__(parent, "Payment")
        self.cart = cart
        self.customer_id = customer_id
        self.submitting = False
        self.method = tk.StringVar(self, value="cash")
        self.amount = tk.StringVar(self)
        self.reference = tk.StringVar(self)
        self.change = tk.StringVar(self)
        ttk.Label(self.body, text="Total", font=("Segoe UI", 14)).pack()
        ttk.Label(
            self.body, text=format_peso(cart.total), font=("Segoe UI", 24, "bold")
        ).pack(pady=(0, 16))
        methods = ttk.Frame(self.body)
        methods.pack(fill="x")
        for method, label in (("cash", "Cash"), ("gcash", "GCash")):
            ttk.Radiobutton(
                methods, text=label, variable=self.method, value=method
            ).pack(side="left", padx=12)
        self.cash_frame = ttk.Frame(self.body)
        self.cash_frame.pack(fill="x", pady=12)
        ttk.Label(self.cash_frame, text="Amount received").pack(anchor="w")
        self.amount_entry = ttk.Entry(
            self.cash_frame, textvariable=self.amount, width=36
        )
        self.amount_entry.pack(fill="x", pady=4)
        quick = ttk.Frame(self.cash_frame)
        quick.pack(fill="x")
        for label, value in (
            ("Exact", str(cart.total)),
            ("100", "100"),
            ("500", "500"),
            ("1000", "1000"),
        ):
            ttk.Button(
                quick,
                text=label,
                command=lambda amount=value: self.amount.set(amount),
                bootstyle="secondary-outline",
            ).pack(side="left", padx=2)
        ttk.Label(self.cash_frame, textvariable=self.change).pack(anchor="w", pady=8)
        self.gcash_frame = ttk.Frame(self.body)
        ttk.Label(self.gcash_frame, text="GCash reference number").pack(anchor="w")
        self.reference_entry = ttk.Entry(
            self.gcash_frame, textvariable=self.reference, width=36
        )
        self.reference_entry.pack(fill="x", pady=4)
        self.feedback = ttk.Label(
            self.body, textvariable=self.error, bootstyle="danger", wraplength=380
        )
        self.feedback.pack(fill="x", pady=8)
        actions = ttk.Frame(self.body)
        actions.pack(fill="x")
        self.confirm_button = ttk.Button(
            actions, text="Confirm payment", command=self.confirm
        )
        self.confirm_button.pack(side="left")
        ttk.Button(
            actions, text="Cancel", command=self.destroy, bootstyle="secondary"
        ).pack(side="right")
        self.first_input = self.amount_entry
        self.bind("<Return>", lambda _event: self.confirm())
        self.method.trace_add("write", self.change_method)
        self.amount.trace_add("write", self.update_payment)
        self.reference.trace_add("write", self.update_payment)
        self.update_payment()

    def payment(self):
        return Payment(self.method.get(), self.amount.get(), self.reference.get())

    def change_method(self, *_args):
        self.cash_frame.pack_forget()
        self.gcash_frame.pack_forget()
        frame = self.cash_frame if self.method.get() == "cash" else self.gcash_frame
        frame.pack(fill="x", pady=12, before=self.feedback)
        self.first_input = (
            self.amount_entry if self.method.get() == "cash" else self.reference_entry
        )
        self.first_input.focus_set()
        self.update_payment()

    def update_payment(self, *_args):
        def validate():
            tender = sale_service.validate_payment(self.cart.total, self.payment())
            self.change.set(
                f"Change: {format_peso(tender.change_amount)}"
                if tender.method == "cash"
                else ""
            )

        valid = self.perform(validate)
        self.confirm_button.configure(
            state="normal" if valid and not self.submitting else "disabled"
        )
        if not valid:
            self.change.set("")

    def confirm(self):
        if (
            self.submitting
            or self.result is not None
            or self.confirm_button.instate(["disabled"])
        ):
            return
        self.submitting = True
        self.confirm_button.configure(state="disabled")

        def complete():
            self.result = sale_service.complete_sale(
                self.cart, self.payment(), customer_id=self.customer_id
            )

        if self.perform(complete):
            self.destroy()
        else:
            self.submitting = False
            self.confirm_button.configure(state="normal")
