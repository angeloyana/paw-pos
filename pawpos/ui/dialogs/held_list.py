"""Persistent held transactions with resume and reasoned cancellation."""

import tkinter as tk

import ttkbootstrap as ttk

from pawpos.core.errors import ValidationError
from pawpos.core.money import format_peso
from pawpos.services import sale_service
from pawpos.ui.dialogs.base import ModalDialog
from pawpos.ui.dialogs.void import VoidDialog
from pawpos.ui.widgets.table import TableView


class HeldListDialog(ModalDialog):
    def __init__(self, parent, *, can_resume: bool = True):
        super().__init__(parent, "Held transactions")
        self.can_resume = can_resume
        self.message = tk.StringVar(self)
        ttk.Label(self.body, textvariable=self.message, wraplength=720).pack(
            anchor="w", pady=(0, 8)
        )
        container = ttk.Frame(self.body)
        container.pack(fill="both", expand=True)
        self.table = TableView(
            container,
            columns=("time", "items", "total", "customer", "cashier"),
            show="headings",
            selectmode="browse",
            height=10,
        )
        for key, label, width in (
            ("time", "Held at", 160),
            ("items", "Lines", 55),
            ("total", "Total", 100),
            ("customer", "Customer", 180),
            ("cashier", "Cashier", 150),
        ):
            self.table.heading(key, text=label)
            self.table.column(
                key, width=width, anchor="e" if key in ("items", "total") else "w"
            )
        self.table.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(container, command=self.table.yview)
        scroll.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scroll.set)
        self.first_input = self.table
        self.table.bind("<Return>", lambda _event: self.resume())
        self.table.bind("<Double-1>", lambda _event: self.resume())
        ttk.Label(
            self.body, textvariable=self.error, bootstyle="danger", wraplength=720
        ).pack(pady=8)
        actions = ttk.Frame(self.body)
        actions.pack(fill="x")
        self.resume_button = ttk.Button(actions, text="Resume", command=self.resume)
        self.resume_button.pack(side="left")
        self.cancel_button = ttk.Button(
            actions,
            text="Cancel held (void)",
            command=self.cancel_selected,
            bootstyle="danger",
        )
        self.cancel_button.pack(side="left", padx=8)
        ttk.Button(
            actions, text="Refresh", command=self.refresh, bootstyle="secondary"
        ).pack(side="left")
        ttk.Button(actions, text="Close", command=self.destroy).pack(side="right")
        self.refresh()

    def refresh(self):
        def load():
            rows = sale_service.list_held()
            self.table.delete(*self.table.get_children())
            for row in rows:
                self.table.insert(
                    "",
                    "end",
                    iid=str(row.id),
                    values=(
                        row.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        row.item_count,
                        format_peso(row.total),
                        row.customer_name or "Walk-in",
                        row.cashier_name,
                    ),
                )
            self.resume_button.configure(
                state="normal" if rows and self.can_resume else "disabled"
            )
            self.cancel_button.configure(state="normal" if rows else "disabled")
            self.message.set(
                "Hold or empty the active cart before resuming a held transaction."
                if not self.can_resume
                else "Select a held transaction to resume or cancel."
                if rows
                else "No held transactions."
            )

        self.perform(load)

    def selected_id(self):
        selection = self.table.selection()
        if not selection:
            raise ValidationError("Select a held transaction first.")
        return int(selection[0])

    def resume(self):
        def restore():
            if not self.can_resume:
                raise ValidationError("Hold or empty the active cart before resuming.")
            self.result = sale_service.resume_held(self.selected_id())

        if self.perform(restore):
            self.destroy()

    def cancel_selected(self):
        def cancel():
            sale_id = self.selected_id()

            def apply(_scope, reason):
                sale_service.cancel_held(sale_id, reason)

            result = VoidDialog(
                self,
                apply,
                allow_line=False,
                description=f"Cancel held transaction #{sale_id}.",
            ).show()
            if result:
                self.refresh()

        self.perform(cancel)
