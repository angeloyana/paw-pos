import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttk

from pawpos.services import category_service
from pawpos.ui.owner.catalog_screen import CatalogScreen


class CategoriesScreen(CatalogScreen):
    def __init__(self, parent):
        super().__init__(parent, "Categories")
        self.category_id = None
        self.records = {}
        self.name = tk.StringVar()
        self.description = tk.StringVar()
        self.is_food = tk.BooleanVar()
        self.is_active = tk.BooleanVar(value=True)
        self.show_inactive = tk.BooleanVar(value=True)
        ttk.Button(self.toolbar, text="Add category", command=self.new).pack(
            side="left"
        )
        ttk.Button(
            self.toolbar,
            text="Deactivate selected",
            bootstyle="danger-outline",
            command=self.deactivate,
        ).pack(side="left", padx=8)
        ttk.Checkbutton(
            self.toolbar,
            text="Show inactive",
            variable=self.show_inactive,
            command=self.refresh,
        ).pack(side="left", padx=8)
        ttk.Button(self.toolbar, text="Refresh", command=self.refresh).pack(
            side="right"
        )
        self.tree = self.make_table(
            [
                ("name", "Name", 200),
                ("food", "Food", 60),
                ("description", "Description", 220),
                ("active", "Active", 65),
            ]
        )
        self.tree.bind("<<TreeviewSelect>>", self.edit_selected)
        self.form_title = ttk.Label(
            self.form, text="New category", font=("Segoe UI", 14, "bold")
        )
        self.form_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self.name_entry = self.entry(1, "Name", self.name)
        self.entry(2, "Description", self.description)
        ttk.Checkbutton(self.form, text="Food category", variable=self.is_food).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=8
        )
        ttk.Checkbutton(self.form, text="Active", variable=self.is_active).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=8
        )
        self.save_button = ttk.Button(
            self.form, text="Save category", command=self.save
        )
        self.save_button.grid(row=5, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Label(
            self.form,
            text="Categories with products cannot be deactivated.",
            wraplength=280,
        ).grid(row=6, column=0, columnspan=2, sticky="w")
        self.refresh()

    def refresh(self) -> None:
        self.perform(self._load)

    def _load(self) -> None:
        categories = category_service.list_categories(
            include_inactive=self.show_inactive.get()
        )
        self.records = {category.id: category for category in categories}
        self.tree.delete(*self.tree.get_children())
        for category in categories:
            self.tree.insert(
                "",
                "end",
                iid=str(category.id),
                values=(
                    category.name,
                    "Yes" if category.is_food else "No",
                    category.description,
                    "Yes" if category.is_active else "No",
                ),
            )
        self.new()

    def new(self) -> None:
        self.category_id = None
        self.name.set("")
        self.description.set("")
        self.is_food.set(False)
        self.is_active.set(True)
        self.form_title.configure(text="New category")
        self.tree.selection_remove(*self.tree.selection())
        self.name_entry.focus_set()

    def edit_selected(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        category = self.records[int(selected[0])]
        self.category_id = category.id
        self.name.set(category.name)
        self.description.set(category.description)
        self.is_food.set(category.is_food)
        self.is_active.set(category.is_active)
        self.form_title.configure(text="Edit category")

    def save(self) -> None:
        def save():
            category_service.save_category(
                self.name.get(),
                description=self.description.get(),
                is_food=self.is_food.get(),
                is_active=self.is_active.get(),
                category_id=self.category_id,
            )
            self._load()

        self.perform(save, "Category saved.")

    def deactivate(self) -> None:
        selected = self.tree.selection()
        if not selected:
            self.status.set("Select a category first.")
            return
        if not messagebox.askyesno(
            "Deactivate category", "Deactivate this category?", parent=self
        ):
            return

        def deactivate():
            category_service.deactivate_category(int(selected[0]))
            self._load()

        self.perform(deactivate, "Category deactivated.")
