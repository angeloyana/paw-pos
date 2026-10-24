"""Centered login form; database access stays in the authentication service."""

import logging
import tkinter as tk
from collections.abc import Callable

import ttkbootstrap as ttk
from PIL import Image, ImageTk

from pawpos.config import ASSETS_DIR, SHOP_NAME
from pawpos.core.errors import PawPOSError
from pawpos.core.session import CurrentUser
from pawpos.services import auth_service

logger = logging.getLogger(__name__)


class LoginScreen(ttk.Frame):
    def __init__(self, parent: ttk.Window, on_login: Callable[[CurrentUser], None]):
        super().__init__(parent, padding=24, bootstyle="light")
        self.on_login = on_login
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.error = tk.StringVar()

        card = ttk.Frame(self, padding=32)
        card.place(relx=0.5, rely=0.5, anchor="center")
        with Image.open(ASSETS_DIR / "logo.png") as source:
            self.logo = ImageTk.PhotoImage(source.resize((96, 96)), master=self)
        ttk.Label(card, image=self.logo).pack(pady=(0, 12))
        ttk.Label(card, text=SHOP_NAME, font=("Segoe UI", 24, "bold")).pack()
        ttk.Label(card, text="Sign in to your shop").pack(pady=(4, 24))
        ttk.Label(card, text="Username").pack(anchor="w")
        self.username_entry = ttk.Entry(card, textvariable=self.username, width=36)
        self.username_entry.pack(fill="x", pady=(4, 16))
        ttk.Label(card, text="Password").pack(anchor="w")
        self.password_entry = ttk.Entry(
            card, textvariable=self.password, show="•", width=36
        )
        self.password_entry.pack(fill="x", pady=(4, 12))
        ttk.Label(
            card, textvariable=self.error, bootstyle="danger", wraplength=320
        ).pack(fill="x", pady=(0, 12))
        self.login_button = ttk.Button(
            card, text="Login", command=self.submit, bootstyle="primary"
        )
        self.login_button.pack(fill="x")
        self.username_entry.bind("<Return>", self.submit)
        self.password_entry.bind("<Return>", self.submit)

    def submit(self, _event: tk.Event | None = None) -> None:
        self.error.set("")
        self.login_button.configure(state="disabled")
        try:
            user = auth_service.login(self.username.get(), self.password.get())
        except PawPOSError as error:
            self.error.set(str(error))
            self.password_entry.focus_set()
            return
        except Exception:
            logger.exception("Login failed unexpectedly")
            self.error.set(
                "Cannot sign in right now. Please try again or contact the shop owner."
            )
            return
        finally:
            self.password.set("")
            self.login_button.configure(state="normal")
        self.on_login(user)
