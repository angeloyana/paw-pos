"""Reusable Matplotlib canvas that follows the active account theme."""

from textwrap import fill

import ttkbootstrap as ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator, StrMethodFormatter

from pawpos.core.money import format_peso


class ChartFrame(ttk.Frame):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        ttk.Label(self, text=title, font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        self.colors = ttk.Style().colors
        self._last_draw = None
        # Own the Figure directly; pyplot's global registry would retain old screens.
        self.figure = Figure(
            figsize=(4.8, 2.6), dpi=100, layout="constrained", facecolor=self.colors.bg
        )
        self.axes = self.figure.add_subplot()
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")

    def _style(self, *, horizontal=False):
        self.colors = ttk.Style().colors
        self.figure.set_facecolor(self.colors.bg)
        self.axes.clear()
        self.axes.set_facecolor(self.colors.bg)
        self.axes.tick_params(colors=self.colors.fg, labelsize=8)
        self.axes.set_axisbelow(True)
        self.axes.grid(
            axis="x" if horizontal else "y", color=self.colors.border, alpha=0.5
        )
        for side in ("top", "right"):
            self.axes.spines[side].set_visible(False)
        for side in ("bottom", "left"):
            self.axes.spines[side].set_color(self.colors.border)
        self.axes.xaxis.label.set_color(self.colors.fg)
        self.axes.yaxis.label.set_color(self.colors.fg)

    def draw_daily(self, rows):
        self._last_draw = (self.draw_daily, rows)
        self._style()
        # Pass Decimal values through; Matplotlib converts only its rendering coordinates.
        self.axes.bar(
            range(len(rows)),
            [row.net_sales for row in rows],
            color=[
                self.colors.danger if row.net_sales < 0 else self.colors.primary
                for row in rows
            ],
        )
        step = 1 if len(rows) <= 7 else 5
        ticks = list(range(0, len(rows), step))
        if rows and ticks[-1] != len(rows) - 1:
            ticks.append(len(rows) - 1)
        self.axes.set_xticks(
            ticks,
            [rows[index].day.strftime("%b %d") for index in ticks],
            rotation=30,
            ha="right",
        )
        self.axes.yaxis.set_major_formatter(StrMethodFormatter("₱{x:,.2f}"))
        self.axes.yaxis.set_major_locator(MaxNLocator(nbins=5))
        self.axes.axhline(0, color=self.colors.secondary, linewidth=0.7)
        if not any(row.transactions or row.approved_refunds for row in rows):
            self.axes.text(
                0.5,
                0.5,
                "No sales or approved refunds\nin this range.",
                transform=self.axes.transAxes,
                ha="center",
                va="center",
                color=self.colors.fg,
            )
        self.canvas.draw_idle()

    def draw_best_sellers(self, rows):
        self._last_draw = (self.draw_best_sellers, rows)
        self._style(horizontal=True)
        if rows:
            bars = self.axes.barh(
                range(len(rows)),
                [row.net_revenue for row in rows],
                color=[
                    self.colors.danger if row.net_revenue < 0 else self.colors.primary
                    for row in rows
                ],
            )
            self.axes.set_yticks(
                range(len(rows)),
                [f"{fill(row.product_name, 20)} ({row.unit_type})" for row in rows],
            )
            self.axes.invert_yaxis()
            self.axes.bar_label(
                bars,
                labels=[format_peso(row.net_revenue) for row in rows],
                padding=3,
                fontsize=8,
                color=self.colors.fg,
            )
            self.axes.margins(x=0.25)
        else:
            self.axes.set_yticks([])
            self.axes.text(
                0.5,
                0.5,
                "No completed sales or approved refunds\nin this range.",
                transform=self.axes.transAxes,
                ha="center",
                va="center",
                color=self.colors.fg,
            )
        self.axes.xaxis.set_major_locator(MaxNLocator(nbins=4))
        self.axes.xaxis.set_major_formatter(StrMethodFormatter("₱{x:,.2f}"))
        self.axes.axvline(0, color=self.colors.secondary, linewidth=0.7)
        self.axes.set_xlabel("Net revenue (₱)", fontsize=8)
        self.canvas.draw_idle()

    def refresh_theme(self):
        if self._last_draw is not None:
            draw, rows = self._last_draw
            draw(rows)

    def destroy(self):
        self._last_draw = None
        # Cancel queued Tk draws before destroying the canvas during navigation/logout.
        for name in ("_idle_draw_id", "_event_loop_id"):
            callback = getattr(self.canvas, name, None)
            if callback is not None:
                self.canvas.get_tk_widget().after_cancel(callback)
                setattr(self.canvas, name, None)
        self.figure.clear()
        super().destroy()
