"""One themed root window with replaceable login and workspace frames."""

import logging
import tkinter as tk

import ttkbootstrap as ttk

from pawpos.config import SHOP_NAME, THEME
from pawpos.core.session import CurrentUser
from pawpos.services import auth_service, settings_service
from pawpos.ui.login_screen import LoginScreen
from pawpos.ui.owner.shell import OwnerShell
from pawpos.ui.pos_screen import POSScreen

logger = logging.getLogger(__name__)


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
        self.apply_theme(THEME)
        self.title(f"{SHOP_NAME} — Login")
        screen = LoginScreen(self, self.show_workspace)
        self._replace_screen(screen)
        screen.username_entry.focus_set()

    def show_workspace(self, user: CurrentUser) -> None:
        theme_error = False
        try:
            theme = settings_service.get_settings().theme
        except Exception:
            logger.exception("Cannot load account theme")
            theme = THEME
            theme_error = True
        self.apply_theme(theme)
        self.title(f"{SHOP_NAME} — {user.full_name}")
        screen = (
            OwnerShell(self, user, self.show_login)
            if user.role == "owner"
            else POSScreen(self, user, self.show_login)
        )
        self._replace_screen(screen)
        if theme_error:
            target = screen.current_screen if isinstance(screen, OwnerShell) else screen
            target.status.set("Cannot load your theme. Open Settings to retry.")

    def apply_theme(self, theme: str) -> None:
        """Restyle the existing workspace without losing POS state."""
        if theme not in settings_service.theme_names():
            theme = THEME
        if self.style.theme_use() == theme:
            return
        self.style.theme_use(theme)

        def restyle(widget):
            if isinstance(widget, tk.Canvas):
                widget.configure(background=self.style.colors.bg)
            refresh = getattr(widget, "refresh_theme", None)
            if refresh is not None:
                refresh()
            for child in widget.winfo_children():
                restyle(child)

        restyle(self)

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
