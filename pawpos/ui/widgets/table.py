"""Consistent, theme-aware tables for workspaces and dialogs."""

from tkinter import font

import ttkbootstrap as ttk
from ttkbootstrap.style import Colors


class TableView(ttk.Treeview):
    STYLE = "PawPOS.Treeview"
    STRIPES = ("pawpos_even", "pawpos_odd")

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._stripe_job = None
        self._body_font = font.nametofont("TkDefaultFont").copy()
        self._heading_size = max(10, self._body_font.cget("size"))
        self._body_font.configure(size=max(11, self._body_font.cget("size")))
        self.refresh_theme()
        self.configure(style=self.STYLE)

    def refresh_theme(self):
        style = ttk.Style()
        colors = style.colors
        scale = self.winfo_fpixels("1i") / 96
        padding = max(4, round(6 * scale))
        self._cell_padding = max(8, round(8 * scale))
        stripe = Colors.make_transparent(0.045, colors.inputfg, colors.inputbg)
        header = Colors.make_transparent(0.09, colors.primary, colors.inputbg)
        style.configure(
            self.STYLE,
            font=(self._body_font.cget("family"), self._body_font.cget("size")),
            rowheight=max(round(32 * scale), self._body_font.metrics("linespace") + 12),
            background=colors.inputbg,
            fieldbackground=colors.inputbg,
            foreground=colors.inputfg,
            bordercolor=colors.border,
            borderwidth=1,
            relief="solid",
            padding=(self._cell_padding, 0),
        )
        style.map(
            self.STYLE,
            background=[("selected", colors.selectbg)],
            foreground=[("selected", colors.selectfg)],
        )
        style.configure(
            f"{self.STYLE}.Heading",
            font=(self._body_font.cget("family"), self._heading_size, "bold"),
            padding=(self._cell_padding, padding),
            background=header,
            foreground=colors.inputfg,
            relief="flat",
        )
        style.map(
            f"{self.STYLE}.Heading",
            background=[("active", stripe)],
            foreground=[("active", colors.inputfg)],
        )
        self.tag_configure(self.STRIPES[0], background=colors.inputbg)
        self.tag_configure(self.STRIPES[1], background=stripe)
        self._schedule_stripes()

    def _schedule_stripes(self):
        # Coalesce bulk reloads so striping runs once, rather than once per row.
        if self._stripe_job is None:
            self._stripe_job = self.after_idle(self._refresh_stripes)

    def _refresh_stripes(self):
        self._stripe_job = None
        for index, item in enumerate(self.get_children()):
            tags = tuple(t for t in self.item(item, "tags") if t not in self.STRIPES)
            self.item(item, tags=(*tags, self.STRIPES[index % 2]))
        self._fit_columns()

    def _fit_columns(self):
        # Fixed widths predate the larger table font. Keep text inside each cell,
        # and let the existing horizontal scrollbars handle narrower windows.
        heading_font = font.Font(
            self, font=ttk.Style().lookup(f"{self.STYLE}.Heading", "font")
        )
        columns = self.cget("columns")
        widths = [heading_font.measure(self.heading(key, "text")) for key in columns]
        for item in self.get_children():
            for index, value in enumerate(self.item(item, "values")[: len(columns)]):
                widths[index] = max(widths[index], self._body_font.measure(value))
        for key, width in zip(columns, widths):
            minimum = max(self.column(key, "minwidth"), width + 2 * self._cell_padding)
            self.column(
                key, minwidth=minimum, width=max(self.column(key, "width"), minimum)
            )

    def insert(self, parent, index, iid=None, **kwargs):
        item = super().insert(parent, index, iid=iid, **kwargs)
        self._schedule_stripes()
        return item

    def delete(self, *items):
        super().delete(*items)
        self._schedule_stripes()

    def move(self, item, parent, index):
        super().move(item, parent, index)
        self._schedule_stripes()

    def destroy(self):
        if self._stripe_job is not None:
            self.after_cancel(self._stripe_job)
            self._stripe_job = None
        super().destroy()
