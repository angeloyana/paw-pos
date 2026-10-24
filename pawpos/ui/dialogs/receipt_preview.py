"""Read-only receipt preview with a default-viewer PDF printing action."""

import tkinter as tk

import ttkbootstrap as ttk

from pawpos.services import receipt_service
from pawpos.ui.dialogs.base import ModalDialog


class ReceiptPreview(ModalDialog):
    def __init__(self, parent, receipt):
        super().__init__(parent, f"Receipt — {receipt.receipt_number}")
        self.receipt = receipt
        self.message = tk.StringVar(self)
        container = ttk.Frame(self.body)
        container.pack(fill="both", expand=True)
        self.text = tk.Text(
            container, width=42, height=25, wrap="none", font="TkFixedFont"
        )
        self.text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(container, command=self.text.yview)
        scroll.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scroll.set)
        self.text.insert("1.0", receipt_service.receipt_text(receipt))
        self.text.configure(state="disabled")
        ttk.Label(self.body, textvariable=self.message, wraplength=400).pack(pady=8)
        ttk.Label(
            self.body, textvariable=self.error, bootstyle="danger", wraplength=400
        ).pack()
        self.first_input = ttk.Button(self.body, text="Print", command=self.print_pdf)
        self.first_input.pack(side="left", pady=8)
        ttk.Button(self.body, text="Close", command=self.destroy).pack(side="right")

    def print_pdf(self):
        def generate():
            path = receipt_service.print_receipt(self.receipt)
            self.message.set(f"PDF opened: {path}\nPrint from the PDF viewer.")

        self.perform(generate)
