import tkinter as tk
from datetime import date
from unittest.mock import patch

import pytest
import ttkbootstrap as ttk

from pawpos.services import (
    customer_service,
    inventory_service,
    sales_history_service,
    void_history_service,
)
from pawpos.services import refund_tracking_service as tracking
from pawpos.ui.dialogs.refund_status import RefundStatusDialog
from pawpos.ui.widgets.auto_filter import AutoFilter
from tests.test_catalog_ui import owner_screen


def settle(app):
    finished = tk.BooleanVar(app)
    app.after(350, lambda: finished.set(True))
    app.wait_variable(finished)


@pytest.mark.parametrize(
    "page,service,method,attribute,values",
    [
        (
            "Sales History",
            sales_history_service,
            "list_sales",
            "receipt_number",
            ("a", "ab"),
        ),
        ("Customers", customer_service, "list_customers", "search", ("a", "ab")),
        ("Inventory", inventory_service, "stock_overview", "search", ("a", "ab")),
    ],
)
def test_text_filters_debounce_and_manual_refresh_cancels(
    app, page, service, method, attribute, values
):
    screen = owner_screen(app, page)
    variable = getattr(screen, attribute)
    with patch.object(service, method, wraps=getattr(service, method)) as query:
        for value in values:
            variable.set(value)
            app.update()
        query.assert_not_called()
        settle(app)
        assert query.call_count == 1
        variable.set("latest")
        screen.refresh()
        assert query.call_count == 2
        settle(app)
        assert query.call_count == 2
    assert variable.get() == "latest"
    if attribute == "receipt_number":
        assert query.call_args.kwargs["receipt_number"] == "latest"
    elif page == "Customers":
        assert query.call_args.args == ("latest",)


def test_customer_search_keeps_focus_and_filters_rows(app):
    screen = owner_screen(app, "Customers")
    customer_service.create_customer("Matching customer")
    customer_service.create_customer("Other customer")
    entry = next(w for w in screen.toolbar.winfo_children() if isinstance(w, ttk.Entry))
    entry.focus_force()
    app.update()
    screen.search.set("Matching")
    entry.icursor("end")
    settle(app)
    assert app.focus_get() == entry
    assert entry.index("insert") == len("Matching")
    assert len(screen.records) == 1
    assert next(iter(screen.records.values())).name == "Matching customer"


@pytest.mark.parametrize("page", ["Sales History", "Inventory", "Void History"])
def test_history_dates_apply_clear_cancel_and_validate(app, page):
    screen = owner_screen(app, page)
    service, method = {
        "Sales History": (sales_history_service, "list_sales"),
        "Inventory": (inventory_service, "list_movements"),
        "Void History": (void_history_service, "list_voids"),
    }[page]
    pickers = (
        screen.history_date_pickers if page == "Inventory" else screen.date_pickers
    )
    with patch.object(service, method, wraps=getattr(service, method)) as query:
        screen.date_from.set("2026-10-25")
        app.update()
        assert query.call_args.kwargs["date_from"] == date(2026, 10, 25)
        pickers[0].clear_button.invoke()
        app.update()
        assert query.call_args.kwargs["date_from"] is None
        count = query.call_count
        with patch("pawpos.ui.widgets.date_picker._CalendarDialog") as calendar:
            calendar.return_value.selection = None
            pickers[0].open_calendar()
        app.update()
        assert query.call_count == count
    screen.date_from.set("2026-10-27")
    screen.date_to.set("2026-10-26")
    app.update()
    assert "must not be after" in screen.status.get()


def test_sales_and_movement_dropdowns_apply_combined_filters(app):
    sales = owner_screen(app, "Sales History")
    with patch.object(sales_history_service, "list_sales", return_value=[]) as query:
        sales.method.set("GCash")
        sales.cashier.set(next(iter(sales.cashiers)))
        app.update()
        query.assert_called_once()
        assert query.call_args.kwargs["payment_method"] == "gcash"
        assert query.call_args.kwargs["cashier_id"] is not None
    screen = owner_screen(app, "Inventory")
    with patch.object(inventory_service, "list_movements", return_value=[]) as query:
        screen.history_product.set(next(iter(screen.products)))
        screen.history_type.set("sale")
        app.update()
        query.assert_called_once()
        assert query.call_args.kwargs["product_id"] is not None


def test_refund_filters_automatically_reload_and_retain_retry(app):
    parent = owner_screen(app, "Customers")
    dialog = RefundStatusDialog(parent, owner=True)
    with patch.object(tracking, "list_refunds", return_value=[]) as query:
        dialog.receipt.set("receipt")
        dialog.filter.set("Unread decisions")
        app.update()
        query.assert_called_once_with("receipt", "all")
        settle(app)
        query.assert_called_once()
        dialog.refresh_button.invoke()
        assert query.call_count == 2
    dialog.destroy()


def test_automatic_reload_failure_keeps_rows_and_refresh_retries(app):
    screen = owner_screen(app, "Customers")
    customer = customer_service.create_customer("Matching customer")
    screen.refresh()
    before = screen.tree.get_children()
    with patch.object(
        customer_service, "list_customers", side_effect=RuntimeError("private")
    ):
        screen.search.set("Matching")
        settle(app)
    assert screen.tree.get_children() == before
    assert "Cannot complete" in screen.status.get()
    assert "private" not in screen.status.get()
    screen.refresh()
    assert screen.tree.get_children() == (str(customer.id),)


def test_destroy_removes_pending_callbacks_and_variable_traces(app):
    frame = ttk.Frame(app)
    variable = tk.StringVar(app)
    calls = []
    helper = AutoFilter(frame, lambda: calls.append(True), text=(variable,))
    variable.set("pending")
    frame.destroy()
    assert helper.pending is None
    assert variable.trace_info() == []
    variable.set("after destruction")
    settle(app)
    assert calls == []
