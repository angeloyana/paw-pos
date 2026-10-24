import tkinter as tk
from decimal import Decimal
from unittest.mock import patch

from PIL import Image
from sqlalchemy import func, select

from pawpos.models import Sale, StockMovement
from pawpos.services import auth_service, product_service
from pawpos.ui.dialogs.customer_picker import CustomerPicker
from pawpos.ui.dialogs.held_list import HeldListDialog
from pawpos.ui.dialogs.weight import WeightDialog
from pawpos.ui.pos_screen import POSScreen
from pawpos.ui.widgets.product_card import ThumbnailCache


def cashier_pos(app):
    user = auth_service.login("cashier", "cashier123")
    app.show_workspace(user)
    app.update()
    return app.screen


def by_name(screen, name):
    return next(row for row in screen.products.values() if row.name == name)


def test_product_grid_cart_weight_edit_remove_and_no_stock_writes(app, session_factory):
    screen = cashier_pos(app)
    toy = by_name(screen, "Rubber Chew Toy")
    food = by_name(screen, "Dog Food Loose (Adult)")
    with session_factory() as session:
        movements = session.scalar(select(func.count()).select_from(StockMovement))
    screen.cards[toy.id].button.invoke()
    screen.cards[toy.id].button.invoke()
    assert screen.cart.lines[0].quantity == 2
    with patch.object(WeightDialog, "show", return_value=Decimal("1.375")):
        screen.cards[food.id].button.invoke()
    assert screen.cart.total == Decimal("430.63")
    assert screen.total_text.get() == "₱430.63"
    assert screen.table.item(str(food.id), "values")[1] == "1.375 kg"
    screen.table.selection_set(str(toy.id))
    with patch.object(WeightDialog, "show", return_value=Decimal("3")):
        screen.edit_selected()
    assert screen.cart.total == Decimal("580.63")
    screen.table.focus_force()
    app.update()
    screen.table.event_generate("<Delete>")
    app.update()
    assert [line.product_id for line in screen.cart.lines] == [food.id]
    with session_factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(StockMovement)) == movements
        )
        assert session.scalar(select(func.count()).select_from(Sale)) == 0


def test_filters_empty_state_out_of_stock_and_piece_stock_cap(app):
    screen = cashier_pos(app)
    empty = by_name(screen, "Flea and Tick Spray")
    assert str(screen.cards[empty.id].button.cget("state")) == "disabled"
    screen.cards[empty.id].button.invoke()
    assert screen.cart.lines == ()
    toy = by_name(screen, "Cat Feather Wand")
    screen.choose_category(toy.category_id)
    assert all(row.category_id == toy.category_id for row in screen.products.values())
    screen.search.set("FEATHER")
    assert list(screen.products) == [toy.id]
    for _ in range(4):
        screen.add_product(toy.id)
    assert screen.cart.lines[0].quantity == 3
    assert "Not enough stock" in screen.status.get()
    screen.search.set("no matching product")
    assert screen.cards == {}
    assert "No products" in screen.grid_frame.winfo_children()[0].cget("text")
    assert screen.cart.lines[0].quantity == 3


def test_disabled_payment_empty_cart_cancel_and_generic_errors(app):
    screen = cashier_pos(app)
    assert str(screen.pay_button.cget("state")) == "disabled"
    food = by_name(screen, "Dog Food Loose (Adult)")
    with patch.object(WeightDialog, "show", return_value=None):
        screen.add_product(food.id)
    assert screen.cart.lines == ()
    with patch.object(
        product_service, "list_products", side_effect=RuntimeError("private detail")
    ):
        screen.add_product(food.id)
    assert "Cannot complete" in screen.status.get()
    assert "private detail" not in screen.status.get()
    screen.remove_selected()
    assert "Select a cart line" in screen.status.get()


def test_weight_dialog_live_price_validation_and_merge_stock(app):
    cashier_pos(app)
    dialog = WeightDialog(app, "Food", Decimal("95"), "kg", Decimal("2"))
    for value in ("0", "-1", "1.0001", "NaN", "2.001"):
        dialog.value.set(value)
        assert str(dialog.confirm_button.cget("state")) == "disabled"
        assert dialog.error.get()
    dialog.value.set("1.375")
    assert dialog.preview.get() == "Line total: ₱130.63"
    dialog.confirm()
    assert dialog.result == Decimal("1.375")
    merged = WeightDialog(
        app,
        "Food",
        Decimal("95"),
        "kg",
        Decimal("2"),
        existing_quantity=Decimal("1.375"),
    )
    merged.value.set("0.626")
    assert "stock" in merged.error.get()
    merged.value.set("0.625")
    assert merged.preview.get() == "Line total: ₱190.00"
    merged.destroy()
    piece = WeightDialog(app, "Toy", Decimal("150"), "piece", Decimal("3"), initial="1")
    piece.value.set("1.5")
    assert str(piece.confirm_button.cget("state")) == "disabled"
    piece.destroy()


def test_customer_picker_quick_add_search_selection_cancel_and_walk_in(app):
    screen = cashier_pos(app)
    picker = CustomerPicker(app)
    picker.create()
    assert "Name is required" in picker.error.get()
    picker.name.set("Ana")
    picker.contact.set("0917")
    picker.create()
    customer = picker.result
    with patch.object(CustomerPicker, "show", return_value=customer):
        screen.select_customer()
    assert screen.customer == customer
    assert screen.customer_text.get() == "Ana"
    picker = CustomerPicker(app)
    picker.search.set("917")
    assert picker.table.get_children() == (str(customer.id),)
    picker.table.selection_set(str(customer.id))
    picker.select()
    assert picker.result == customer
    with patch.object(CustomerPicker, "show", return_value=None):
        screen.select_customer()
    assert screen.customer == customer
    with patch.object(CustomerPicker, "show", return_value=False):
        screen.select_customer()
    assert screen.customer is None
    assert screen.customer_text.get() == "Walk-in"


def test_pos_shortcuts_modal_scope_and_cleanup(app):
    screen = cashier_pos(app)
    screen.table.focus_force()
    app.update()
    app.event_generate("<F2>")
    app.update()
    assert app.focus_get() == screen.search_entry
    for key, message in (
        ("F4", "cart is empty"),
        ("F5", "cart is empty"),
        ("F6", "cart is empty"),
    ):
        app.event_generate(f"<{key}>")
        app.update()
        assert message in screen.status.get()
    with patch.object(
        HeldListDialog,
        "show",
        autospec=True,
        side_effect=lambda dialog: dialog.destroy(),
    ) as show:
        app.event_generate("<F8>")
        app.update()
        show.assert_called_once()
    dialog = WeightDialog(app, "Food", Decimal("95"), "kg", Decimal("2"))
    dialog.deiconify()
    dialog.first_input.focus_force()
    app.update()
    screen.status.set("unchanged")
    dialog.event_generate("<F5>")
    app.update()
    assert screen.status.get() == "unchanged"
    dialog.destroy()
    screen.logout_button.invoke()
    app.update()
    assert not app.bind("<F2>")
    assert not app.bind("<F8>")


def test_owner_pos_navigation_preserves_cart_and_scopes_shortcuts(app):
    app.show_workspace(auth_service.login("owner", "owner123"))
    shell = app.screen
    shell.buttons["POS"].invoke()
    app.update()
    screen = shell.current_screen
    assert isinstance(screen, POSScreen)
    toy = by_name(screen, "Rubber Chew Toy")
    screen.add_product(toy.id)
    shell.buttons["Products"].invoke()
    app.update()
    screen.status.set("hidden")
    shell.buttons["Products"].focus_force()
    app.event_generate("<F5>")
    app.update()
    assert screen.status.get() == "hidden"
    shell.buttons["POS"].invoke()
    app.update()
    assert shell.current_screen is screen
    assert screen.cart.lines[0].product_id == toy.id


def test_modal_show_enter_and_escape(app):
    cashier_pos(app)
    dialog = WeightDialog(
        app, "Food", Decimal("95"), "kg", Decimal("2"), initial="1.375"
    )
    dialog.after(100, lambda: dialog.event_generate("<Return>"))
    assert dialog.show() == Decimal("1.375")
    dialog = CustomerPicker(app)
    dialog.after(100, lambda: dialog.event_generate("<Escape>"))
    assert dialog.show() is None
    assert app.grab_current() is None


def test_deactivated_product_is_blocked_and_removed_on_refresh(app):
    screen = cashier_pos(app)
    toy = by_name(screen, "Rubber Chew Toy")
    auth_service.login("owner", "owner123")
    product_service.deactivate_product(toy.id)
    auth_service.login("cashier", "cashier123")
    screen.add_product(toy.id)
    assert screen.cart.lines == ()
    assert "no longer available" in screen.status.get()
    screen.refresh_products()
    assert toy.id not in screen.cards


def test_owner_pos_controls_fit_minimum_window(app):
    app.state("normal")
    try:
        app.attributes("-zoomed", False)
    except tk.TclError:
        pass  # Windows uses state("normal") without the X11 zoomed attribute.
    app.geometry("1280x720")
    app.show_workspace(auth_service.login("owner", "owner123"))
    app.screen.show_page("POS")
    app.update()
    screen = app.screen.current_screen
    assert (
        screen.pay_button.winfo_rooty() + screen.pay_button.winfo_height()
        <= app.winfo_rooty() + app.winfo_height()
    )
    assert (
        screen.pay_button.winfo_rootx() + screen.pay_button.winfo_width()
        <= app.winfo_rootx() + app.winfo_width()
    )
    assert screen.canvas.winfo_width() >= 400


def test_thumbnail_cache_loads_image_and_handles_missing_or_corrupt_images(
    app, tmp_path
):
    cache = ThumbnailCache(app)
    path = tmp_path / "product.png"
    Image.new("RGB", (200, 100), "red").save(path)
    photo = cache.get(str(path))
    assert photo.width() == 96 and photo.height() == 48
    assert cache.get(str(path)) is photo
    assert cache.get("missing.png").width() == 96
    path.write_text("corrupt image")
    assert ThumbnailCache(app).get(str(path)).width() == 96
