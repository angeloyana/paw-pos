from unittest.mock import patch

from pawpos.services import (
    customer_service,
    product_service,
    sale_service,
)
from pawpos.services.cart import Cart
from pawpos.services.sale_service import Payment
from tests.test_catalog_ui import owner_screen, select


def test_customer_add_edit_search_and_no_delete(app):
    screen = owner_screen(app, "Customers")
    screen.name.set(" Ana Cruz ")
    screen.contact.set("0917")
    screen.save_button.invoke()
    assert screen.status.get() == "Customer saved."
    customer = customer_service.list_customers("0917")[0]
    select(app, screen, customer.id)
    assert "No completed purchases" in screen.purchase_message.get()
    screen.name.set("Ana Santos")
    screen.contact.set("")
    screen.save_button.invoke()
    assert customer_service.list_customers("Santos")[0].contact == ""
    screen.search.set("SANTOS")
    screen.refresh()
    assert len(screen.tree.get_children()) == 1
    screen.search.set("not found")
    screen.refresh()
    assert screen.tree.get_children() == ()
    assert "No customers match" in screen.purchase_message.get()
    assert not screen.tree.bind("<Delete>")


def test_customer_validation_and_failed_write_preserve_form(app):
    screen = owner_screen(app, "Customers")
    screen.contact.set("Keep contact")
    screen.save_button.invoke()
    assert "required" in screen.status.get()
    assert screen.contact.get() == "Keep contact"
    screen.name.set("New customer")
    with patch.object(
        customer_service, "create_customer", side_effect=RuntimeError("Write failed")
    ):
        screen.save_button.invoke()
    assert (
        screen.name.get() == "New customer" and screen.contact.get() == "Keep contact"
    )
    assert customer_service.list_customers() == []


def test_selected_customer_completed_purchases_and_links_survive_edit(app):
    screen = owner_screen(app, "Customers")
    first = customer_service.create_customer("Ana")
    second = customer_service.create_customer("Ben")
    product = next(
        p
        for p in product_service.list_products()
        if p.unit_type == "piece" and p.stock_quantity > 2
    )
    cart = Cart()
    cart.add_piece(
        product.id,
        product.name,
        product.unit_price,
        stock_quantity=product.stock_quantity,
    )
    completed = sale_service.complete_sale(
        cart, Payment("cash", 1000), customer_id=first.id
    )
    sale_service.complete_sale(cart, Payment("cash", 1000), customer_id=second.id)
    sale_service.hold_cart(cart, customer_id=first.id)
    screen.refresh()
    select(app, screen, first.id)
    assert screen.purchases_tree.get_children() == (str(completed.id),)
    screen.name.set("Ana Updated")
    screen.save_button.invoke()
    select(app, screen, first.id)
    assert "Ana Updated" in screen.purchase_message.get()
    assert (
        screen.purchases_tree.item(str(completed.id), "values")[0]
        == completed.receipt_number
    )
    app.screen.buttons["POS"].invoke()
    app.update()
    assert customer_service.list_customers("Updated")[0].id == first.id


def test_saved_customer_refresh_failure_clears_form_before_retry(app):
    screen = owner_screen(app, "Customers")
    screen.name.set("Saved once")
    with patch.object(screen, "_load", side_effect=RuntimeError("Read failed")):
        screen.save_button.invoke()
    assert "Customer saved" in screen.status.get()
    assert screen.name.get() == ""
    screen.save_button.invoke()
    assert len(customer_service.list_customers()) == 1


def test_customer_layout_at_minimum_window_size(app):
    app.geometry("1280x720")
    screen = owner_screen(app, "Customers")
    app.update()
    assert (
        screen.purchases_tree.winfo_rooty() + screen.purchases_tree.winfo_height()
        <= app.winfo_rooty() + app.winfo_height()
    )
    assert screen.tree.winfo_height() > 100
