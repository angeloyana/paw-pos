"""Role destinations while the POS and owner shell are built in later phases."""

from collections.abc import Callable

import ttkbootstrap as ttk

from pawpos.config import SHOP_NAME
from pawpos.core.session import CurrentUser


class PlaceholderScreen(ttk.Frame):
    def __init__(
        self, parent: ttk.Window, user: CurrentUser, on_logout: Callable[[], None]
    ):
        super().__init__(parent, padding=32)
        self.role = user.role
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text=SHOP_NAME, font=("Segoe UI", 20, "bold")).pack(
            side="left"
        )
        self.logout_button = ttk.Button(header, text="Logout", command=on_logout)
        self.logout_button.pack(side="right")
        self.heading = "Owner dashboard" if user.role == "owner" else "Cashier POS"
        ttk.Label(self, text=self.heading, font=("Segoe UI", 24, "bold")).pack(
            pady=(100, 16)
        )
        ttk.Label(
            self, text=f"Welcome, {user.full_name}.", font=("Segoe UI", 14)
        ).pack()
        ttk.Label(
            self, text="You are signed in. This workspace is coming in a later phase."
        ).pack(pady=16)
