"""Shared table, form, and feedback helpers for the two catalog screens."""

import logging
import tkinter as tk
from collections.abc import Callable

import ttkbootstrap as ttk

from pawpos.core.errors import PawPOSError
from pawpos.ui.widgets.table import TableView

logger = logging.getLogger(__name__)


class CatalogScreen(ttk.Frame):
    def __init__(self, parent, title: str):
        super().__init__(parent, padding=20)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        ttk.Label(self, text=title, font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.status = tk.StringVar()
        self.status_label = ttk.Label(self, textvariable=self.status, wraplength=900)
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(8, 12))
        self.toolbar = ttk.Frame(self)
        self.toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self.body = ttk.Frame(self)
        self.body.grid(row=3, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)
        form_view = ttk.Frame(self.body)
        form_view.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
        form_view.rowconfigure(0, weight=1)
        form_view.columnconfigure(0, weight=1)
        self.form_canvas = tk.Canvas(
            form_view,
            width=320,
            height=1,
            highlightthickness=0,
            background=ttk.Style().colors.bg,
        )
        self.form_canvas.grid(row=0, column=0, sticky="nsew")
        form_scroll = ttk.Scrollbar(
            form_view, orient="vertical", command=self.form_canvas.yview
        )
        form_scroll.grid(row=0, column=1, sticky="ns")
        self.form_canvas.configure(yscrollcommand=form_scroll.set)
        self.form = ttk.Frame(self.form_canvas)
        form_window = self.form_canvas.create_window(
            0, 0, window=self.form, anchor="nw"
        )
        self.form.bind(
            "<Configure>",
            lambda _event: self.form_canvas.configure(
                scrollregion=self.form_canvas.bbox("all"),
                width=self.form.winfo_reqwidth(),
            ),
        )
        self.form_canvas.bind(
            "<Configure>",
            lambda event: self.form_canvas.itemconfigure(
                form_window, width=event.width
            ),
        )
        self.form.columnconfigure(1, weight=1)

    def perform(self, action: Callable[[], None], success: str = "") -> bool:
        try:
            action()
        except PawPOSError as error:
            self.status.set(str(error))
            self.status_label.configure(bootstyle="danger")
            return False
        except Exception:
            logger.exception("Catalog operation failed")
            self.status.set(
                "Cannot complete this action. Please try again or contact the shop owner."
            )
            self.status_label.configure(bootstyle="danger")
            return False
        self.status.set(success)
        self.status_label.configure(bootstyle="success")
        return True

    def make_table(self, columns: list[tuple[str, str, int]]) -> TableView:
        container = ttk.Frame(self.body)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        tree = TableView(
            container,
            columns=[key for key, _, _ in columns],
            show="headings",
            selectmode="browse",
            height=18,
        )
        for key, title, width in columns:
            tree.heading(key, text=title)
            tree.column(
                key,
                width=width,
                minwidth=45,
                stretch=key == "name",
                anchor="e" if key in ("price", "stock", "threshold") else "w",
            )
        tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        return tree

    def entry(self, row: int, label: str, variable: tk.StringVar) -> ttk.Entry:
        ttk.Label(self.form, text=label).grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=6
        )
        widget = ttk.Entry(self.form, textvariable=variable, width=22)
        widget.grid(row=row, column=1, sticky="ew", pady=6)
        return widget
