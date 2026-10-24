"""Owner sales summary, selectable charts, and low-stock products."""

import logging
import tkinter as tk
from datetime import datetime

import ttkbootstrap as ttk

from pawpos.core.errors import PawPOSError
from pawpos.core.money import format_peso, format_qty
from pawpos.services import report_service
from pawpos.ui.widgets.chart_frame import ChartFrame
from pawpos.ui.widgets.table import TableView

logger = logging.getLogger(__name__)


class DashboardScreen(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=16)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=3, minsize=250)
        self.rowconfigure(4, weight=2, minsize=160)
        self.status = tk.StringVar(self)
        self.daily_range = tk.StringVar(self, value="7 days")
        self.best_range = tk.StringVar(self, value="7 days")
        self.values = {
            key: tk.StringVar(self, value="—")
            for key in ("net_sales", "transactions", "low_stock", "pending_refunds")
        }
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Owner dashboard", font=("Segoe UI", 20, "bold")).pack(
            side="left"
        )
        self.refresh_button = ttk.Button(header, text="Refresh", command=self.refresh)
        self.refresh_button.pack(side="right")
        self.status_label = ttk.Label(self, textvariable=self.status, wraplength=950)
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(8, 12))
        cards = ttk.Frame(self)
        cards.grid(row=2, column=0, sticky="ew")
        for index, (key, title) in enumerate(
            (
                ("net_sales", "Today's net sales"),
                ("transactions", "Today's transactions"),
                ("low_stock", "Low-stock items"),
                ("pending_refunds", "Pending refunds"),
            )
        ):
            cards.columnconfigure(index, weight=1, uniform="cards")
            card = ttk.Frame(cards, padding=12, bootstyle="light")
            card.grid(
                row=0, column=index, sticky="nsew", padx=(0, 8) if index < 3 else 0
            )
            ttk.Label(card, text=title, bootstyle="inverse-light").pack(anchor="w")
            ttk.Label(
                card,
                textvariable=self.values[key],
                font=("Segoe UI", 20, "bold"),
                bootstyle="inverse-light",
            ).pack(anchor="w", pady=(4, 0))
        charts = ttk.Frame(self)
        charts.grid(row=3, column=0, sticky="nsew", pady=12)
        charts.columnconfigure((0, 1), weight=1, uniform="charts")
        charts.rowconfigure(1, weight=1)
        for column, label, variable, values in (
            (0, "Sales range", self.daily_range, ("7 days", "30 days")),
            (
                1,
                "Best-seller range",
                self.best_range,
                ("Today", "7 days", "30 days"),
            ),
        ):
            tools = ttk.Frame(charts)
            tools.grid(
                row=0, column=column, sticky="ew", padx=(0, 12) if column == 0 else 0
            )
            ttk.Label(tools, text=label).pack(side="left")
            combo = ttk.Combobox(
                tools, textvariable=variable, values=values, state="readonly", width=8
            )
            combo.pack(side="right")
            combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
            if column == 0:
                self.daily_selector = combo
            else:
                self.best_selector = combo
        self.daily_chart = ChartFrame(charts, "Daily net sales")
        self.daily_chart.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        self.best_chart = ChartFrame(charts, "Top 5 products")
        self.best_chart.grid(row=1, column=1, sticky="nsew")
        low = ttk.Frame(self)
        low.grid(row=4, column=0, sticky="nsew")
        low.columnconfigure(0, weight=1)
        low.rowconfigure(1, weight=1)
        self.low_message = tk.StringVar(self, value="Low stock")
        ttk.Label(
            low, textvariable=self.low_message, font=("Segoe UI", 12, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.low_tree = TableView(
            low,
            columns=("name", "category", "stock", "threshold"),
            show="headings",
            height=4,
        )
        for key, title, width in (
            ("name", "Product", 280),
            ("category", "Category", 200),
            ("stock", "Stock", 120),
            ("threshold", "Threshold", 120),
        ):
            self.low_tree.heading(key, text=title)
            self.low_tree.column(
                key,
                width=width,
                minwidth=65,
                anchor="e" if key in ("stock", "threshold") else "w",
            )
        self.low_tree.grid(row=1, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(low, command=self.low_tree.yview)
        vertical.grid(row=1, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(
            low, orient="horizontal", command=self.low_tree.xview
        )
        horizontal.grid(row=2, column=0, sticky="ew")
        self.low_tree.configure(
            yscrollcommand=vertical.set, xscrollcommand=horizontal.set
        )
        self.refresh()

    def refresh(self):
        try:
            summary = report_service.today_summary()
            daily = report_service.daily_sales(
                {"7 days": 7, "30 days": 30}[self.daily_range.get()]
            )
            best = report_service.best_sellers(
                {"Today": 1, "7 days": 7, "30 days": 30}[self.best_range.get()]
            )
            low = report_service.low_stock()
            # Fetch every report before replacing visible data, preserving it on read failure.
            self.values["net_sales"].set(format_peso(summary.net_sales))
            self.values["transactions"].set(str(summary.transactions))
            self.values["low_stock"].set(str(summary.low_stock_count))
            self.values["pending_refunds"].set(str(summary.pending_refunds))
            self.daily_chart.draw_daily(daily)
            self.best_chart.draw_best_sellers(best)
            self.low_tree.delete(*self.low_tree.get_children())
            for product in low:
                self.low_tree.insert(
                    "",
                    "end",
                    iid=str(product.id),
                    values=(
                        product.name,
                        product.category_name,
                        format_qty(product.stock_quantity, product.unit_type),
                        format_qty(product.low_stock_threshold, product.unit_type),
                    ),
                )
            self.low_message.set(
                "Low stock — active products at or below threshold"
                if low
                else "No active products are low on stock."
            )
            self.status.set(
                f"Updated {datetime.now():%H:%M:%S}. Net sales deduct refunds on their approval date."
            )
            self.status_label.configure(bootstyle="secondary")
        except PawPOSError as error:
            self.status.set(str(error))
            self.status_label.configure(bootstyle="danger")
        except Exception:
            logger.exception("Dashboard refresh failed")
            self.status.set("Cannot refresh the dashboard. Please try Refresh again.")
            self.status_label.configure(bootstyle="danger")
