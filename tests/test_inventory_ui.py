from datetime import date
from decimal import Decimal
from unittest.mock import patch

from pawpos.services import inventory_service as inventory
from pawpos.ui.owner.inventory import InventoryScreen
from tests.test_catalog_ui import owner_screen


def select_product(screen, unit="piece"):
    label, product = next(
        (label, p)
        for label, p in screen.products.items()
        if p.unit_type == unit and p.stock_quantity > 0
    )
    screen.receive_product.set(label)
    screen.adjust_product.set(label)
    screen.prefill_supplier()
    return product


def test_owner_inventory_four_tabs_receive_adjust_and_readonly_history(app):
    screen = owner_screen(app, "Inventory")
    assert isinstance(screen, InventoryScreen)
    assert len(screen.notebook.tabs()) == 4
    product = select_product(screen)
    assert screen.supplier.get() == product.supplier
    screen.receive_quantity.set("3")
    screen.supplier.set("Local supplier")
    screen.receive_note.set("Delivery")
    screen.receive_button.invoke()
    assert screen.status.get() == "Stock received."
    assert screen.receive_quantity.get() == ""
    assert screen.overview_tree.item(str(product.id), "values")[2] == str(
        int(product.stock_quantity + 3)
    )
    screen.adjust_quantity.set("-1")
    screen.reason.set("Damage")
    screen.adjust_note.set("Broken")
    screen.adjust_button.invoke()
    assert screen.status.get() == "Stock adjusted."
    row = screen.history_tree.item(screen.history_tree.get_children()[0], "values")
    assert row[2] == "adjustment" and row[3] == "-1" and row[-1] == "Damage: Broken"
    assert "read-only" in screen.history_empty.get()
    assert not screen.history_tree.bind("<Double-1>")
    assert not screen.history_tree.bind("<Delete>")
    assert len(screen.overview_tree.tag_has("low")) >= 1


def test_invalid_entry_preserves_form_and_stock(app):
    screen = owner_screen(app, "Inventory")
    product = select_product(screen)
    screen.receive_quantity.set("1.5")
    screen.receive_button.invoke()
    assert "decimal places" in screen.status.get()
    assert screen.receive_quantity.get() == "1.5"
    screen.receive_quantity.set("1")
    screen.delivery_date.set("bad")
    screen.receive_button.invoke()
    assert "YYYY-MM-DD" in screen.status.get()
    screen.adjust_quantity.set("-999999")
    screen.adjust_note.set("Loss")
    screen.adjust_button.invoke()
    assert "negative" in screen.status.get()
    assert screen.adjust_note.get() == "Loss"
    assert (
        next(p for p in inventory.stock_overview() if p.id == product.id).stock_quantity
        == product.stock_quantity
    )


def test_history_filters_empty_state_and_invalid_dates(app):
    screen = owner_screen(app, "Inventory")
    product = select_product(screen, "kg")
    screen.receive_quantity.set("0.125")
    screen.receive_button.invoke()
    screen.history_product.set(screen.receive_product.get())
    screen.history_type.set("stock_received")
    screen.date_from.set(date.today().isoformat())
    screen.date_to.set(date.today().isoformat())
    screen.refresh_history()
    rows = screen.history_tree.get_children()
    assert rows
    values = screen.history_tree.item(rows[0], "values")
    assert values[1] == product.name and values[3] == "+0.125 kg"
    screen.history_type.set("refund")
    screen.refresh_history()
    assert not screen.history_tree.get_children()
    assert "No stock movements" in screen.history_empty.get()
    screen.date_from.set("not a date")
    screen.refresh_history()
    assert "YYYY-MM-DD" in screen.status.get()
    screen.search.set("unmatched product")
    screen.refresh()
    assert not screen.overview_tree.get_children()


def test_owner_pos_refreshes_stock_after_inventory_and_preserves_cart(app):
    screen = owner_screen(app, "POS")
    # The POS is kept alive while inventory changes stock.
    original = screen
    app.screen.buttons["Inventory"].invoke()
    app.update()
    screen = app.screen.current_screen
    product = select_product(screen)
    screen.receive_quantity.set("2")
    screen.receive_button.invoke()
    app.screen.buttons["POS"].invoke()
    app.update()
    assert app.screen.current_screen is original
    assert (
        next(p for p in inventory.stock_overview() if p.id == product.id).stock_quantity
        == product.stock_quantity + 2
    )


def test_saved_stock_cannot_be_submitted_again_after_refresh_failure(app):
    screen = owner_screen(app, "Inventory")
    product = select_product(screen)
    screen.receive_quantity.set("1")
    with patch.object(screen, "_load", side_effect=RuntimeError("Read failed")):
        screen.receive_button.invoke()
    assert "Stock saved" in screen.status.get()
    assert screen.receive_quantity.get() == ""
    assert next(
        p for p in inventory.stock_overview() if p.id == product.id
    ).stock_quantity == product.stock_quantity + Decimal("1")
    screen.receive_button.invoke()
    assert next(
        p for p in inventory.stock_overview() if p.id == product.id
    ).stock_quantity == product.stock_quantity + Decimal("1")


def test_inventory_controls_fit_minimum_window(app):
    app.geometry("1280x720")
    screen = owner_screen(app, "Inventory")
    for tab, button in (
        ("Receive Stock", screen.receive_button),
        ("Adjust Stock", screen.adjust_button),
    ):
        screen.notebook.select(screen.tabs[tab])
        app.update()
        assert (
            button.winfo_rooty() + button.winfo_height()
            <= app.winfo_rooty() + app.winfo_height()
        )
    screen.notebook.select(screen.tabs["Movement History"])
    app.update()
    assert screen.history_tree.winfo_height() > 100
