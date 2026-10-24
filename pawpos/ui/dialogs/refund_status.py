"""Shared refund decisions and confirmed payout recording."""

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from pawpos.core.errors import ValidationError
from pawpos.core.money import format_peso, format_qty
from pawpos.services import refund_tracking_service as tracking
from pawpos.ui.dialogs.base import ModalDialog

STATUS_LABELS = {
    "all": "All",
    "pending": "Pending",
    "rejected": "Rejected",
    "awaiting_payout": "Approved — awaiting payout",
    "paid": "Paid",
    "legacy_paid": "Assumed paid before tracking",
}


class PayoutDialog(ModalDialog):
    def __init__(self, parent, refund, *, correction=False):
        super().__init__(parent, "Correct payout" if correction else "Record payout")
        self.geometry("650x420")
        self.refund = refund
        self.correction = correction
        self.method = tk.StringVar(
            self, value=refund.payout.method if correction else "cash"
        )
        self.reference = tk.StringVar(
            self, value=(refund.payout.reference or "") if correction else ""
        )
        self.reason = tk.StringVar(self)
        request = refund.request
        ttk.Label(
            self.body,
            text=f"Refund #{request.id} — {request.receipt_number}\nFull amount: {format_peso(request.total_amount)}",
            wraplength=580,
        ).pack(anchor="w", pady=8)
        ttk.Label(self.body, text="Payment method").pack(anchor="w")
        self.first_input = ttk.Combobox(
            self.body,
            textvariable=self.method,
            values=("cash", "gcash"),
            state="readonly",
        )
        self.first_input.pack(fill="x", pady=4)
        ttk.Label(
            self.body, text="GCash reference (required for GCash, up to 50 characters)"
        ).pack(anchor="w")
        ttk.Entry(self.body, textvariable=self.reference).pack(fill="x", pady=4)
        if correction:
            ttk.Label(self.body, text="Correction reason (required)").pack(anchor="w")
            ttk.Entry(self.body, textvariable=self.reason).pack(fill="x", pady=4)
        else:
            ttk.Label(
                self.body,
                text="Confirm only after returning the money. Coordinate with other staff before paying the customer.",
                wraplength=580,
            ).pack(anchor="w", pady=8)
        ttk.Label(
            self.body, textvariable=self.error, bootstyle="danger", wraplength=580
        ).pack(anchor="w", pady=8)
        actions = ttk.Frame(self.body)
        actions.pack(fill="x", side="bottom")
        self.save_button = ttk.Button(
            actions,
            text="Save correction" if correction else "Confirm money returned",
            command=self.save,
        )
        self.save_button.pack(side="left")
        ttk.Button(
            actions, text="Cancel", command=self.destroy, bootstyle="secondary"
        ).pack(side="right")

    def save(self):
        def save():
            request = self.refund.request
            # Validate before the confirmation so incomplete input cannot imply payment.
            if self.method.get() == "gcash" and not self.reference.get().strip():
                raise ValidationError("GCash reference is required.")
            if len(self.reference.get().strip()) > 50:
                raise ValidationError("GCash reference must be at most 50 characters.")
            if self.correction and not self.reason.get().strip():
                raise ValidationError("Correction reason is required.")
            wording = (
                "Save corrected payment details"
                if self.correction
                else "Confirm the full amount has already been returned"
            )
            if not messagebox.askyesno(
                "Correct payout" if self.correction else "Confirm money returned",
                f"{wording}?\nRefund #{request.id}\n{request.receipt_number}\n{format_peso(request.total_amount)} via {self.method.get()}\nReference: {self.reference.get().strip() or '—'}",
                parent=self,
            ):
                return
            if self.correction:
                self.result = tracking.correct_payout(
                    request.id,
                    self.method.get(),
                    self.reference.get(),
                    self.reason.get(),
                )
            else:
                self.result = tracking.record_payout(
                    request.id, self.method.get(), self.reference.get()
                )

        if self.perform(save) and self.result is not None:
            self.save_button.configure(state="disabled")
            self.destroy()


class RefundStatusDialog(ModalDialog):
    def __init__(self, parent, *, owner=False, initial_id=None, unread_only=False):
        super().__init__(parent, "Refunds — status and payouts")
        self.geometry("1050x650")
        self.minsize(850, 550)
        self.owner = owner
        self.selected = None
        self.records = {}
        self.receipt = tk.StringVar(self)
        self.filter = tk.StringVar(
            self, value="Unread decisions" if unread_only else "All"
        )
        toolbar = ttk.Frame(self.body)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Receipt").pack(side="left")
        self.first_input = ttk.Entry(toolbar, textvariable=self.receipt, width=24)
        self.first_input.pack(side="left", padx=8)
        self.first_input.bind("<Return>", lambda _event: self.refresh())
        ttk.Combobox(
            toolbar,
            textvariable=self.filter,
            values=(*STATUS_LABELS.values(), "Unread decisions"),
            state="readonly",
            width=30,
        ).pack(side="left")
        self.refresh_button = ttk.Button(toolbar, text="Refresh", command=self.refresh)
        self.refresh_button.pack(side="left", padx=8)
        self.tree = ttk.Treeview(
            self.body,
            columns=("id", "receipt", "requester", "amount", "status"),
            show="headings",
            height=8,
            selectmode="browse",
        )
        for key, title, width in (
            ("id", "ID", 45),
            ("receipt", "Receipt", 200),
            ("requester", "Requester", 150),
            ("amount", "Amount", 100),
            ("status", "Status", 260),
        ):
            self.tree.heading(key, text=title)
            self.tree.column(
                key, width=width, minwidth=45, anchor="e" if key == "amount" else "w"
            )
        self.tree.pack(fill="both", expand=True, pady=(12, 0))
        horizontal = ttk.Scrollbar(
            self.body, orient="horizontal", command=self.tree.xview
        )
        horizontal.pack(fill="x")
        self.tree.configure(xscrollcommand=horizontal.set)
        vertical = ttk.Scrollbar(self.tree, command=self.tree.yview)
        vertical.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vertical.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.select())
        self.detail = tk.Text(self.body, height=9, wrap="word", state="disabled")
        self.detail.pack(fill="both", expand=True, pady=8)
        detail_scroll = ttk.Scrollbar(self.detail, command=self.detail.yview)
        detail_scroll.pack(side="right", fill="y")
        self.detail.configure(yscrollcommand=detail_scroll.set)
        ttk.Label(
            self.body, textvariable=self.error, bootstyle="danger", wraplength=950
        ).pack(anchor="w", pady=4)
        actions = ttk.Frame(self.body)
        actions.pack(fill="x")
        self.payout_button = ttk.Button(
            actions, text="Record payout", command=self.payout, state="disabled"
        )
        self.payout_button.pack(side="left")
        self.correct_button = ttk.Button(
            actions,
            text="Correct payout details",
            command=lambda: self.payout(correction=True),
            state="disabled",
        )
        if owner:
            self.correct_button.pack(side="left", padx=8)
        ttk.Button(
            actions, text="Close", command=self.destroy, bootstyle="secondary"
        ).pack(side="right")
        self.refresh()
        if initial_id is not None and self.tree.exists(str(initial_id)):
            self.tree.selection_set(str(initial_id))
            self.select()

    def _detail(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def _clear(self):
        self.selected = None
        self.payout_button.configure(state="disabled")
        self.correct_button.configure(state="disabled")

    def refresh(self):
        def load():
            status = next(
                (
                    key
                    for key, value in STATUS_LABELS.items()
                    if value == self.filter.get()
                ),
                "all",
            )
            rows = tracking.list_refunds(self.receipt.get(), status)
            if self.filter.get() == "Unread decisions":
                unread = {notice.request_id for notice in tracking.unread_notices()}
                rows = [row for row in rows if row.request.id in unread]
            # Keep previous data if either read fails.
            self._clear()
            self.records = {row.request.id: row for row in rows}
            self.tree.delete(*self.tree.get_children())
            for row in rows:
                request = row.request
                self.tree.insert(
                    "",
                    "end",
                    iid=str(request.id),
                    values=(
                        request.id,
                        request.receipt_number,
                        request.requester,
                        format_peso(request.total_amount),
                        STATUS_LABELS[row.status],
                    ),
                )
            self._detail(
                "Select a request to see its decision and payment details."
                if rows
                else "No refund requests match these filters."
            )

        self.perform(load)

    def select(self):
        selection = self.tree.selection()
        if not selection:
            return
        self._clear()

        def load():
            row = tracking.get_refund(int(selection[0]))
            request = row.request
            lines = [
                f"Refund #{request.id} — {request.receipt_number} — {STATUS_LABELS[row.status]}",
                f"Amount: {format_peso(request.total_amount)}; requested by {request.requester} at {request.requested_at:%Y-%m-%d %H:%M}",
                f"Reason: {request.reason}",
            ]
            if request.reviewed_at:
                lines.append(
                    f"Reviewed by {request.reviewer} at {request.reviewed_at:%Y-%m-%d %H:%M}. {request.review_note}"
                )
            lines.extend(
                f"{item.product_name}: {format_qty(item.quantity, item.unit_type)} — {format_peso(item.amount)}"
                for item in request.items
            )
            if row.payout:
                payout = row.payout
                if payout.legacy_assumed_paid:
                    lines.append(
                        "Assumed paid before tracking; method, reference, cashier, and payment time unknown."
                    )
                else:
                    lines.append(
                        f"Paid via {payout.method}; reference: {payout.reference or '—'}; recorded by {payout.paid_by} at {payout.paid_at:%Y-%m-%d %H:%M}."
                    )
            for correction in row.corrections:
                lines.append(
                    f"Correction by {correction.corrected_by} at {correction.corrected_at:%Y-%m-%d %H:%M}: {correction.old_method} / {correction.old_reference or '—'} → {correction.new_method} / {correction.new_reference or '—'}. Reason: {correction.reason}"
                )
            self._detail("\n".join(lines))
            # A failed acknowledgment leaves the decision visible and unread for retry.
            tracking.acknowledge_decision(request.id)
            self.selected = row
            self.payout_button.configure(
                state="normal" if row.status == "awaiting_payout" else "disabled"
            )
            self.correct_button.configure(
                state="normal" if self.owner and row.status == "paid" else "disabled"
            )

        self.perform(load)

    def payout(self, *, correction=False):
        def show():
            if self.selected is None:
                raise ValidationError("Select a refund first.")
            current = tracking.get_refund(self.selected.request.id)
            expected = "paid" if correction else "awaiting_payout"
            if current.status != expected:
                self._clear()
                raise ValidationError(
                    "Refund status changed. Refresh before continuing."
                )
            result = PayoutDialog(self, current, correction=correction).show()
            if result is None:
                return
            # Disable committed actions before the fallible list refresh.
            self._clear()
            self.refresh()
            if self.error.get():
                raise ValidationError(
                    f"Payment details saved. Refresh to see them. {self.error.get()}"
                )

        self.perform(show)
