"""Owner stock overview, delivery entry, corrections, and movement history."""

import logging
import tkinter as tk
from datetime import date

import ttkbootstrap as ttk

from pawpos.core.errors import PawPOSError, ValidationError
from pawpos.core.money import format_qty
from pawpos.services import inventory_service as inventory
from pawpos.ui.widgets.auto_filter import AutoFilter
from pawpos.ui.widgets.date_picker import DatePicker
from pawpos.ui.widgets.table import TableView

logger = logging.getLogger(__name__)


class InventoryScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=20)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        ttk.Label(self, text="Inventory", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.status = tk.StringVar()
        self.status_label = ttk.Label(self, textvariable=self.status, wraplength=900)
        self.status_label.grid(row=1, column=0, sticky="ew", pady=12)
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=2, column=0, sticky="nsew")
        self.tabs = {}
        for title in (
            "Stock Overview",
            "Receive Stock",
            "Adjust Stock",
            "Movement History",
        ):
            tab = ttk.Frame(self.notebook, padding=12)
            self.notebook.add(tab, text=title)
            self.tabs[title] = tab
        self.products = {}
        self.search = tk.StringVar()
        self.receive_product = tk.StringVar()
        self.adjust_product = tk.StringVar()
        self.receive_quantity = tk.StringVar()
        self.adjust_quantity = tk.StringVar()
        self.supplier = tk.StringVar()
        self.receive_note = tk.StringVar()
        self.adjust_note = tk.StringVar()
        self.delivery_date = tk.StringVar(value=date.today().isoformat())
        self.reason = tk.StringVar(value="Correction")
        self.history_product = tk.StringVar(value="All products")
        self.history_type = tk.StringVar(value="All types")
        self.date_from = tk.StringVar()
        self.date_to = tk.StringVar()
        self._build_overview()
        self._build_entry("Receive Stock", self.receive_product, receiving=True)
        self._build_entry("Adjust Stock", self.adjust_product, receiving=False)
        self._build_history()
        self.refresh()
        self.refresh_history()
        self.auto_filter = AutoFilter(self, self.refresh, text=(self.search,))
        self.history_auto_filter = AutoFilter(
            self,
            self.refresh_history,
            choices=(
                self.history_product,
                self.history_type,
                self.date_from,
                self.date_to,
            ),
        )
        self.notebook.bind("<<NotebookTabChanged>>", self._tab_changed)

    def refresh_theme(self):
        self.overview_tree.tag_configure("low", foreground=ttk.Style().colors.warning)

    def _tab_changed(self, _event=None):
        if self.notebook.select() == str(self.tabs["Movement History"]):
            self.refresh_history()

    def perform(self, action, success=""):
        try:
            action()
        except PawPOSError as error:
            self.status.set(str(error))
            self.status_label.configure(bootstyle="danger")
            return False
        except Exception:
            logger.exception("Inventory operation failed")
            self.status.set("Cannot complete this action. Please try again.")
            self.status_label.configure(bootstyle="danger")
            return False
        self.status.set(success)
        self.status_label.configure(bootstyle="success")
        return True

    def _table(self, parent, columns):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        frame = ttk.Frame(parent)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tree = TableView(frame, columns=[c[0] for c in columns], show="headings")
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(
                key,
                width=width,
                minwidth=70,
                anchor="e" if key in ("stock", "threshold", "change", "after") else "w",
            )
        tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        return tree

    def _build_overview(self):
        tab = self.tabs["Stock Overview"]
        toolbar = ttk.Frame(tab)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(toolbar, text="Search").pack(side="left")
        entry = ttk.Entry(toolbar, textvariable=self.search)
        entry.pack(side="left", padx=8)
        entry.bind("<Return>", lambda _event: self.refresh())
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="left")
        self.overview_tree = self._table(
            tab,
            [
                ("name", "Product", 210),
                ("category", "Category", 150),
                ("stock", "Stock", 110),
                ("threshold", "Threshold", 110),
                ("status", "Status", 110),
            ],
        )
        self.overview_tree.tag_configure("low", foreground=ttk.Style().colors.warning)
        ttk.Label(
            tab,
            text="Low stock: balance at or below threshold. Inactive products are included.",
        ).grid(row=2, column=0, sticky="w", pady=8)

    @staticmethod
    def _field(tab, row, label, variable, *, values=None):
        ttk.Label(tab, text=label).grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=7
        )
        if values is None:
            widget = ttk.Entry(tab, textvariable=variable, width=48)
        else:
            widget = ttk.Combobox(
                tab, textvariable=variable, values=values, state="readonly", width=46
            )
        widget.grid(row=row, column=1, sticky="ew", pady=7)
        return widget

    def _build_entry(self, title, variable, *, receiving):
        tab = self.tabs[title]
        tab.columnconfigure(1, weight=1)
        combo = self._field(tab, 0, "Product", variable, values=[])
        if receiving:
            self.receive_combo = combo
            combo.bind("<<ComboboxSelected>>", self.prefill_supplier)
            self._field(tab, 1, "Quantity to receive", self.receive_quantity)
            self._field(tab, 2, "Supplier", self.supplier)
            ttk.Label(tab, text="Delivery date").grid(
                row=3, column=0, sticky="w", padx=(0, 12), pady=7
            )
            self.delivery_picker = DatePicker(tab, self.delivery_date)
            self.delivery_picker.grid(row=3, column=1, sticky="ew", pady=7)
            self._field(tab, 4, "Note (optional)", self.receive_note)
            self.receive_button = ttk.Button(
                tab, text="Receive stock", command=self.receive
            )
            self.receive_button.grid(row=5, column=1, sticky="w", pady=16)
            hint = "Supplier is prefilled from the product. Delivery details are saved in history."
        else:
            self.adjust_combo = combo
            self._field(tab, 1, "Quantity change (+ or -)", self.adjust_quantity)
            self._field(
                tab, 2, "Reason", self.reason, values=inventory.ADJUSTMENT_REASONS
            )
            self._field(tab, 3, "Note (required)", self.adjust_note)
            self.adjust_button = ttk.Button(
                tab, text="Apply adjustment", command=self.adjust
            )
            self.adjust_button.grid(row=5, column=1, sticky="w", pady=16)
            hint = "Enter a signed change, such as -2 for loss or +3 for a count correction."
        ttk.Label(tab, text=hint, wraplength=700).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=8
        )

    def _build_history(self):
        tab = self.tabs["Movement History"]
        filters = ttk.Frame(tab)
        filters.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.history_combo = self._field(
            filters, 0, "Product", self.history_product, values=["All products"]
        )
        self._field(
            filters,
            1,
            "Type",
            self.history_type,
            values=("All types", *inventory.MOVEMENT_TYPES),
        )
        dates = ttk.Frame(filters)
        dates.grid(row=2, column=0, columnspan=2, sticky="w")
        self.history_date_pickers = []
        for label, variable in (("From", self.date_from), ("To", self.date_to)):
            ttk.Label(dates, text=label).pack(side="left", padx=(0, 8))
            picker = DatePicker(dates, variable, allow_clear=True)
            picker.pack(side="left", padx=(0, 12))
            self.history_date_pickers.append(picker)
        ttk.Label(dates, text="Blank = any date").pack(side="left")
        ttk.Button(dates, text="Refresh", command=self.refresh_history).pack(
            side="left", padx=12
        )
        self.history_tree = self._table(
            tab,
            [
                ("date", "Date", 150),
                ("name", "Product", 200),
                ("type", "Type", 130),
                ("change", "Change", 100),
                ("after", "Stock after", 110),
                ("reference", "Reference", 180),
                ("user", "User", 150),
                ("note", "Note", 300),
            ],
        )
        self.history_empty = tk.StringVar()
        ttk.Label(tab, textvariable=self.history_empty).grid(
            row=2, column=0, sticky="w", pady=8
        )

    def refresh(self):
        if hasattr(self, "auto_filter"):
            self.auto_filter.cancel()
        self.perform(self._load, "Stock overview refreshed.")

    def _load(self):
        products = inventory.stock_overview()
        self.products = {f"{p.name} (#{p.id}, {p.unit_type})": p for p in products}
        for combo in (self.receive_combo, self.adjust_combo):
            combo.configure(values=list(self.products))
        self.history_combo.configure(values=["All products", *self.products])
        self.overview_tree.delete(*self.overview_tree.get_children())
        for p in products:
            if self.search.get().strip().casefold() not in p.name.casefold():
                continue
            low = p.stock_quantity <= p.low_stock_threshold
            self.overview_tree.insert(
                "",
                "end",
                iid=str(p.id),
                values=(
                    p.name,
                    p.category_name,
                    format_qty(p.stock_quantity, p.unit_type),
                    format_qty(p.low_stock_threshold, p.unit_type),
                    ", ".join(
                        s
                        for s in (
                            "Low" if low else "",
                            "Inactive" if not p.is_active else "",
                        )
                        if s
                    )
                    or "OK",
                ),
                tags=("low",) if low else (),
            )

    def prefill_supplier(self, _event=None):
        product = self.products.get(self.receive_product.get())
        if product:
            self.supplier.set(product.supplier)

    def _product_id(self, variable):
        product = self.products.get(variable.get())
        if product is None:
            raise ValidationError("Choose a product.")
        return product.id

    @staticmethod
    def _date(value):
        if not value.strip():
            return None
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            raise ValidationError("Enter dates as YYYY-MM-DD.") from None

    def receive(self):
        def save():
            inventory.receive_stock(
                self._product_id(self.receive_product),
                self.receive_quantity.get(),
                supplier=self.supplier.get(),
                note=self.receive_note.get(),
                received_date=self._date(self.delivery_date.get()),
            )
            # Clear committed input before refresh, so a read failure cannot invite resubmission.
            self.receive_quantity.set("")
            self.receive_note.set("")
            self._after_change()

        self.perform(save, "Stock received.")

    def adjust(self):
        def save():
            inventory.adjust_stock(
                self._product_id(self.adjust_product),
                self.adjust_quantity.get(),
                reason=self.reason.get(),
                note=self.adjust_note.get(),
            )
            self.adjust_quantity.set("")
            self.adjust_note.set("")
            self._after_change()

        self.perform(save, "Stock adjusted.")

    def _after_change(self):
        # A failed refresh must not report a committed write as a failed stock change.
        try:
            self._load()
            self._load_history()
        except Exception:
            logger.exception("Stock saved, but inventory refresh failed")
            self.status.set(
                "Stock saved. Refresh inventory to see the updated balance."
            )
            raise ValidationError(self.status.get()) from None

    def refresh_history(self):
        if hasattr(self, "history_auto_filter"):
            self.history_auto_filter.cancel()
        self.perform(self._load_history)

    def _load_history(self):
        rows = inventory.list_movements(
            product_id=None
            if self.history_product.get() == "All products"
            else self._product_id(self.history_product),
            movement_type=None
            if self.history_type.get() == "All types"
            else self.history_type.get(),
            date_from=self._date(self.date_from.get()),
            date_to=self._date(self.date_to.get()),
        )
        self.history_tree.delete(*self.history_tree.get_children())
        for row in rows:
            change = format_qty(row.quantity_change, row.unit_type)
            self.history_tree.insert(
                "",
                "end",
                iid=str(row.id),
                values=(
                    row.created_at.strftime("%Y-%m-%d %H:%M"),
                    row.product_name,
                    row.movement_type,
                    ("+" if row.quantity_change > 0 else "") + change,
                    format_qty(row.stock_after, row.unit_type),
                    row.reference,
                    row.user_name,
                    row.note,
                ),
            )
        self.history_empty.set(
            "No stock movements match these filters."
            if not rows
            else "History is read-only. Stock after is the balance when posted."
        )
