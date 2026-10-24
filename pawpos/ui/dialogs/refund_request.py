"""Cashier receipt lookup and refund request entry; review stays in the owner workspace."""

import tkinter as tk

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledFrame

from pawpos.core.errors import PawPOSError, ValidationError
from pawpos.core.money import format_peso, format_qty, round_money
from pawpos.services import receipt_service, refund_service
from pawpos.services.catalog_validation import quantity
from pawpos.ui.dialogs.base import ModalDialog
from pawpos.ui.dialogs.receipt_preview import ReceiptPreview


class RefundRequestDialog(ModalDialog):
    def __init__(self, parent):
        super().__init__(parent, "Request refund")
        self.geometry("1000x600")
        self.minsize(800, 500)
        self.sale = None
        self.rows = {}
        self.receipt_number = tk.StringVar(self)
        self.reason = tk.StringVar(self)
        self.summary = tk.StringVar(
            self, value="Enter a completed receipt number and press Load."
        )
        self.total = tk.StringVar(self, value="Requested total: ₱0.00")
        toolbar = ttk.Frame(self.body)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Receipt number").pack(side="left")
        self.first_input = ttk.Entry(
            toolbar, textvariable=self.receipt_number, width=32
        )
        self.first_input.pack(side="left", padx=8)
        self.first_input.bind("<Return>", lambda _event: self.load())
        ttk.Button(toolbar, text="Load", command=self.load).pack(side="left")
        self.reprint_button = ttk.Button(
            toolbar, text="Reprint receipt", command=self.reprint, state="disabled"
        )
        self.reprint_button.pack(side="right")
        ttk.Label(self.body, textvariable=self.summary, wraplength=900).pack(
            anchor="w", pady=12
        )
        self.lines = ScrolledFrame(self.body, height=260, autohide=True)
        self.lines.pack(fill="both", expand=True)
        ttk.Label(
            self.body,
            text="Select items, enter quantities, and flag opened/used items. Opened food is not refundable.",
            wraplength=900,
        ).pack(anchor="w", pady=8)
        reason_row = ttk.Frame(self.body)
        reason_row.pack(fill="x")
        ttk.Label(reason_row, text="Reason (required)").pack(side="left")
        ttk.Entry(reason_row, textvariable=self.reason).pack(
            side="left", fill="x", expand=True, padx=8
        )
        ttk.Label(
            self.body, textvariable=self.total, font=("Segoe UI", 14, "bold")
        ).pack(anchor="e", pady=8)
        ttk.Label(
            self.body, textvariable=self.error, bootstyle="danger", wraplength=900
        ).pack(anchor="w", pady=8)
        actions = ttk.Frame(self.body)
        actions.pack(fill="x")
        self.submit_button = ttk.Button(
            actions, text="Submit request", command=self.submit, state="disabled"
        )
        self.submit_button.pack(side="left")
        ttk.Label(
            actions, text="Owner approval required. Money is returned manually."
        ).pack(side="left", padx=12)
        ttk.Button(
            actions, text="Cancel", command=self.destroy, bootstyle="secondary"
        ).pack(side="right")
        self.receipt_number.trace_add("write", self._invalidate)

    def _invalidate(self, *_args):
        self.sale = None
        self.rows.clear()
        for child in self.lines.winfo_children():
            child.destroy()
        self.submit_button.configure(state="disabled")
        self.reprint_button.configure(state="disabled")
        self.summary.set("Press Load to look up the receipt.")
        self.total.set("Requested total: ₱0.00")

    def load(self):
        self._invalidate()

        def load():
            sale = refund_service.lookup_receipt(self.receipt_number.get())
            self.sale = sale
            self.summary.set(
                f"{sale.receipt_number} — completed {sale.completed_at:%Y-%m-%d %H:%M}. Refund requests must be within 7 days."
            )
            self.lines.columnconfigure(1, weight=1)
            for column, title in enumerate(
                ("Return", "Item / price", "Available", "Quantity", "Opened/used")
            ):
                ttk.Label(self.lines, text=title, font=("Segoe UI", 10, "bold")).grid(
                    row=0, column=column, sticky="w", padx=8, pady=6
                )
            for index, item in enumerate(sale.items, 1):
                selected = tk.BooleanVar(self)
                amount = tk.StringVar(self)
                opened = tk.BooleanVar(self)
                self.rows[item.id] = (item, selected, amount, opened)
                ttk.Checkbutton(
                    self.lines,
                    variable=selected,
                    state="normal" if item.remaining > 0 else "disabled",
                ).grid(row=index, column=0, padx=8)
                ttk.Label(
                    self.lines,
                    text=f"{item.product_name}\n{format_peso(item.unit_price)}{'/kg' if item.unit_type == 'kg' else ''}",
                    wraplength=330,
                ).grid(row=index, column=1, sticky="w", padx=8, pady=8)
                ttk.Label(
                    self.lines, text=format_qty(item.remaining, item.unit_type)
                ).grid(row=index, column=2, sticky="e", padx=8)
                ttk.Entry(self.lines, textvariable=amount, width=12).grid(
                    row=index, column=3, padx=8
                )
                ttk.Checkbutton(self.lines, variable=opened).grid(
                    row=index, column=4, padx=8
                )
                for variable in (selected, amount):
                    variable.trace_add("write", lambda *_args: self.update_total())
            self.submit_button.configure(state="normal")
            self.reprint_button.configure(state="normal")

        self.perform(load)

    def update_total(self):
        try:
            total = 0
            for item, selected, amount, _opened in self.rows.values():
                if selected.get():
                    qty = quantity(amount.get(), "Refund quantity", item.unit_type)
                    total += round_money(qty * item.unit_price)
            self.total.set(f"Requested total: {format_peso(total)}")
        except PawPOSError:
            self.total.set("Enter valid quantities to see the requested total.")

    def submit(self):
        def save():
            if self.sale is None:
                raise ValidationError("Load a completed receipt first.")
            items = [
                refund_service.RefundLineInput(item.id, amount.get(), opened.get())
                for item, selected, amount, opened in self.rows.values()
                if selected.get()
            ]
            self.result = refund_service.create_request(
                self.sale.receipt_number, items, self.reason.get()
            )

        if self.perform(save):
            self.destroy()

    def reprint(self):
        def preview():
            if self.sale is None:
                raise ValidationError("Load a completed receipt first.")
            ReceiptPreview(self, receipt_service.build_receipt(self.sale.id)).show()

        self.perform(preview)
