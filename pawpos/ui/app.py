"""One themed root window with replaceable login and workspace frames."""

import tkinter as tk

import ttkbootstrap as ttk

from pawpos.config import SHOP_NAME, THEME
from pawpos.core.session import CurrentUser
from pawpos.services import auth_service
from pawpos.ui.login_screen import LoginScreen
from pawpos.ui.placeholder_screen import PlaceholderScreen


class PawPOSApp(ttk.Window):
    def __init__(self):
        super().__init__(
            title=SHOP_NAME, themename=THEME, size=(1280, 720), minsize=(1280, 720)
        )
        self.screen: ttk.Frame | None = None
        try:
            self.state("zoomed")
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)
            except tk.TclError:
                pass  # A window manager is optional in headless GUI checks.
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_login()

    def _replace_screen(self, screen: ttk.Frame) -> None:
        if self.screen is not None:
            self.screen.destroy()
        self.screen = screen
        screen.pack(fill="both", expand=True)

    def show_login(self) -> None:
        auth_service.logout()
        self.title(f"{SHOP_NAME} — Login")
        screen = LoginScreen(self, self.show_workspace)
        self._replace_screen(screen)
        screen.username_entry.focus_set()

    def show_workspace(self, user: CurrentUser) -> None:
        self.title(f"{SHOP_NAME} — {user.full_name}")
        self._replace_screen(PlaceholderScreen(self, user, self.show_login))

    def close(self) -> None:
        auth_service.logout()
        self.destroy()


def run_app() -> None:
    """Start the desktop event loop after database initialization succeeds."""
    app = PawPOSApp()
    try:
        app.mainloop()
    finally:
        auth_service.logout()
