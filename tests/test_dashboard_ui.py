from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from pawpos.services import (
    auth_service,
    inventory_service,
    product_service,
    refund_service,
    report_service,
    sale_service,
)
from pawpos.services.cart import Cart
from pawpos.services.refund_service import RefundLineInput
from pawpos.services.sale_service import Payment
from pawpos.ui.owner.dashboard import DashboardScreen
from tests.test_catalog_ui import owner_screen
from tests.test_refund_ui import sale


def test_owner_default_dashboard_renders_seed_summary_empty_charts_and_low_stock(app):
    app.show_workspace(auth_service.login("owner", "owner123"))
    app.update()
    screen = app.screen.current_screen
    assert isinstance(screen, DashboardScreen)
    assert {key: value.get() for key, value in screen.values.items()} == {
        "net_sales": "₱0.00",
        "transactions": "0",
        "low_stock": "2",
        "pending_refunds": "0",
    }
    assert len(screen.daily_chart.axes.patches) == 7
    assert (
        screen.daily_chart.axes.yaxis.get_major_formatter()(Decimal("0.50")) == "₱0.50"
    )
    assert any("No sales" in text.get_text() for text in screen.daily_chart.axes.texts)
    assert any(
        "No completed sales" in text.get_text() for text in screen.best_chart.axes.texts
    )
    assert len(screen.low_tree.get_children()) == 2
    assert "approval date" in screen.status.get()


def test_sales_refunds_pending_cards_and_quantity_chart(app):
    completed, _, _ = sale(app)
    lines = refund_service.lookup_receipt(completed.receipt_number).items
    toy = next(line for line in lines if line.unit_type == "piece")
    food = next(line for line in lines if line.unit_type == "kg")
    request = refund_service.create_request(
        completed.receipt_number, [RefundLineInput(toy.id, 1)], "Return"
    )
    auth_service.login("owner", "owner123")
    refund_service.approve(request.id, {request.items[0].id: False})
    refund_service.create_request(
        completed.receipt_number, [RefundLineInput(food.id, "0.5")], "Pending"
    )
    screen = owner_screen(app, "Dashboard")
    assert screen.values["net_sales"].get() == "₱280.63"
    assert screen.values["transactions"].get() == "1"
    assert screen.values["pending_refunds"].get() == "1"
    assert app.screen.buttons["Refunds"].cget("text") == "Refunds (1)"
    labels = [text.get_text() for text in screen.best_chart.axes.get_yticklabels()]
    assert any("piece" in label for label in labels) and any(
        "kg" in label for label in labels
    )
    assert [text.get_text() for text in screen.best_chart.axes.texts] == [
        "2",
        "1.375 kg",
    ]


def test_chart_range_selectors_redraw_existing_canvases(app):
    _, toy, _ = sale(app)
    auth_service.login("owner", "owner123")
    product = next(p for p in product_service.list_products() if p.id == toy.id)
    cart = Cart()
    cart.add_piece(
        product.id,
        product.name,
        product.unit_price,
        stock_quantity=product.stock_quantity,
    )
    with patch.object(sale_service, "datetime") as clock:
        clock.now.return_value = datetime.now() - timedelta(days=20)
        sale_service.complete_sale(cart, Payment("cash", 500))
    screen = owner_screen(app, "Dashboard")
    daily_canvas, best_canvas = screen.daily_chart.canvas, screen.best_chart.canvas
    screen.daily_range.set("30 days")
    screen.daily_selector.event_generate("<<ComboboxSelected>>")
    app.update()
    assert len(screen.daily_chart.axes.patches) == 30
    screen.best_range.set("Today")
    screen.best_selector.event_generate("<<ComboboxSelected>>")
    app.update()
    assert screen.best_chart.axes.patches[0].get_width() == 2
    screen.best_range.set("30 days")
    screen.best_selector.event_generate("<<ComboboxSelected>>")
    app.update()
    assert screen.best_chart.axes.patches[0].get_width() == 3
    assert (
        screen.daily_chart.canvas is daily_canvas
        and screen.best_chart.canvas is best_canvas
    )


def test_receiving_stock_and_navigation_refresh_dashboard_without_losing_cart(app):
    screen = owner_screen(app, "POS")
    product = next(p for p in screen.products.values() if p.name == "Cat Feather Wand")
    screen.add_product(product.id)
    before = screen.cart.lines
    app.screen.buttons["Dashboard"].invoke()
    app.update()
    dashboard = app.screen.current_screen
    assert str(product.id) in dashboard.low_tree.get_children()
    inventory_service.receive_stock(product.id, 3)
    dashboard.refresh_button.invoke()
    assert str(product.id) not in dashboard.low_tree.get_children()
    assert dashboard.values["low_stock"].get() == "1"
    app.screen.buttons["POS"].invoke()
    app.update()
    assert app.screen.current_screen is screen and screen.cart.lines == before
    app.screen.buttons["Dashboard"].invoke()
    app.update()
    assert app.screen.current_screen.values["low_stock"].get() == "1"


def test_dashboard_read_failure_preserves_visible_data_and_refresh_recovers(app):
    screen = owner_screen(app, "Dashboard")
    before = {key: value.get() for key, value in screen.values.items()}
    rows_before = screen.low_tree.get_children()
    with patch.object(
        report_service, "low_stock", side_effect=RuntimeError("Read failed")
    ):
        screen.refresh_button.invoke()
    assert "Cannot refresh" in screen.status.get()
    assert {key: value.get() for key, value in screen.values.items()} == before
    assert screen.low_tree.get_children() == rows_before
    screen.refresh_button.invoke()
    assert screen.status.get().startswith("Updated")


def test_negative_net_sales_and_empty_low_stock_render(app):
    screen = owner_screen(app, "Dashboard")
    rows = report_service.daily_sales()
    from dataclasses import replace

    rows[-1] = replace(
        rows[-1], approved_refunds=Decimal("10.00"), net_sales=Decimal("-10.00")
    )
    screen.daily_chart.draw_daily(rows)
    app.update()
    assert screen.daily_chart.axes.patches[-1].get_height() == -10
    for product in report_service.low_stock():
        inventory_service.receive_stock(
            product.id, product.low_stock_threshold - product.stock_quantity + 1
        )
    screen.refresh_button.invoke()
    assert (
        screen.low_tree.get_children() == () and screen.values["low_stock"].get() == "0"
    )
    assert "No active products" in screen.low_message.get()


def test_dashboard_fits_minimum_window_and_repeated_navigation_cleans_canvases(app):
    app.geometry("1280x720")
    screen = owner_screen(app, "Dashboard")
    app.update()
    assert (
        screen.low_tree.winfo_rooty() + screen.low_tree.winfo_height()
        <= app.winfo_rooty() + app.winfo_height()
    )
    assert screen.daily_chart.canvas.get_tk_widget().winfo_height() >= 160
    old_canvas = screen.daily_chart.canvas.get_tk_widget()
    for _ in range(3):
        app.screen.buttons["Customers"].invoke()
        app.update()
        app.screen.buttons["Dashboard"].invoke()
        app.update()
    assert not old_canvas.winfo_exists()
    assert len(app.screen.content.winfo_children()) == 1
