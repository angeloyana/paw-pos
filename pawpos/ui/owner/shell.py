"""Owner navigation; only completed screens are enabled."""

import logging
from collections.abc import Callable

import ttkbootstrap as ttk
from PIL import Image, ImageTk

from pawpos.config import ASSETS_DIR, SHOP_NAME
from pawpos.core.session import CurrentUser
from pawpos.services import refund_service
from pawpos.ui.owner.categories import CategoriesScreen
from pawpos.ui.owner.customers import CustomersScreen
from pawpos.ui.owner.inventory import InventoryScreen
from pawpos.ui.owner.products import ProductsScreen
from pawpos.ui.owner.refunds import RefundsScreen
from pawpos.ui.pos_screen import POSScreen

logger = logging.getLogger(__name__)


class OwnerShell(ttk.Frame):
    def __init__(self, parent, user: CurrentUser, on_logout: Callable[[], None]):
        super().__init__(parent)
        self.role = "owner"
        self.heading = "Owner dashboard"
        self.user = user
        self.on_logout = on_logout
        self.pos_screen = None
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(self, padding=16, bootstyle="light")
        sidebar.grid(row=0, column=0, sticky="ns")
        with Image.open(ASSETS_DIR / "logo.png") as image:
            self.logo = ImageTk.PhotoImage(image.resize((56, 56)), master=self)
        ttk.Label(sidebar, image=self.logo).pack(pady=(0, 8))
        ttk.Label(sidebar, text=SHOP_NAME, font=("Segoe UI", 20, "bold")).pack(
            pady=(0, 8)
        )
        ttk.Label(sidebar, text=user.full_name, wraplength=160).pack(pady=(0, 20))
        self.buttons = {}
        for label in (
            "Dashboard",
            "Products",
            "Categories",
            "Inventory",
            "Customers",
            "Sales History",
            "Refunds",
            "Users",
            "POS",
        ):
            button = ttk.Button(
                sidebar,
                text=label,
                width=18,
                bootstyle="secondary-outline",
                command=lambda page=label: self.show_page(page),
            )
            button.pack(fill="x", pady=3)
            if label not in (
                "Dashboard",
                "Products",
                "Categories",
                "Inventory",
                "Customers",
                "Refunds",
                "POS",
            ):
                button.configure(state="disabled")
            self.buttons[label] = button
        self.logout_button = ttk.Button(sidebar, text="Logout", command=on_logout)
        self.logout_button.pack(side="bottom", fill="x", pady=(20, 0))
        self.content = ttk.Frame(self)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.current_screen = None
        self.show_page("Dashboard")

    def show_page(self, page: str) -> None:
        if page not in (
            "Dashboard",
            "Products",
            "Categories",
            "Inventory",
            "Customers",
            "Refunds",
            "POS",
        ):
            return
        if self.current_screen is not None:
            if self.current_screen is self.pos_screen:
                self.current_screen.pack_forget()
            else:
                self.current_screen.destroy()
        for label, button in self.buttons.items():
            button.configure(
                bootstyle="primary" if label == page else "secondary-outline"
            )
        if page == "POS":
            if self.pos_screen is None:
                self.pos_screen = POSScreen(self.content, self.user, self.on_logout)
                self.pos_screen.bind(
                    "<<RefundsChanged>>", lambda _event: self.refresh_refund_badge()
                )
            else:
                self.pos_screen.refresh_catalog()
            self.current_screen = self.pos_screen
        elif page == "Products":
            self.current_screen = ProductsScreen(self.content)
        elif page == "Inventory":
            self.current_screen = InventoryScreen(self.content)
        elif page == "Refunds":
            self.current_screen = RefundsScreen(self.content, self.refresh_refund_badge)
        elif page == "Customers":
            self.current_screen = CustomersScreen(self.content)
        elif page == "Categories":
            self.current_screen = CategoriesScreen(self.content)
        else:
            self.current_screen = ttk.Frame(self.content, padding=32)
            ttk.Label(
                self.current_screen,
                text="Owner dashboard",
                font=("Segoe UI", 24, "bold"),
            ).pack(anchor="w")
            ttk.Label(
                self.current_screen,
                text="Manage your products, categories, and inventory from the sidebar.",
            ).pack(anchor="w", pady=16)
            ttk.Label(
                self.current_screen,
                text="Reports and other workspaces will be available in later phases.",
            ).pack(anchor="w")
        self.current_screen.pack(fill="both", expand=True)
        self.refresh_refund_badge()

    def refresh_refund_badge(self):
        try:
            count = refund_service.pending_refund_count()
            self.buttons["Refunds"].configure(text=f"Refunds ({count})")
        except Exception:
            logger.exception("Cannot refresh the pending refund badge")
