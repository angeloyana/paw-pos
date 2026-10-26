"""Shared account settings form for the owner page and POS modal."""

import logging
import tkinter as tk

import ttkbootstrap as ttk

from pawpos.core.errors import PawPOSError
from pawpos.services import auth_service, settings_service
from pawpos.ui.dialogs.base import ModalDialog

logger = logging.getLogger(__name__)


class SettingsScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=20)
        self.columnconfigure(0, weight=1)
        self.status = tk.StringVar(self)
        self.theme = tk.StringVar(self, value=ttk.Style().theme_use())
        self.current_password = tk.StringVar(self)
        self.new_password = tk.StringVar(self)
        self.confirmation = tk.StringVar(self)
        ttk.Label(self, text="Settings", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.status_label = ttk.Label(self, textvariable=self.status, wraplength=450)
        self.status_label.grid(row=1, column=0, sticky="ew", pady=8)
        appearance = ttk.Labelframe(self, text="Appearance", padding=12)
        appearance.grid(row=2, column=0, sticky="ew")
        appearance.columnconfigure(0, weight=1)
        self.theme_selector = ttk.Combobox(
            appearance,
            textvariable=self.theme,
            values=settings_service.theme_names(),
            state="readonly",
        )
        self.theme_selector.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.apply_button = ttk.Button(
            appearance, text="Apply theme", command=self.apply_theme
        )
        self.apply_button.grid(row=0, column=1)
        self.reload_button = ttk.Button(
            appearance, text="Reload saved theme", command=self.load
        )
        self.reload_button.grid(row=1, column=0, sticky="w", pady=(8, 0))
        account = ttk.Labelframe(self, text="Change password", padding=12)
        account.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        account.columnconfigure(0, weight=1)
        self.password_entries = []
        for row, (label, variable) in enumerate(
            (
                ("Current password", self.current_password),
                ("New password", self.new_password),
                ("Confirm new password", self.confirmation),
            )
        ):
            ttk.Label(account, text=label).grid(row=row * 2, column=0, sticky="w")
            entry = ttk.Entry(account, textvariable=variable, show="•")
            entry.grid(row=row * 2 + 1, column=0, sticky="ew", pady=(4, 8))
            self.password_entries.append(entry)
        self.change_button = ttk.Button(
            account, text="Change password", command=self.change_password
        )
        self.change_button.grid(row=6, column=0, sticky="w")
        self.load()

    def perform(self, action, success):
        try:
            action()
        except PawPOSError as error:
            self.status.set(str(error))
            self.status_label.configure(bootstyle="danger")
            return False
        except Exception:
            logger.exception("Settings operation failed")
            self.status.set("Cannot complete this action. Please try again.")
            self.status_label.configure(bootstyle="danger")
            return False
        self.status.set(success)
        self.status_label.configure(bootstyle="success")
        return True

    def load(self):
        self.perform(
            lambda: self.theme.set(settings_service.get_settings().theme),
            "",
        )

    def apply_theme(self):
        if not self.perform(
            lambda: settings_service.set_theme(self.theme.get()), "Theme saved."
        ):
            return
        try:
            self._root().apply_theme(self.theme.get())
        except Exception:
            logger.exception("Cannot apply saved theme")
            self.status.set("Theme saved. Sign in again to apply it.")
            self.status_label.configure(bootstyle="warning")

    def clear_passwords(self):
        for variable in (self.current_password, self.new_password, self.confirmation):
            variable.set("")

    def change_password(self):
        def save():
            auth_service.change_password(
                self.current_password.get(),
                self.new_password.get(),
                self.confirmation.get(),
            )
            self.clear_passwords()

        self.perform(save, "Password changed.")

    def destroy(self):
        self.clear_passwords()
        super().destroy()


class SettingsDialog(ModalDialog):
    def __init__(self, parent):
        self._previous_focus = parent.focus_get()
        super().__init__(parent, "Settings")
        self.minsize(520, 580)
        self.form = SettingsScreen(self.body)
        self.form.pack(fill="both", expand=True)
        ttk.Button(self.body, text="Close", command=self.destroy).pack(
            anchor="e", pady=(12, 0)
        )
        self.first_input = self.form.theme_selector
        self.bind("<FocusIn>", self.focus_first_input)

    def focus_first_input(self, event):
        if event.widget is self:
            self.first_input.focus_set()

    def show(self):
        previous_focus = self._previous_focus
        try:
            return super().show()
        finally:
            # Some window managers move focus away when a themed modal closes.
            try:
                if previous_focus is not None and previous_focus.winfo_exists():
                    previous_focus.focus_force()
            except tk.TclError:
                pass
