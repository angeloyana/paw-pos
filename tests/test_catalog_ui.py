from decimal import Decimal
from unittest.mock import patch

from PIL import Image

from pawpos.services import auth_service, category_service, product_service
from pawpos.ui.owner import products as products_ui
from pawpos.ui.owner.categories import CategoriesScreen
from pawpos.ui.owner.products import ProductsScreen
from pawpos.ui.owner.shell import OwnerShell


def owner_screen(app, page):
    identity = auth_service.login("owner", "owner123")
    app.show_workspace(identity)
    assert isinstance(app.screen, OwnerShell)
    app.screen.buttons[page].invoke()
    app.update()
    return app.screen.current_screen


def select(app, screen, row_id):
    screen.tree.selection_set(str(row_id))
    app.update()


def test_owner_can_create_edit_deactivate_and_reactivate_category(app):
    screen = owner_screen(app, "Categories")
    assert isinstance(screen, CategoriesScreen)
    screen.name.set("Aquarium")
    screen.description.set("Fish supplies")
    screen.save_button.invoke()
    assert screen.status.get() == "Category saved."
    category = next(
        c for c in category_service.list_categories() if c.name == "Aquarium"
    )
    select(app, screen, category.id)
    screen.name.set("Aquarium care")
    screen.save_button.invoke()
    assert any(c.name == "Aquarium care" for c in category_service.list_categories())
    select(app, screen, category.id)
    with patch("pawpos.ui.owner.categories.messagebox.askyesno", return_value=True):
        screen.deactivate()
    assert "deactivated" in screen.status.get()
    assert category.id not in [c.id for c in category_service.list_categories()]
    select(app, screen, category.id)
    screen.is_active.set(True)
    screen.save_button.invoke()
    assert category.id in [c.id for c in category_service.list_categories()]


def test_category_validation_and_used_category_error_keep_form(app):
    screen = owner_screen(app, "Categories")
    screen.save_button.invoke()
    assert "required" in screen.status.get()
    category = category_service.list_categories()[0]
    select(app, screen, category.id)
    with patch("pawpos.ui.owner.categories.messagebox.askyesno", return_value=True):
        screen.deactivate()
    assert "has products" in screen.status.get()
    assert screen.name.get() == category.name
    assert category.id in [c.id for c in category_service.list_categories()]


def test_product_create_image_edit_preserves_stock_and_deactivate(
    app, tmp_path, monkeypatch
):
    store = tmp_path / "assets" / "products"
    monkeypatch.setattr(product_service, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(product_service, "PRODUCT_IMAGES_DIR", store)
    monkeypatch.setattr(products_ui, "PROJECT_ROOT", tmp_path)
    source = tmp_path / "toy.png"
    Image.new("RGB", (32, 32), "red").save(source)
    screen = owner_screen(app, "Products")
    assert isinstance(screen, ProductsScreen)
    screen.name.set("Test toy")
    screen.category.set("Toys")
    screen.price.set("12.50")
    screen.stock.set("3")
    screen.threshold.set("1")
    with patch(
        "pawpos.ui.owner.products.filedialog.askopenfilename", return_value=str(source)
    ):
        screen.choose_image()
    assert screen.image_source == str(source)
    assert screen.preview.image is not None
    screen.save_button.invoke()
    assert screen.status.get() == "Product saved."
    product = product_service.list_products("Test toy")[0]
    assert (tmp_path / product.image_path).exists()
    source.unlink()
    select(app, screen, product.id)
    assert screen.preview.image is not None
    assert str(screen.stock_entry.cget("state")) == "disabled"
    screen.name.set("Updated toy")
    screen.price.set("15.00")
    screen.stock.set("999")
    screen.save_button.invoke()
    updated = product_service.list_products("Updated toy")[0]
    assert updated.stock_quantity == Decimal("3")
    assert updated.image_path == product.image_path
    select(app, screen, product.id)
    with patch("pawpos.ui.owner.products.messagebox.askyesno", return_value=True):
        screen.deactivate()
    assert "deactivated" in screen.status.get()
    assert product_service.list_products("Updated toy") == []
    assert any(
        p.id == product.id for p in product_service.list_products(include_inactive=True)
    )


def test_product_validation_and_filters(app):
    screen = owner_screen(app, "Products")
    screen.name.set("Invalid toy")
    screen.stock.set("1.5")
    screen.save_button.invoke()
    assert "decimal places" in screen.status.get()
    assert screen.name.get() == "Invalid toy"
    screen.search.set("WHISKAS")
    screen.refresh()
    assert len(screen.records) == 1
    assert next(iter(screen.records.values())).name == "Whiskas Pouch 85g"
    screen.filter_category.set("Toys")
    screen.refresh()
    assert screen.records == {}
    screen.search.set("")
    screen.refresh()
    assert len(screen.records) == 2


def test_missing_product_image_falls_back_to_placeholder(app, tmp_path):
    screen = owner_screen(app, "Products")
    screen.show_image(tmp_path / "missing.png")
    assert screen.preview.image is not None


def test_product_form_scrolls_to_last_field_at_minimum_window_size(app):
    app.geometry("1280x720")
    screen = owner_screen(app, "Products")
    screen.status.set(
        "Validation feedback may take up additional space above the form."
    )
    app.update()
    screen.form_canvas.yview_moveto(1)
    app.update()
    note_bottom = screen.stock_note.winfo_rooty() + screen.stock_note.winfo_height()
    viewport_bottom = (
        screen.form_canvas.winfo_rooty() + screen.form_canvas.winfo_height()
    )
    assert note_bottom <= viewport_bottom


def test_category_change_appears_in_product_form_and_shell_logout(app):
    screen = owner_screen(app, "Categories")
    screen.name.set("New category")
    screen.save_button.invoke()
    app.screen.buttons["Products"].invoke()
    app.update()
    assert "New category" in app.screen.current_screen.category_ids
    app.screen.logout_button.invoke()
    app.update()
    from pawpos.core import session
    from pawpos.ui.login_screen import LoginScreen

    assert session.current_user is None
    assert isinstance(app.screen, LoginScreen)
