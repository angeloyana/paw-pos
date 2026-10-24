"""Product browsing, in-memory cart editing, and optional customer selection."""

import logging
import tkinter as tk
from collections.abc import Callable

import ttkbootstrap as ttk

from pawpos.config import SHOP_NAME
from pawpos.core.errors import BusinessRuleError, PawPOSError, ValidationError
from pawpos.core.money import format_peso, format_qty
from pawpos.core.session import CurrentUser
from pawpos.services import (
    category_service,
    product_service,
    receipt_service,
    refund_tracking_service,
    sale_service,
)
from pawpos.services.cart import Cart
from pawpos.ui.dialogs.customer_picker import CustomerPicker
from pawpos.ui.dialogs.held_list import HeldListDialog
from pawpos.ui.dialogs.payment import PaymentDialog
from pawpos.ui.dialogs.receipt_preview import ReceiptPreview
from pawpos.ui.dialogs.refund_request import RefundRequestDialog
from pawpos.ui.dialogs.refund_status import RefundStatusDialog
from pawpos.ui.dialogs.void import VoidDialog
from pawpos.ui.dialogs.weight import WeightDialog
from pawpos.ui.widgets.product_card import ProductCard, ThumbnailCache
from pawpos.ui.widgets.table import TableView
from pawpos.ui.widgets.tooltip import add_tooltip

logger = logging.getLogger(__name__)


class POSScreen(ttk.Frame):
    def __init__(self, parent, user: CurrentUser, on_logout: Callable[[], None]):
        super().__init__(parent, padding=12)
        self.role = user.role
        self.heading = "Cashier POS"
        self.cart = Cart()
        self.customer = None
        self.last_sale = None
        self.products = {}
        self.cards = {}
        self.category_id = None
        self.search = tk.StringVar(self)
        self.status = tk.StringVar(self)
        self.total_text = tk.StringVar(self, value=format_peso(0))
        self.customer_text = tk.StringVar(self, value="Walk-in")
        self.cache = ThumbnailCache(self)
        self.columnconfigure(0, weight=3, minsize=440)
        self.columnconfigure(1, weight=2, minsize=400)
        self.rowconfigure(2, weight=1)
        header = ttk.Frame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.logo = self.cache.get("assets/logo.png", (32, 32))
        ttk.Label(
            header,
            image=self.logo,
            text=f" {SHOP_NAME}  |  {user.full_name}",
            compound="left",
        ).pack(side="left")
        self.logout_button = ttk.Button(header, text="Logout", command=on_logout)
        self.logout_button.pack(side="right")
        self.settings_button = ttk.Button(
            header, text="Settings", command=self.open_settings
        )
        self.settings_button.pack(side="right", padx=6)
        self.last_receipt_button = ttk.Button(
            header,
            text="Last receipt",
            command=self.open_last_receipt,
            state="disabled",
        )
        self.last_receipt_button.pack(side="right", padx=6)
        self.refund_button = ttk.Button(
            header, text="Request Refund", command=self.request_refund
        )
        self.refund_button.pack(side="right", padx=6)
        self.refund_status_button = ttk.Button(
            header, text="Refunds", command=self.open_refunds
        )
        self.refund_status_button.pack(side="right", padx=6)
        self.held_button = ttk.Button(header, text="Held (F8)", command=self.open_held)
        self.held_button.pack(side="right")
        add_tooltip(
            self.held_button, "F8: List saved transactions to resume or cancel."
        )
        ttk.Label(
            self, textvariable=self.status, bootstyle="danger", wraplength=850
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=8)
        browse = ttk.Frame(self)
        browse.grid(row=2, column=0, sticky="nsew", padx=(0, 12))
        browse.columnconfigure(0, weight=1)
        browse.rowconfigure(2, weight=1)
        tools = ttk.Frame(browse)
        tools.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(tools, text="Search (F2)").pack(side="left")
        self.search_entry = ttk.Entry(tools, textvariable=self.search)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=8)
        add_tooltip(
            self.search_entry, "F2: Focus product search while the POS is active."
        )
        ttk.Button(tools, text="Refresh", command=self.refresh_catalog).pack(
            side="right"
        )
        self.category_bar = ttk.Frame(browse)
        self.category_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=8)
        self.canvas = tk.Canvas(
            browse,
            highlightthickness=0,
            width=440,
            height=1,
            background=ttk.Style().colors.bg,
        )
        self.canvas.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(browse, command=self.canvas.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.grid_frame = ttk.Frame(self.canvas)
        self.grid_window = self.canvas.create_window(
            0, 0, window=self.grid_frame, anchor="nw"
        )
        self.grid_frame.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind("<Configure>", self.layout_cards)
        self._build_cart()
        self.search.trace_add("write", lambda *_args: self.refresh_products())
        self._shortcut_bindings = {}
        for key, action in {
            "<F2>": self.search_entry.focus_set,
            "<F4>": self.hold_current,
            "<F5>": self.pay,
            "<F6>": self.void_current,
            "<F8>": self.open_held,
        }.items():
            self._shortcut_bindings[key] = self.winfo_toplevel().bind(
                key,
                lambda event, callback=action: self.shortcut(event, callback),
                add="+",
            )
        self.refresh_catalog()
        self.render_cart()
        self.refund_notice = tk.StringVar(self)
        notice_bar = ttk.Frame(self)
        notice_bar.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(notice_bar, textvariable=self.refund_notice, wraplength=700).pack(
            side="left"
        )
        self.notice_button = ttk.Button(
            notice_bar,
            text="View decisions",
            command=lambda: self.open_refunds(unread_only=True),
        )
        self.notice_button.pack(side="right", padx=6)
        self.notice_retry = ttk.Button(
            notice_bar, text="Refresh notices", command=self.refresh_refund_notices
        )
        self.notice_retry.pack(side="right")
        self._notice_after = None
        self._poll_refund_notices()

    def open_settings(self):
        from pawpos.ui.settings_screen import SettingsDialog

        SettingsDialog(self).show()

    def open_refunds(self, *, unread_only=False):
        self.perform(
            lambda: RefundStatusDialog(
                self, owner=self.role == "owner", unread_only=unread_only
            ).show()
        )
        self.refresh_refund_notices()

    def refresh_refund_notices(self):
        try:
            notices = refund_tracking_service.unread_notices()
        except Exception:
            logger.exception("Cannot refresh refund decision notices")
            self.refund_notice.set(
                "Cannot refresh refund decisions. Use Refresh notices to retry."
            )
            return
        self.refund_status_button.configure(
            text=f"Refunds ({len(notices)} unread)" if notices else "Refunds"
        )
        self.notice_button.configure(state="normal" if notices else "disabled")
        if notices:
            latest = notices[0]
            self.refund_notice.set(
                f"Refund #{latest.request_id} was {latest.status}. {len(notices)} unread decision(s)."
            )
        else:
            self.refund_notice.set("No unread refund decisions.")

    def _poll_refund_notices(self):
        self._notice_after = None
        self.refresh_refund_notices()
        self._notice_after = self.after(10000, self._poll_refund_notices)

    def perform(self, action) -> bool:
        try:
            action()
        except PawPOSError as error:
            self.status.set(str(error))
            return False
        except Exception:
            logger.exception("POS operation failed")
            self.status.set("Cannot complete this action. Please try again.")
            return False
        self.status.set("")
        return True

    def _build_cart(self):
        panel = ttk.Frame(self)
        panel.grid(row=2, column=1, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        ttk.Label(panel, text="CART", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        table_frame = ttk.Frame(panel)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table = TableView(
            table_frame,
            columns=("name", "qty", "price", "total"),
            show="headings",
            selectmode="browse",
        )
        for key, label, width in (
            ("name", "Item", 150),
            ("qty", "Qty / kg", 75),
            ("price", "Unit price", 90),
            ("total", "Total", 100),
        ):
            self.table.heading(key, text=label)
            self.table.column(
                key,
                width=width,
                minwidth=50,
                stretch=key == "name",
                anchor="w" if key == "name" else "e",
            )
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(table_frame, command=self.table.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scroll.set)
        self.table.bind("<Double-1>", lambda _event: self.edit_selected())
        self.table.bind("<Return>", lambda _event: self.edit_selected())
        self.table.bind("<Delete>", lambda _event: self.remove_selected())
        self.empty_label = ttk.Label(
            panel, text="Cart is empty. Click a product to start.", wraplength=360
        )
        self.empty_label.grid(row=2, column=0, sticky="w", pady=6)
        edits = ttk.Frame(panel)
        edits.grid(row=3, column=0, sticky="ew", pady=8)
        self.edit_button = ttk.Button(
            edits, text="Edit quantity", command=self.edit_selected
        )
        self.edit_button.pack(side="left")
        add_tooltip(
            self.edit_button,
            "Enter or double-click a cart row to edit its quantity or weight.",
        )
        self.remove_button = ttk.Button(
            edits,
            text="Remove (Delete)",
            command=self.remove_selected,
            bootstyle="secondary",
        )
        self.remove_button.pack(side="left", padx=6)
        add_tooltip(
            self.remove_button,
            "Delete: Remove the selected cart row. Use Void for a logged cancellation.",
        )
        add_tooltip(
            self.table, "Select a row, then press Enter to edit or Delete to remove it."
        )
        customer = ttk.Frame(panel)
        customer.grid(row=4, column=0, sticky="ew", pady=8)
        ttk.Label(customer, textvariable=self.customer_text, wraplength=250).pack(
            side="left"
        )
        ttk.Button(customer, text="Select customer", command=self.select_customer).pack(
            side="right"
        )
        ttk.Label(
            panel, textvariable=self.total_text, font=("Segoe UI", 24, "bold")
        ).grid(row=5, column=0, sticky="e", pady=16)
        actions = ttk.Frame(panel)
        actions.grid(row=6, column=0, sticky="ew")
        self.hold_button = ttk.Button(
            actions, text="Hold (F4)", command=self.hold_current
        )
        self.hold_button.pack(side="left")
        add_tooltip(
            self.hold_button,
            "F4: Save the cart and customer for later, without changing stock.",
        )
        self.void_button = ttk.Button(
            actions, text="Void (F6)", bootstyle="danger", command=self.void_current
        )
        self.void_button.pack(side="left", padx=6)
        add_tooltip(
            self.void_button,
            "F6: Void a selected line or the whole cart, with a required reason.",
        )
        self.pay_button = ttk.Button(actions, text="PAY (F5)", command=self.pay)
        self.pay_button.pack(side="right", fill="x", expand=True)
        add_tooltip(
            self.pay_button,
            "F5: Complete payment with Cash or GCash. Add an item first.",
        )

    def refresh_catalog(self):
        def load():
            categories = category_service.list_categories()
            if self.category_id not in {row.id for row in categories}:
                self.category_id = None
            for child in self.category_bar.winfo_children():
                child.destroy()
            for index, (key, label) in enumerate(
                [(None, "All")] + [(row.id, row.name) for row in categories]
            ):
                ttk.Button(
                    self.category_bar,
                    text=label,
                    bootstyle="primary"
                    if key == self.category_id
                    else "secondary-outline",
                    command=lambda value=key: self.choose_category(value),
                ).grid(row=index // 3, column=index % 3, sticky="ew", padx=2, pady=2)
            for column in range(3):
                self.category_bar.columnconfigure(column, weight=1)

        if self.perform(load):
            self.refresh_products()

    def choose_category(self, category_id):
        self.category_id = category_id
        self.refresh_catalog()

    def refresh_products(self):
        def load():
            products = product_service.list_products(
                self.search.get(), self.category_id
            )
            self.products = {row.id: row for row in products}
            for child in self.grid_frame.winfo_children():
                child.destroy()
            self.cards = {}
            for product in products:
                card = ProductCard(
                    self.grid_frame,
                    product,
                    self.cache,
                    lambda key=product.id: self.add_product(key),
                )
                self.cards[product.id] = card
            if not products:
                ttk.Label(self.grid_frame, text="No products match your search.").grid(
                    padx=12, pady=24
                )
            self.layout_cards()
            self.canvas.yview_moveto(0)

        self.perform(load)

    def layout_cards(self, event=None):
        width = event.width if event else self.canvas.winfo_width()
        self.canvas.itemconfigure(self.grid_window, width=max(width, 1))
        columns = max(1, width // 160)
        for index, card in enumerate(self.cards.values()):
            card.grid(
                row=index // columns,
                column=index % columns,
                sticky="nsew",
                padx=4,
                pady=4,
            )

    def current_product(self, product_id):
        # Refresh independently of visible search/category filters before changing a line.
        products = {row.id: row for row in product_service.list_products()}
        if product_id not in products:
            raise BusinessRuleError(
                "This product is no longer available. Remove it from the cart."
            )
        return products[product_id]

    def add_product(self, product_id):
        def add():
            product = self.current_product(product_id)
            if product.stock_quantity <= 0:
                raise BusinessRuleError("This product is out of stock.")
            if product.unit_type == "piece":
                self.cart.add_piece(
                    product.id,
                    product.name,
                    product.unit_price,
                    stock_quantity=product.stock_quantity,
                )
            else:
                existing_line = next(
                    (line for line in self.cart.lines if line.product_id == product.id),
                    None,
                )
                amount = WeightDialog(
                    self,
                    product.name,
                    existing_line.unit_price if existing_line else product.unit_price,
                    product.unit_type,
                    product.stock_quantity,
                    existing_quantity=existing_line.quantity if existing_line else 0,
                ).show()
                if amount is None:
                    return
                self.cart.add_weight(
                    product.id,
                    product.name,
                    product.unit_price,
                    amount,
                    stock_quantity=product.stock_quantity,
                )
            self.render_cart(product_id)

        self.perform(add)
        self.search_entry.focus_set()

    def selected_id(self):
        selected = self.table.selection()
        if not selected:
            raise ValidationError("Select a cart line first.")
        return int(selected[0])

    def edit_selected(self):
        def edit():
            product_id = self.selected_id()
            line = next(
                line for line in self.cart.lines if line.product_id == product_id
            )
            product = self.current_product(product_id)
            if product.unit_type != line.unit_type:
                raise BusinessRuleError(
                    "Product units changed. Remove and add this item again."
                )
            amount = WeightDialog(
                self,
                line.product_name,
                line.unit_price,
                line.unit_type,
                product.stock_quantity,
                initial=line.quantity,
            ).show()
            if amount is not None:
                self.cart.set_quantity(
                    product_id, amount, stock_quantity=product.stock_quantity
                )
                self.render_cart(product_id)

        self.perform(edit)
        self.search_entry.focus_set()

    def remove_selected(self):
        def remove():
            self.cart.remove_line(self.selected_id())
            self.render_cart()

        self.perform(remove)

    def render_cart(self, selected=None):
        self.table.delete(*self.table.get_children())
        for line in self.cart.lines:
            self.table.insert(
                "",
                "end",
                iid=str(line.product_id),
                values=(
                    line.product_name,
                    format_qty(line.quantity, line.unit_type),
                    format_peso(line.unit_price),
                    format_peso(line.line_total),
                ),
            )
        if selected is not None:
            self.table.selection_set(str(selected))
        self.total_text.set(format_peso(self.cart.total))
        self.empty_label.configure(
            text="" if self.cart.lines else "Cart is empty. Click a product to start."
        )
        self.pay_button.configure(state="normal" if self.cart.lines else "disabled")

    def select_customer(self):
        def select():
            result = CustomerPicker(self).show()
            if result is not None:
                self.customer = result or None
                self.customer_text.set(
                    self.customer.name if self.customer else "Walk-in"
                )

        self.perform(select)

    def request_refund(self):
        result = None

        def request():
            nonlocal result
            result = RefundRequestDialog(self).show()

        if self.perform(request) and result is not None:
            self.status.set(
                f"Refund request #{result.id} submitted for owner approval."
            )
            self.event_generate("<<RefundsChanged>>", when="tail")
        self.search_entry.focus_set()

    def hold_current(self):
        if not self.cart.lines:
            self.status.set("The cart is empty. Add a product before holding.")
            return
        held = None

        def save():
            nonlocal held
            held = sale_service.hold_cart(
                self.cart, customer_id=self.customer.id if self.customer else None
            )

        if self.perform(save):
            self.cart.clear()
            self.customer = None
            self.customer_text.set("Walk-in")
            self.render_cart()
            self.status.set(f"Transaction #{held.id} held.")
            self.search_entry.focus_set()

    def open_held(self):
        resumed = None

        def choose():
            nonlocal resumed
            resumed = HeldListDialog(self, can_resume=not bool(self.cart.lines)).show()

        if self.perform(choose) and resumed is not None:
            self.cart = resumed.cart
            self.customer = resumed.customer
            self.customer_text.set(self.customer.name if self.customer else "Walk-in")
            self.render_cart()
            self.refresh_products()
            self.status.set(
                "Held transaction resumed. Stock will be checked at payment."
            )
            self.search_entry.focus_set()

    def void_current(self):
        if not self.cart.lines:
            self.status.set("The cart is empty. Nothing to void.")
            return
        selected = self.table.selection()
        product_id = int(selected[0]) if selected else None

        def apply(scope, reason):
            if scope == "line":
                sale_service.void_line(self.cart, product_id, reason)
            else:
                sale_service.void_all(self.cart, reason)

        def choose():
            result = VoidDialog(
                self,
                apply,
                allow_line=product_id is not None,
                description=f"Active cart: {len(self.cart.lines)} lines, {format_peso(self.cart.total)}.",
            ).show()
            if result:
                if result == "transaction":
                    self.customer = None
                    self.customer_text.set("Walk-in")
                self.render_cart()

        self.perform(choose)
        self.search_entry.focus_set()

    def pay(self):
        if not self.cart.lines:
            self.status.set("The cart is empty. Add a product before payment.")
            return
        completed = None

        def take_payment():
            nonlocal completed
            completed = PaymentDialog(
                self, self.cart, self.customer.id if self.customer else None
            ).show()

        if not self.perform(take_payment) or completed is None:
            return
        # Payment is already committed; clear before doing any fallible receipt work.
        self.last_sale = completed
        self.cart.clear()
        self.customer = None
        self.customer_text.set("Walk-in")
        self.render_cart()
        self.last_receipt_button.configure(state="normal")
        self.refresh_products()
        self.open_last_receipt()
        self.search_entry.focus_set()

    def open_last_receipt(self):
        if self.last_sale is None:
            return

        def preview():
            receipt = receipt_service.build_receipt(self.last_sale.id)
            ReceiptPreview(self, receipt).show()

        if self.perform(preview):
            self.status.set(f"Sale {self.last_sale.receipt_number} completed.")
        else:
            self.status.set(
                f"Sale {self.last_sale.receipt_number} is complete. {self.status.get()} Use Last receipt to retry."
            )

    def shortcut(self, event, action):
        focus = self.focus_get()
        if self.winfo_ismapped() and (
            focus is None or focus.winfo_toplevel() == self.winfo_toplevel()
        ):
            action()
            return "break"

    def destroy(self):
        if self._notice_after is not None:
            self.after_cancel(self._notice_after)
            self._notice_after = None
        for key, binding in self._shortcut_bindings.items():
            self.winfo_toplevel().unbind(key, binding)
        super().destroy()
