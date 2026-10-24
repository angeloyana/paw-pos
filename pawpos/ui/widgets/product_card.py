"""Product cards and a screen-owned thumbnail cache."""

from pathlib import Path

import ttkbootstrap as ttk
from PIL import Image, ImageTk, UnidentifiedImageError

from pawpos.config import ASSETS_DIR, PROJECT_ROOT
from pawpos.core.money import format_peso, format_qty


class ThumbnailCache:
    def __init__(self, master):
        self.master = master
        self.images = {}

    def get(self, image_path, size=(96, 96)):
        path = (
            PROJECT_ROOT / image_path
            if image_path
            else ASSETS_DIR / "placeholder_product.png"
        )
        key = (str(path), size)
        if key not in self.images:
            try:
                image = self._load(path, size)
            except (
                OSError,
                ValueError,
                UnidentifiedImageError,
                Image.DecompressionBombError,
            ):
                image = self._load(ASSETS_DIR / "placeholder_product.png", size)
            self.images[key] = ImageTk.PhotoImage(image, master=self.master)
        return self.images[key]

    @staticmethod
    def _load(path: Path, size):
        with Image.open(path) as source:
            image = source.convert("RGBA")
            image.thumbnail(size, Image.Resampling.LANCZOS)
            return image


class ProductCard(ttk.Frame):
    def __init__(self, parent, product, cache, on_add):
        super().__init__(parent, padding=8, relief="ridge", borderwidth=1)
        self.image = cache.get(product.image_path)
        self.button = ttk.Button(
            self,
            image=self.image,
            command=on_add,
            bootstyle="light",
            state="normal" if product.stock_quantity > 0 else "disabled",
        )
        self.button.pack()
        ttk.Label(
            self, text=product.name, wraplength=130, anchor="center", width=17
        ).pack(pady=4)
        ttk.Label(
            self,
            text=format_peso(product.unit_price)
            + ("/kg" if product.unit_type == "kg" else ""),
        ).pack()
        ttk.Label(
            self,
            text=("Stock: " + format_qty(product.stock_quantity, product.unit_type))
            if product.stock_quantity
            else "Out of stock",
            bootstyle="secondary",
        ).pack(pady=4)
        if product.stock_quantity > 0:
            self.bind("<Button-1>", lambda _event: on_add())
            for child in self.winfo_children():
                if child is not self.button:
                    child.bind("<Button-1>", lambda _event: on_add())
