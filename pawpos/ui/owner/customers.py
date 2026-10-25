"""Owner customer editing and completed purchase lookup."""

import tkinter as tk

import ttkbootstrap as ttk

from pawpos.core.money import format_peso
from pawpos.services import customer_service, sales_history_service
from pawpos.ui.owner.catalog_screen import CatalogScreen
from pawpos.ui.widgets.auto_filter import AutoFilter
from pawpos.ui.widgets.table import TableView


class CustomersScreen(CatalogScreen):
    def __init__(self, parent):
        super().__init__(parent, "Customers")
        self.customer_id = None
        self.records = {}
        self.search = tk.StringVar(self)
        self.name = tk.StringVar(self)
        self.contact = tk.StringVar(self)
        ttk.Label(self.toolbar, text="Search name/contact").pack(side="left")
        search = ttk.Entry(self.toolbar, textvariable=self.search, width=24)
        search.pack(side="left", padx=8)
        search.bind("<Return>", lambda _event: self.refresh())
        ttk.Button(self.toolbar, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(self.toolbar, text="Add customer", command=self.new).pack(
            side="right"
        )
        self.tree = self.make_table(
            [("name", "Name", 240), ("contact", "Contact", 220)]
        )
        self.tree.bind("<<TreeviewSelect>>", self.edit_selected)
        self.form_title = ttk.Label(
            self.form, text="New customer", font=("Segoe UI", 14, "bold")
        )
        self.form_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.name_entry = self.entry(1, "Name", self.name)
        self.entry(2, "Contact", self.contact)
        self.save_button = ttk.Button(
            self.form, text="Save customer", command=self.save
        )
        self.save_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Label(
            self.form,
            text="Contact is optional. Customer records are kept with their purchase history.",
            wraplength=280,
        ).grid(row=4, column=0, columnspan=2, sticky="w")
        purchases = ttk.Frame(self)
        purchases.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        purchases.columnconfigure(0, weight=1)
        self.purchase_message = tk.StringVar(
            self, value="Select a customer to see completed purchases."
        )
        ttk.Label(purchases, textvariable=self.purchase_message).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        self.purchases_tree = TableView(
            purchases,
            columns=("receipt", "date", "method", "total", "refunded"),
            show="headings",
            height=4,
        )
        for key, label, width in (
            ("receipt", "Receipt", 200),
            ("date", "Date", 160),
            ("method", "Payment", 100),
            ("total", "Total", 120),
            ("refunded", "Refunded", 120),
        ):
            self.purchases_tree.heading(key, text=label)
            self.purchases_tree.column(
                key,
                width=width,
                minwidth=70,
                anchor="e" if key in ("total", "refunded") else "w",
            )
        self.purchases_tree.grid(row=1, column=0, sticky="ew")
        vertical = ttk.Scrollbar(purchases, command=self.purchases_tree.yview)
        vertical.grid(row=1, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(
            purchases, orient="horizontal", command=self.purchases_tree.xview
        )
        horizontal.grid(row=2, column=0, sticky="ew")
        self.purchases_tree.configure(
            yscrollcommand=vertical.set, xscrollcommand=horizontal.set
        )
        self.refresh()
        self.auto_filter = AutoFilter(self, self.refresh, text=(self.search,))

    def refresh(self):
        if hasattr(self, "auto_filter"):
            self.auto_filter.cancel()
        self.perform(self._load, "Select a customer to edit, or add a new one.")

    def _load(self):
        rows = customer_service.list_customers(self.search.get())
        self.new(focus=False)
        self.tree.delete(*self.tree.get_children())
        self.records = {row.id: row for row in rows}
        for row in rows:
            self.tree.insert("", "end", iid=str(row.id), values=(row.name, row.contact))
        if not rows:
            self.purchase_message.set(
                "No customers match your search. Use Add customer to create one."
            )

    def new(self, *, focus=True):
        self.customer_id = None
        self.name.set("")
        self.contact.set("")
        self.form_title.configure(text="New customer")
        self.tree.selection_remove(*self.tree.selection())
        self.purchases_tree.delete(*self.purchases_tree.get_children())
        self.purchase_message.set("Select a customer to see completed purchases.")
        if focus:
            self.name_entry.focus_set()

    def edit_selected(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return

        def load():
            customer = self.records[int(selected[0])]
            self.customer_id = customer.id
            self.name.set(customer.name)
            self.contact.set(customer.contact)
            self.form_title.configure(text="Edit customer")
            rows = sales_history_service.list_sales(customer_id=customer.id)
            self.purchases_tree.delete(*self.purchases_tree.get_children())
            for row in rows:
                self.purchases_tree.insert(
                    "",
                    "end",
                    iid=str(row.id),
                    values=(
                        row.receipt_number,
                        row.completed_at.strftime("%Y-%m-%d %H:%M"),
                        "Cash" if row.payment_method == "cash" else "GCash",
                        format_peso(row.total),
                        format_peso(row.refunded_amount),
                    ),
                )
            self.purchase_message.set(
                f"Completed purchases for {customer.name}"
                if rows
                else f"No completed purchases for {customer.name}."
            )

        self.perform(load)

    def save(self):
        def write():
            if self.customer_id is None:
                customer_service.create_customer(self.name.get(), self.contact.get())
            else:
                customer_service.update_customer(
                    self.customer_id, self.name.get(), self.contact.get()
                )

        if self.perform(write):
            self.new()
            if not self.perform(self._load, "Customer saved."):
                self.status.set(
                    f"Customer saved. Refresh to update the list. {self.status.get()}"
                )
