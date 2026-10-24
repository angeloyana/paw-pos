"""Owner pending refunds and processed review history."""

import logging
import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

try:
    from ttkbootstrap.widgets.scrolled import ScrolledFrame
except ImportError:  # Compatibility with earlier supported ttkbootstrap 1.x.
    from ttkbootstrap.scrolled import ScrolledFrame

from pawpos.core.errors import PawPOSError, ValidationError
from pawpos.core.money import format_peso, format_qty
from pawpos.services import refund_service, refund_tracking_service
from pawpos.ui.dialogs.refund_status import STATUS_LABELS, RefundStatusDialog

logger = logging.getLogger(__name__)


class RefundsScreen(ttk.Frame):
    def __init__(self, parent, on_change=lambda: None):
        super().__init__(parent, padding=20)
        self.on_change = on_change
        self.records = {}
        self.selected = None
        self.resellable = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.status = tk.StringVar(self)
        self.detail = tk.StringVar(
            self, value="Select a refund request to see its items."
        )
        self.note = tk.StringVar(self)
        ttk.Label(self, text="Refunds", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="e")
        self.payouts_button = ttk.Button(
            toolbar, text="Status / payouts", command=self.open_payouts
        )
        self.payouts_button.pack(side="left", padx=8)
        ttk.Button(toolbar, text="Refresh", command=self.refresh).pack(side="right")
        ttk.Label(self, textvariable=self.status, wraplength=900).grid(
            row=1, column=0, sticky="ew", pady=8
        )
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=2, column=0, sticky="nsew")
        self.trees = {}
        for title in ("Pending", "History"):
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=title)
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)
            tree = ttk.Treeview(
                tab,
                columns=(
                    "id",
                    "receipt",
                    "requester",
                    "date",
                    "items",
                    "reason",
                    "amount",
                    "status",
                ),
                show="headings",
                selectmode="browse",
                height=6,
            )
            for key, label, width in (
                ("id", "ID", 50),
                ("receipt", "Receipt", 185),
                ("requester", "Requester", 140),
                ("date", "Requested", 140),
                ("items", "Items", 55),
                ("reason", "Reason", 180),
                ("amount", "Amount", 100),
                ("status", "Status", 90),
            ):
                tree.heading(key, text=label)
                tree.column(
                    key,
                    width=width,
                    minwidth=45,
                    anchor="e" if key in ("items", "amount") else "w",
                )
            tree.grid(row=0, column=0, sticky="nsew")
            vertical = ttk.Scrollbar(tab, command=tree.yview)
            vertical.grid(row=0, column=1, sticky="ns")
            horizontal = ttk.Scrollbar(tab, orient="horizontal", command=tree.xview)
            horizontal.grid(row=1, column=0, sticky="ew")
            tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            tree.bind(
                "<<TreeviewSelect>>", lambda _event, name=title: self.select(name)
            )
            self.trees[title] = tree
        self.notebook.bind("<<NotebookTabChanged>>", self._tab_changed)
        ttk.Label(self, textvariable=self.detail, wraplength=900).grid(
            row=3, column=0, sticky="ew", pady=8
        )
        self.lines = ScrolledFrame(self, height=125, autohide=True)
        self.lines.grid(row=4, column=0, sticky="ew")
        controls = ttk.Frame(self)
        controls.grid(row=5, column=0, sticky="ew", pady=8)
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="Rejection note").grid(row=0, column=0, padx=(0, 8))
        self.note_entry = ttk.Entry(controls, textvariable=self.note)
        self.note_entry.grid(row=0, column=1, sticky="ew")
        self.approve_button = ttk.Button(
            controls, text="Approve", command=self.approve, state="disabled"
        )
        self.approve_button.grid(row=0, column=2, padx=8)
        self.reject_button = ttk.Button(
            controls,
            text="Reject",
            command=self.reject,
            bootstyle="danger",
            state="disabled",
        )
        self.reject_button.grid(row=0, column=3)
        self.refresh()

    def open_payouts(self):
        request_id = self.selected.id if self.selected else None
        if self.perform(
            lambda: RefundStatusDialog(self, owner=True, initial_id=request_id).show()
        ):
            self.refresh()

    def _tab_changed(self, _event=None):
        self.clear_selection()
        for tree in self.trees.values():
            tree.selection_remove(*tree.selection())

    def perform(self, action, success=""):
        try:
            action()
        except PawPOSError as error:
            self.status.set(str(error))
            return False
        except Exception:
            logger.exception("Refund review failed")
            self.status.set("Cannot complete this action. Please try again.")
            return False
        self.status.set(success)
        return True

    def clear_selection(self):
        self.selected = None
        self.resellable.clear()
        self.note.set("")
        self.detail.set("Select a refund request to see its items.")
        for child in self.lines.winfo_children():
            child.destroy()
        self.approve_button.configure(state="disabled")
        self.reject_button.configure(state="disabled")
        self.note_entry.configure(state="disabled")

    def refresh(self):
        self.perform(self._load)

    def _load(self):
        pending, history = refund_service.list_pending(), refund_service.list_history()
        self.clear_selection()
        self.records = {r.id: r for r in (*pending, *history)}
        for title, requests in (("Pending", pending), ("History", history)):
            tree = self.trees[title]
            tree.delete(*tree.get_children())
            for request in requests:
                tree.insert(
                    "",
                    "end",
                    iid=str(request.id),
                    values=(
                        request.id,
                        request.receipt_number,
                        request.requester,
                        request.requested_at.strftime("%Y-%m-%d %H:%M"),
                        len(request.items),
                        request.reason,
                        format_peso(request.total_amount),
                        request.status,
                    ),
                )
        self.notebook.tab(0, text=f"Pending ({len(pending)})")
        self.on_change()
        if not pending:
            self.detail.set(
                "No pending refund requests. Processed reviews appear in History."
            )

    def select(self, title):
        selection = self.trees[title].selection()
        if not selection:
            return
        self.clear_selection()
        request = self.records[int(selection[0])]
        self.selected = request
        pending = request.status == "pending"
        review = (
            f"\nReviewed by {request.reviewer} at {request.reviewed_at:%Y-%m-%d %H:%M}. {request.review_note}"
            if request.reviewed_at
            else ""
        )
        self.detail.set(
            f"#{request.id} — {request.receipt_number} — {request.status} — {format_peso(request.total_amount)}\nReason: {request.reason}{review}"
        )
        if request.status == "approved":

            def payment_details():
                tracked = refund_tracking_service.get_refund(request.id)
                self.detail.set(
                    self.detail.get()
                    + f"\nPayment: {STATUS_LABELS[tracked.status]}. Open Status / payouts for details and actions."
                )

            self.perform(payment_details)
        for index, item in enumerate(request.items):
            ttk.Label(
                self.lines,
                text=f"{item.product_name}: {format_qty(item.quantity, item.unit_type)} — {format_peso(item.amount)} — {'Opened/used' if item.is_opened else 'Unopened'}",
                wraplength=600,
            ).grid(row=index, column=0, sticky="w", padx=(0, 12), pady=6)
            if pending:
                value = tk.StringVar(self, value="No")
                self.resellable[item.id] = value
                ttk.Label(self.lines, text="Resellable").grid(
                    row=index, column=1, padx=8
                )
                ttk.Combobox(
                    self.lines,
                    textvariable=value,
                    values=("Yes", "No"),
                    state="readonly",
                    width=6,
                ).grid(row=index, column=2, padx=8)
            else:
                ttk.Label(
                    self.lines,
                    text=f"Resellable: {'Yes' if item.resellable else 'No' if item.resellable is False else '—'}",
                ).grid(row=index, column=1, padx=8)
        self.approve_button.configure(state="normal" if pending else "disabled")
        self.reject_button.configure(state="normal" if pending else "disabled")
        self.note_entry.configure(state="normal" if pending else "disabled")

    def _pending_id(self):
        if self.selected is None or self.selected.status != "pending":
            raise ValidationError("Select a pending refund first.")
        return self.selected.id

    def _after_review(self):
        # Disable the committed decision before any fallible refresh.
        self.clear_selection()
        try:
            self._load()
        except Exception:
            logger.exception("Refund saved, but refresh failed")
            raise ValidationError(
                "Review saved. Refresh refunds to see the updated lists."
            ) from None

    def approve(self):
        def save():
            request_id = self._pending_id()
            if not messagebox.askyesno(
                "Approve refund",
                f"Approve refund #{request_id} for {format_peso(self.selected.total_amount)}?\nOnly resellable lines will return to stock. Return money manually.",
                parent=self,
            ):
                return
            refund_service.approve(
                request_id,
                {
                    item_id: value.get() == "Yes"
                    for item_id, value in self.resellable.items()
                },
            )
            self._after_review()

        self.perform(save)

    def reject(self):
        def save():
            request_id = self._pending_id()
            if not self.note.get().strip():
                raise ValidationError("Rejection note is required.")
            if not messagebox.askyesno(
                "Reject refund",
                f"Reject refund #{request_id}? Stock will remain unchanged.",
                parent=self,
            ):
                return
            refund_service.reject(request_id, self.note.get())
            self._after_review()

        self.perform(save)
