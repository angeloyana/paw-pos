"""Shared read-only void history for the POS modal and owner workspace."""

import logging
import tkinter as tk
from datetime import date

import ttkbootstrap as ttk

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError, ValidationError
from pawpos.core.money import format_peso
from pawpos.services import void_history_service
from pawpos.ui.dialogs.base import ModalDialog
from pawpos.ui.widgets.auto_filter import AutoFilter
from pawpos.ui.widgets.date_picker import DatePicker
from pawpos.ui.widgets.table import TableView

logger = logging.getLogger(__name__)


class VoidHistoryScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=16)
        self._identity = login_session.current_user
        self._access = None
        self._session_after = None
        self.records = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        ttk.Label(self, text="Void History", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.status = tk.StringVar(self)
        self.status_label = ttk.Label(self, textvariable=self.status, wraplength=800)
        self.status_label.grid(row=1, column=0, sticky="ew", pady=8)
        toolbar = ttk.Frame(self)
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self.date_from = tk.StringVar(self)
        self.date_to = tk.StringVar(self)
        self.date_pickers = []
        for column, (label, variable) in enumerate(
            (("From", self.date_from), ("To", self.date_to))
        ):
            field = ttk.Frame(toolbar)
            field.grid(row=0, column=column, padx=(0, 12), sticky="w")
            ttk.Label(field, text=label).pack(anchor="w")
            picker = DatePicker(field, variable, allow_clear=True)
            picker.pack(fill="x")
            self.date_pickers.append(picker)
        self.refresh_button = ttk.Button(toolbar, text="Refresh", command=self.refresh)
        self.refresh_button.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        table = ttk.Frame(self)
        table.grid(row=3, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = (
            ("date", "Date/time", 175),
            ("actor", "Actor", 140),
            ("product", "Product", 180),
            ("quantity", "Quantity", 100),
            ("amount", "Amount", 120),
            ("scope", "Scope", 130),
        )
        self.tree = TableView(
            table,
            columns=[key for key, _, _ in columns],
            show="headings",
            selectmode="browse",
            height=7,
        )
        for key, label, width in columns:
            self.tree.heading(key, text=label)
            self.tree.column(
                key,
                width=width,
                stretch=True,
                anchor="e" if key in ("quantity", "amount") else "w",
            )
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.bind("<<TreeviewSelect>>", self.show_selected)
        ttk.Label(self, text="Reason (select a row)").grid(
            row=4, column=0, sticky="w", pady=(12, 4)
        )
        details = ttk.Frame(self)
        details.grid(row=5, column=0, sticky="ew")
        details.columnconfigure(0, weight=1)
        self.detail = tk.Text(
            details,
            height=4,
            width=1,
            wrap="word",
            state="disabled",
            font="TkDefaultFont",
        )
        self.detail.grid(row=0, column=0, sticky="ew")
        scroll = ttk.Scrollbar(details, orient="vertical", command=self.detail.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.detail.configure(yscrollcommand=scroll.set)
        self.refresh()
        self._watch_session()
        self.auto_filter = AutoFilter(
            self,
            self.refresh,
            choices=(self.date_from, self.date_to),
        )

    def _set_detail(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def _clear(self):
        self.records = {}
        self.tree.delete(*self.tree.get_children())
        self._set_detail("")

    def _check_access(self):
        if self._identity is None or login_session.current_user != self._identity:
            raise AuthError("Session changed. Close this history and sign in again.")
        access = void_history_service.get_access()
        if access != self._access:
            self._clear()
            self._access = access

    def _feedback(self, message, *, error=False):
        self.status.set(message)
        self.status_label.configure(bootstyle="danger" if error else "success")

    def _watch_session(self):
        if login_session.current_user != self._identity:
            self._clear()
            self._feedback(
                "Session changed. Close this history and sign in again.", error=True
            )
        self._session_after = self.after(200, self._watch_session)

    def refresh(self):
        if hasattr(self, "auto_filter"):
            self.auto_filter.cancel()
        try:
            self._check_access()
            rows = void_history_service.list_voids(
                date_from=date.fromisoformat(self.date_from.get())
                if self.date_from.get()
                else None,
                date_to=date.fromisoformat(self.date_to.get())
                if self.date_to.get()
                else None,
            )
        except AuthError as error:
            self._clear()
            self._feedback(str(error), error=True)
            return
        except (ValidationError, ValueError) as error:
            self._feedback(str(error), error=True)
            return
        except Exception:
            logger.exception("Cannot refresh void history")
            self._feedback(
                "Cannot load void history. Use Refresh to retry.", error=True
            )
            return
        self._clear()
        self.records = {row.id: row for row in rows}
        for row in rows:
            self.tree.insert(
                "",
                "end",
                iid=str(row.id),
                values=(
                    row.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    row.actor_name,
                    row.product_name,
                    format(row.quantity, ".3f").rstrip("0").rstrip("."),
                    format_peso(row.amount),
                    "Line" if row.scope == "line" else "Transaction",
                ),
            )
        self._feedback("" if rows else "No void records match these filters.")

    def show_selected(self, _event=None):
        try:
            self._check_access()
            selected = self.tree.selection()
            if selected and (row := self.records.get(int(selected[0]))) is not None:
                self._set_detail(row.reason)
        except AuthError as error:
            self._clear()
            self._feedback(str(error), error=True)
        except Exception:
            logger.exception("Cannot read void history details")
            self._feedback(
                "Cannot read the reason. Select the row to retry.", error=True
            )

    def destroy(self):
        if self._session_after is not None:
            self.after_cancel(self._session_after)
            self._session_after = None
        self._clear()
        super().destroy()


class VoidHistoryDialog(ModalDialog):
    def __init__(self, parent):
        super().__init__(parent, "Void History")
        self.geometry("1000x600")
        self.minsize(850, 540)
        self.form = VoidHistoryScreen(self.body)
        self.form.pack(fill="both", expand=True)
        ttk.Button(self.body, text="Close", command=self.destroy).pack(
            anchor="e", pady=(8, 0)
        )
        self.first_input = self.form.date_pickers[0].calendar_button
