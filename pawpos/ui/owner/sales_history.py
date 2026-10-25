"""Owner sales filtering, original sale details, and receipt PDF reprinting."""

import tkinter as tk
from datetime import date

import ttkbootstrap as ttk

from pawpos.core.errors import ValidationError
from pawpos.core.money import format_peso, format_qty
from pawpos.services import receipt_service, sales_history_service, user_service
from pawpos.ui.owner.catalog_screen import CatalogScreen
from pawpos.ui.widgets.auto_filter import AutoFilter
from pawpos.ui.widgets.date_picker import DatePicker


class SalesHistoryScreen(CatalogScreen):
    def __init__(self, parent):
        super().__init__(parent, "Sales History")
        self.selected_sale_id = None
        self.records = {}
        self.cashiers = {}
        self.date_from = tk.StringVar(self)
        self.date_to = tk.StringVar(self)
        self.receipt_number = tk.StringVar(self)
        self.cashier = tk.StringVar(self, value="All accounts")
        self.method = tk.StringVar(self, value="All methods")
        self.date_pickers = []
        for column, (label, variable) in enumerate(
            (
                ("From", self.date_from),
                ("To", self.date_to),
                ("Receipt contains", self.receipt_number),
            )
        ):
            field = ttk.Frame(self.toolbar)
            field.grid(row=0, column=column, sticky="ew", padx=(0, 12))
            ttk.Label(field, text=label).pack(anchor="w")
            if column < 2:
                picker = DatePicker(field, variable, allow_clear=True)
                picker.pack(fill="x")
                self.date_pickers.append(picker)
            else:
                entry = ttk.Entry(field, textvariable=variable, width=22)
                entry.pack(fill="x")
                entry.bind("<Return>", lambda _event: self.refresh())
        choices = ttk.Frame(self.toolbar)
        choices.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Label(choices, text="Cashier").pack(side="left")
        self.cashier_combo = ttk.Combobox(
            choices, textvariable=self.cashier, state="readonly", width=28
        )
        self.cashier_combo.pack(side="left", padx=8)
        ttk.Label(choices, text="Payment").pack(side="left")
        ttk.Combobox(
            choices,
            textvariable=self.method,
            state="readonly",
            values=("All methods", "Cash", "GCash"),
            width=12,
        ).pack(side="left", padx=8)
        ttk.Button(choices, text="Refresh", command=self.refresh).pack(
            side="left", padx=8
        )
        self.tree = self.make_table(
            [
                ("receipt", "Receipt", 190),
                ("date", "Date", 155),
                ("cashier", "Cashier", 150),
                ("customer", "Customer", 150),
                ("method", "Payment", 95),
                ("total", "Total", 115),
                ("refunded", "Refunded", 115),
            ]
        )
        for column in self.tree.cget("columns"):
            self.tree.column(column, stretch=True)
        for column in ("total", "refunded"):
            self.tree.column(column, anchor="e")
        self.tree.bind("<<TreeviewSelect>>", self.show_selected)
        ttk.Label(self.form, text="Sale details", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        self.detail = tk.Text(
            self.form,
            width=34,
            height=20,
            wrap="word",
            state="disabled",
            font="TkDefaultFont",
        )
        self.detail.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.reprint_button = ttk.Button(
            self.form, text="Reprint receipt", command=self.reprint, state="disabled"
        )
        self.reprint_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Label(
            self.form,
            text="Reprint opens an 80 mm PDF in your default viewer. Print from that viewer.",
            wraplength=280,
        ).grid(row=3, column=0, columnspan=2, sticky="w")
        self.refresh()
        self.auto_filter = AutoFilter(
            self,
            self.refresh,
            text=(self.receipt_number,),
            choices=(self.date_from, self.date_to, self.cashier, self.method),
        )

    def _set_detail(self, value):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", value)
        self.detail.configure(state="disabled")

    @staticmethod
    def _date(value):
        if not value.strip():
            return None
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            raise ValidationError(
                "Enter dates as YYYY-MM-DD, or leave blank."
            ) from None

    def refresh(self):
        if hasattr(self, "auto_filter"):
            self.auto_filter.cancel()
        self.perform(
            self._load,
            "Sales history refreshed. Dates are inclusive; blank dates include all sales.",
        )

    def _load(self):
        accounts = user_service.list_users()
        self.cashiers = {
            f"{user.full_name} ({user.username})": user.id for user in accounts
        }
        self.cashier_combo.configure(values=["All accounts", *self.cashiers])
        if (
            self.cashier.get() != "All accounts"
            and self.cashier.get() not in self.cashiers
        ):
            raise ValidationError("Choose an account from the cashier filter.")
        rows = sales_history_service.list_sales(
            date_from=self._date(self.date_from.get()),
            date_to=self._date(self.date_to.get()),
            receipt_number=self.receipt_number.get(),
            cashier_id=self.cashiers.get(self.cashier.get()),
            payment_method={"All methods": None, "Cash": "cash", "GCash": "gcash"}[
                self.method.get()
            ],
        )
        self.selected_sale_id = None
        self.reprint_button.configure(state="disabled")
        self._set_detail(
            "Select a completed sale to see its items and payment."
            if rows
            else "No completed sales match these filters."
        )
        self.tree.delete(*self.tree.get_children())
        self.records = {row.id: row for row in rows}
        for row in rows:
            self.tree.insert(
                "",
                "end",
                iid=str(row.id),
                values=(
                    row.receipt_number,
                    row.completed_at.strftime("%Y-%m-%d %H:%M"),
                    row.cashier_name,
                    row.customer_name,
                    "Cash" if row.payment_method == "cash" else "GCash",
                    format_peso(row.total),
                    format_peso(row.refunded_amount),
                ),
            )

    def show_selected(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        self.selected_sale_id = None
        self.reprint_button.configure(state="disabled")

        def load():
            detail = sales_history_service.get_sale(int(selection[0]))
            sale = detail.summary
            lines = [
                sale.receipt_number,
                sale.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
                f"Cashier: {sale.cashier_name}",
                f"Customer: {sale.customer_name}",
                "",
            ]
            for item in detail.items:
                lines.extend(
                    (
                        item.product_name,
                        f"{format_qty(item.quantity, item.unit_type)} × {format_peso(item.unit_price)} = {format_peso(item.line_total)}",
                        "",
                    )
                )
            lines.extend(
                (
                    f"Total: {format_peso(sale.total)}",
                    f"Approved refunds: {format_peso(sale.refunded_amount)}",
                )
            )
            if sale.payment_method == "cash":
                lines.extend(
                    (
                        f"Cash received: {format_peso(detail.amount_received)}",
                        f"Change: {format_peso(detail.change_amount)}",
                    )
                )
            else:
                lines.append(f"GCash reference: {detail.gcash_reference}")
            self._set_detail("\n".join(lines))
            self.selected_sale_id = sale.id
            self.reprint_button.configure(state="normal")

        self.perform(load)

    def reprint(self):
        path = None

        def print_pdf():
            nonlocal path
            if self.selected_sale_id is None:
                raise ValidationError("Select a completed sale first.")
            path = receipt_service.print_receipt(
                receipt_service.build_receipt(self.selected_sale_id)
            )

        if self.perform(print_pdf):
            self.status.set(f"Receipt PDF opened: {path}. Print from your PDF viewer.")
