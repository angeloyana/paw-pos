"""Reasoned confirmation of a line void, whole-cart void, or held cancellation."""

import tkinter as tk
from collections.abc import Callable

import ttkbootstrap as ttk

from pawpos.core.errors import ValidationError
from pawpos.services.catalog_validation import text
from pawpos.ui.dialogs.base import ModalDialog

REASONS = (
    "Wrong item",
    "Customer changed mind",
    "Wrong weight",
    "Price issue",
    "Other",
)


class VoidDialog(ModalDialog):
    def __init__(
        self,
        parent,
        on_void: Callable[[str, str], None],
        *,
        allow_line: bool = True,
        description: str = "",
    ):
        super().__init__(parent, "Confirm void")
        self.on_void = on_void
        self.allow_line = allow_line
        self.submitting = False
        self.scope = tk.StringVar(self, value="line" if allow_line else "transaction")
        self.reason_choice = tk.StringVar(self)
        self.other = tk.StringVar(self)
        self.confirmation = tk.StringVar(self)
        ttk.Label(self.body, text=description, wraplength=420).pack(
            anchor="w", pady=(0, 8)
        )
        scopes = ttk.Frame(self.body)
        scopes.pack(fill="x")
        if allow_line:
            ttk.Radiobutton(
                scopes, text="Selected line", variable=self.scope, value="line"
            ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            scopes, text="Whole transaction", variable=self.scope, value="transaction"
        ).pack(side="left")
        ttk.Label(self.body, textvariable=self.confirmation, wraplength=420).pack(
            anchor="w", pady=12
        )
        ttk.Label(self.body, text="Reason (required)").pack(anchor="w")
        self.first_input = ttk.Combobox(
            self.body,
            textvariable=self.reason_choice,
            values=REASONS,
            state="readonly",
            width=36,
        )
        self.first_input.pack(fill="x", pady=4)
        ttk.Label(self.body, text="Explain if Other").pack(anchor="w", pady=(8, 0))
        self.other_entry = ttk.Entry(self.body, textvariable=self.other)
        self.other_entry.pack(fill="x", pady=4)
        ttk.Label(
            self.body, textvariable=self.error, bootstyle="danger", wraplength=420
        ).pack(pady=8)
        actions = ttk.Frame(self.body)
        actions.pack(fill="x")
        self.confirm_button = ttk.Button(
            actions, text="Confirm void", command=self.confirm, bootstyle="danger"
        )
        self.confirm_button.pack(side="left")
        ttk.Button(
            actions, text="Cancel", command=self.destroy, bootstyle="secondary"
        ).pack(side="right")
        self.bind("<Return>", self.confirm_key)
        self.first_input.bind("<Return>", self.confirm_key)
        for variable in (self.scope, self.reason_choice, self.other):
            variable.trace_add("write", self.update_validation)
        self.update_validation()

    def validated_reason(self):
        if self.scope.get() not in ("line", "transaction") or (
            self.scope.get() == "line" and not self.allow_line
        ):
            raise ValidationError("Choose a valid void scope.")
        choice = self.reason_choice.get()
        if choice not in REASONS:
            raise ValidationError("Choose a reason.")
        return text(self.other.get(), "Reason", 255) if choice == "Other" else choice

    def update_validation(self, *_args):
        self.other_entry.configure(
            state="normal" if self.reason_choice.get() == "Other" else "disabled"
        )
        self.confirmation.set(
            "Void the selected cart line?"
            if self.scope.get() == "line"
            else "Void the whole transaction? Every line will be logged with this reason."
        )
        valid = self.perform(self.validated_reason)
        self.confirm_button.configure(
            state="normal" if valid and not self.submitting else "disabled"
        )

    def confirm(self):
        if (
            self.submitting
            or self.result is not None
            or self.confirm_button.instate(["disabled"])
        ):
            return
        self.submitting = True
        self.confirm_button.configure(state="disabled")

        def apply():
            reason = self.validated_reason()
            self.on_void(self.scope.get(), reason)
            self.result = self.scope.get()

        if self.perform(apply):
            self.destroy()
        else:
            self.submitting = False
            self.confirm_button.configure(state="normal")

    def confirm_key(self, _event):
        self.confirm()
        return "break"
