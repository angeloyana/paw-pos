"""Owner account creation, cashier status, and password reset forms."""

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from pawpos.core.errors import ValidationError
from pawpos.services import user_service
from pawpos.ui.owner.catalog_screen import CatalogScreen


class UsersScreen(CatalogScreen):
    def __init__(self, parent):
        super().__init__(parent, "Users")
        self.user_id = None
        self.records = {}
        self.username = tk.StringVar(self)
        self.full_name = tk.StringVar(self)
        self.password = tk.StringVar(self)
        ttk.Button(self.toolbar, text="Add cashier", command=self.new).pack(side="left")
        ttk.Button(self.toolbar, text="Refresh", command=self.refresh).pack(
            side="right"
        )
        self.tree = self.make_table(
            [
                ("username", "Username", 160),
                ("name", "Full name", 240),
                ("role", "Role", 90),
                ("active", "Status", 100),
            ]
        )
        self.tree.bind("<<TreeviewSelect>>", self.edit_selected)
        self.form_title = ttk.Label(
            self.form, text="New cashier", font=("Segoe UI", 14, "bold")
        )
        self.form_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.username_entry = self.entry(1, "Username", self.username)
        self.full_name_entry = self.entry(2, "Full name", self.full_name)
        self.password_entry = self.entry(3, "New password", self.password)
        self.password_entry.configure(show="•")
        self.create_button = ttk.Button(
            self.form, text="Create cashier", command=self.create
        )
        self.create_button.grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(12, 6)
        )
        self.toggle_button = ttk.Button(
            self.form,
            text="Disable cashier",
            command=self.toggle_active,
            state="disabled",
            bootstyle="danger-outline",
        )
        self.toggle_button.grid(row=5, column=0, columnspan=2, sticky="ew", pady=6)
        self.reset_button = ttk.Button(
            self.form,
            text="Reset password",
            command=self.reset_password,
            state="disabled",
        )
        self.reset_button.grid(row=6, column=0, columnspan=2, sticky="ew", pady=6)
        self.refresh()

    def refresh(self):
        self.perform(self._load)

    def _load(self):
        rows = user_service.list_users()
        self.new()
        self.tree.delete(*self.tree.get_children())
        self.records = {row.id: row for row in rows}
        for row in rows:
            self.tree.insert(
                "",
                "end",
                iid=str(row.id),
                values=(
                    row.username,
                    row.full_name,
                    row.role.title(),
                    "Enabled" if row.is_active else "Disabled",
                ),
            )

    def new(self):
        self.user_id = None
        self.username.set("")
        self.full_name.set("")
        self.password.set("")
        self.username_entry.configure(state="normal")
        self.full_name_entry.configure(state="normal")
        self.create_button.configure(state="normal")
        self.toggle_button.configure(state="disabled")
        self.reset_button.configure(state="disabled")
        self.form_title.configure(text="New cashier")
        self.tree.selection_remove(*self.tree.selection())
        self.username_entry.focus_set()

    def edit_selected(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        user = self.records[int(selection[0])]
        self.user_id = user.id
        self.username.set(user.username)
        self.full_name.set(user.full_name)
        self.password.set("")
        self.username_entry.configure(state="disabled")
        self.full_name_entry.configure(state="disabled")
        self.create_button.configure(state="disabled")
        self.toggle_button.configure(
            text="Disable cashier" if user.is_active else "Enable cashier",
            state="normal" if user.role == "cashier" else "disabled",
            bootstyle="danger-outline" if user.is_active else "success",
        )
        self.reset_button.configure(state="normal")
        self.form_title.configure(text="Manage account")

    def _selected(self):
        if self.user_id is None:
            raise ValidationError("Select an account first.")
        return self.records[self.user_id]

    def _after_saved(self, message):
        self.new()
        if not self.perform(self._load, message):
            self.status.set(
                f"{message} Refresh to update the account list. {self.status.get()}"
            )

    def create(self):
        def write():
            if self.user_id is not None:
                raise ValidationError("Choose Add cashier to create a new account.")
            user_service.create_cashier(
                self.username.get(), self.full_name.get(), self.password.get()
            )

        if self.perform(write):
            self._after_saved("Cashier created.")

    def toggle_active(self):
        changed = False

        def write():
            nonlocal changed
            user = self._selected()
            if user.is_active and not messagebox.askyesno(
                "Disable cashier",
                f"Disable {user.username}? They will no longer be able to log in.",
                parent=self,
            ):
                return
            user_service.set_active(user.id, not user.is_active)
            changed = True

        if self.perform(write) and changed:
            self._after_saved("Account status updated.")

    def reset_password(self):
        def write():
            user = self._selected()
            user_service.reset_password(user.id, self.password.get())

        if self.perform(write):
            self._after_saved("Password reset.")
