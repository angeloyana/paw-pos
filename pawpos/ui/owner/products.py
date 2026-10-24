import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from PIL import Image, ImageTk, UnidentifiedImageError

from pawpos.config import ASSETS_DIR, PROJECT_ROOT
from pawpos.core.errors import ValidationError
from pawpos.core.money import format_peso, format_qty
from pawpos.services import category_service, product_service
from pawpos.ui.owner.catalog_screen import CatalogScreen


class ProductsScreen(CatalogScreen):
    def __init__(self, parent):
        super().__init__(parent, "Products")
        self.product_id = None
        self.records = {}
        self.category_ids = {}
        self.image_source = None
        self.search = tk.StringVar()
        self.filter_category = tk.StringVar(value="All categories")
        self.show_inactive = tk.BooleanVar(value=True)
        self.name = tk.StringVar()
        self.category = tk.StringVar()
        self.price = tk.StringVar(value="0.00")
        self.unit = tk.StringVar(value="piece")
        self.stock = tk.StringVar(value="0")
        self.threshold = tk.StringVar(value="0")
        self.supplier = tk.StringVar()
        self.is_active = tk.BooleanVar(value=True)
        ttk.Label(self.toolbar, text="Search").pack(side="left", padx=(0, 6))
        search_entry = ttk.Entry(self.toolbar, textvariable=self.search, width=22)
        search_entry.pack(side="left")
        search_entry.bind("<KeyRelease>", lambda _event: self.refresh())
        self.filter_combo = ttk.Combobox(
            self.toolbar, textvariable=self.filter_category, state="readonly", width=20
        )
        self.filter_combo.pack(side="left", padx=8)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        ttk.Checkbutton(
            self.toolbar,
            text="Show inactive",
            variable=self.show_inactive,
            command=self.refresh,
        ).pack(side="left")
        ttk.Button(self.toolbar, text="Refresh", command=self.refresh).pack(
            side="right"
        )
        self.tree = self.make_table(
            [
                ("name", "Name", 170),
                ("category", "Category", 110),
                ("unit", "Unit", 50),
                ("price", "Price", 90),
                ("stock", "Stock", 80),
                ("threshold", "Threshold", 80),
                ("active", "Active", 55),
            ]
        )
        self.tree.bind("<<TreeviewSelect>>", self.edit_selected)
        self.form_title = ttk.Label(
            self.form, text="New product", font=("Segoe UI", 14, "bold")
        )
        self.form_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.name_entry = self.entry(1, "Name", self.name)
        ttk.Label(self.form, text="Category").grid(row=2, column=0, sticky="w")
        self.category_combo = ttk.Combobox(
            self.form, textvariable=self.category, state="readonly", width=20
        )
        self.category_combo.grid(row=2, column=1, sticky="ew", pady=6)
        self.entry(3, "Price (₱)", self.price)
        ttk.Label(self.form, text="Unit").grid(row=4, column=0, sticky="w")
        self.unit_combo = ttk.Combobox(
            self.form,
            textvariable=self.unit,
            values=("piece", "kg"),
            state="readonly",
            width=20,
        )
        self.unit_combo.grid(row=4, column=1, sticky="ew", pady=6)
        self.stock_entry = self.entry(5, "Initial stock", self.stock)
        self.entry(6, "Low-stock limit", self.threshold)
        self.entry(7, "Supplier", self.supplier)
        ttk.Checkbutton(self.form, text="Active", variable=self.is_active).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=6
        )
        image_row = ttk.Frame(self.form)
        image_row.grid(row=9, column=0, columnspan=2, sticky="ew", pady=6)
        self.preview = ttk.Label(image_row)
        self.preview.pack(side="left")
        ttk.Button(image_row, text="Choose image…", command=self.choose_image).pack(
            side="left", padx=12
        )
        buttons = ttk.Frame(self.form)
        buttons.grid(row=10, column=0, columnspan=2, sticky="ew", pady=8)
        self.save_button = ttk.Button(buttons, text="Save product", command=self.save)
        self.save_button.pack(side="left", fill="x", expand=True)
        ttk.Button(
            buttons, text="New", command=self.new, bootstyle="secondary-outline"
        ).pack(side="left", padx=6)
        ttk.Button(
            self.form,
            text="Deactivate selected",
            bootstyle="danger-outline",
            command=self.deactivate,
        ).grid(row=11, column=0, columnspan=2, sticky="ew", pady=6)
        self.stock_note = ttk.Label(
            self.form,
            text="For existing products, change stock through Inventory.",
            wraplength=290,
        )
        self.stock_note.grid(row=12, column=0, columnspan=2, sticky="w", pady=6)
        self.refresh()

    def refresh(self) -> None:
        if self.perform(self._load) and not self.records:
            self.status.set(
                "No products match. Adjust the filters or add a new product."
            )

    def _load(self) -> None:
        categories = category_service.list_categories(include_inactive=True)
        self.category_ids = {
            category.name: category.id for category in categories if category.is_active
        }
        self.category_combo.configure(values=list(self.category_ids))
        filters = {category.name: category.id for category in categories}
        self.filter_combo.configure(values=["All categories", *filters])
        products = product_service.list_products(
            self.search.get(),
            filters.get(self.filter_category.get()),
            include_inactive=self.show_inactive.get(),
        )
        self.records = {product.id: product for product in products}
        self.tree.delete(*self.tree.get_children())
        for product in products:
            self.tree.insert(
                "",
                "end",
                iid=str(product.id),
                values=(
                    product.name,
                    product.category_name,
                    product.unit_type,
                    format_peso(product.unit_price),
                    format_qty(product.stock_quantity, product.unit_type),
                    format_qty(product.low_stock_threshold, product.unit_type),
                    "Yes" if product.is_active else "No",
                ),
            )
        self.new(focus=False)

    def new(self, *, focus=True) -> None:
        self.product_id = None
        self.image_source = None
        self.name.set("")
        self.category.set(next(iter(self.category_ids), ""))
        self.price.set("0.00")
        self.unit.set("piece")
        self.stock.set("0")
        self.threshold.set("0")
        self.supplier.set("")
        self.is_active.set(True)
        self.stock_entry.configure(state="normal")
        self.form_title.configure(text="New product")
        self.tree.selection_remove(*self.tree.selection())
        self.show_image(None)
        if focus:
            self.name_entry.focus_set()

    def edit_selected(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        product = self.records[int(selected[0])]
        self.product_id = product.id
        self.image_source = None
        self.name.set(product.name)
        self.category.set(product.category_name)
        self.price.set(str(product.unit_price))
        self.unit.set(product.unit_type)
        self.stock.set(str(product.stock_quantity))
        self.threshold.set(str(product.low_stock_threshold))
        self.supplier.set(product.supplier)
        self.is_active.set(product.is_active)
        self.stock_entry.configure(state="disabled")
        self.form_title.configure(text="Edit product")
        self.show_image(
            PROJECT_ROOT / product.image_path if product.image_path else None
        )

    def show_image(self, path: Path | None) -> None:
        try:
            with Image.open(path or ASSETS_DIR / "placeholder_product.png") as image:
                image.thumbnail((80, 80))
                photo = ImageTk.PhotoImage(image.copy(), master=self)
        except (OSError, ValueError, UnidentifiedImageError):
            with Image.open(ASSETS_DIR / "placeholder_product.png") as image:
                image.thumbnail((80, 80))
                photo = ImageTk.PhotoImage(image.copy(), master=self)
        self.preview.configure(image=photo)
        self.preview.image = photo

    def choose_image(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Choose product image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.gif *.bmp")],
        )
        if path:

            def preview():
                try:
                    with Image.open(path) as image:
                        image.verify()
                except (
                    OSError,
                    ValueError,
                    UnidentifiedImageError,
                    Image.DecompressionBombError,
                ):
                    raise ValidationError("Choose a valid image file.") from None
                self.show_image(Path(path))
                self.image_source = path

            self.perform(preview)

    def save(self) -> None:
        def save():
            category_id = self.category_ids.get(self.category.get())
            if category_id is None:
                raise ValidationError("Choose an active category before saving.")
            product_service.save_product(
                self.name.get(),
                category_id,
                self.price.get(),
                self.unit.get(),
                product_id=self.product_id,
                initial_stock=self.stock.get() if self.product_id is None else None,
                low_stock_threshold=self.threshold.get(),
                supplier=self.supplier.get(),
                is_active=self.is_active.get(),
                image_source=self.image_source,
            )
            self._load()

        self.perform(save, "Product saved.")

    def deactivate(self) -> None:
        selected = self.tree.selection()
        if not selected:
            self.status.set("Select a product first.")
            return
        if not messagebox.askyesno(
            "Deactivate product",
            "Deactivate this product? It will be hidden from selling.",
            parent=self,
        ):
            return

        def deactivate():
            product_service.deactivate_product(int(selected[0]))
            self._load()

        self.perform(deactivate, "Product deactivated.")
