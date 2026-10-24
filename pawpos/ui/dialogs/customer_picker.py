"""Search existing customers, quick-add one, or return to walk-in checkout."""

import tkinter as tk

import ttkbootstrap as ttk

from pawpos.core.errors import ValidationError
from pawpos.services import customer_service
from pawpos.ui.dialogs.base import ModalDialog


class CustomerPicker(ModalDialog):
    def __init__(self, parent):
        super().__init__(parent, "Select customer")
        self.search = tk.StringVar(self)
        self.name = tk.StringVar(self)
        self.contact = tk.StringVar(self)
        self.customers = {}
        self.message = tk.StringVar(self)
        self.first_input = ttk.Entry(self.body, textvariable=self.search, width=48)
        self.first_input.pack(fill="x")
        table_frame = ttk.Frame(self.body)
        table_frame.pack(fill="both", expand=True, pady=10)
        self.table = ttk.Treeview(
            table_frame,
            columns=("name", "contact"),
            show="headings",
            height=8,
            selectmode="browse",
        )
        self.table.heading("name", text="Name")
        self.table.heading("contact", text="Contact")
        self.table.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(table_frame, command=self.table.yview)
        scroll.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scroll.set)
        self.table.bind("<Double-1>", lambda _event: self.select())
        self.table.bind("<Return>", lambda _event: self.select())
        ttk.Label(self.body, textvariable=self.message, wraplength=440).pack(
            anchor="w", pady=(0, 8)
        )
        actions = ttk.Frame(self.body)
        actions.pack(fill="x")
        ttk.Button(actions, text="Select", command=self.select).pack(side="left")
        ttk.Button(actions, text="Walk-in", command=self.walk_in).pack(
            side="left", padx=8
        )
        ttk.Label(self.body, text="Add new customer").pack(anchor="w", pady=(20, 6))
        ttk.Label(self.body, text="Name").pack(anchor="w")
        ttk.Entry(self.body, textvariable=self.name).pack(fill="x")
        ttk.Label(self.body, text="Contact (optional)").pack(anchor="w")
        ttk.Entry(self.body, textvariable=self.contact).pack(fill="x")
        ttk.Button(self.body, text="Add and select", command=self.create).pack(pady=8)
        ttk.Label(
            self.body, textvariable=self.error, bootstyle="danger", wraplength=440
        ).pack()
        ttk.Button(self.body, text="Cancel", command=self.destroy).pack()
        self.search.trace_add("write", lambda *_args: self.refresh())
        self.refresh()

    def refresh(self):
        def load():
            customers = customer_service.list_customers(self.search.get())
            self.customers = {str(row.id): row for row in customers}
            self.table.delete(*self.table.get_children())
            self.message.set(
                "Select a customer, continue as Walk-in, or add a new one."
                if customers
                else "No customers match your search. Add one below or continue as Walk-in."
                if self.search.get().strip()
                else "No saved customers. Add one below or continue as Walk-in."
            )
            for key, row in self.customers.items():
                self.table.insert("", "end", iid=key, values=(row.name, row.contact))

        self.perform(load)

    def select(self):
        def accept():
            selection = self.table.selection()
            if not selection:
                raise ValidationError("Select a customer first.")
            self.result = self.customers[selection[0]]

        if self.perform(accept):
            self.destroy()

    def create(self):
        def accept():
            self.result = customer_service.create_customer(
                self.name.get(), self.contact.get()
            )

        if self.perform(accept):
            self.destroy()

    def walk_in(self):
        # False distinguishes an explicit walk-in choice from cancelling (None).
        self.result = False
        self.destroy()
