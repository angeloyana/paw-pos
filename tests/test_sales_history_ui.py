from datetime import date, timedelta
from unittest.mock import patch

from sqlalchemy import func, select

from pawpos.models import Sale, StockMovement
from pawpos.services import (
    auth_service,
    customer_service,
    product_service,
    receipt_service,
    refund_service,
    sale_service,
)
from pawpos.services.cart import Cart
from pawpos.services.refund_service import RefundLineInput
from pawpos.services.sale_service import Payment
from tests.test_catalog_ui import owner_screen
from tests.test_catalog_ui import select as select_row


def make_sales(app):
    auth_service.login("owner", "owner123")
    customer = customer_service.create_customer("Ana Cruz", "0917")
    product = next(
        p for p in product_service.list_products() if p.name == "Rubber Chew Toy"
    )
    cart = Cart()
    cart.add_piece(
        product.id,
        product.name,
        product.unit_price,
        2,
        stock_quantity=product.stock_quantity,
    )
    first = sale_service.complete_sale(
        cart, Payment("cash", 500), customer_id=customer.id
    )
    auth_service.login("cashier", "cashier123")
    second = sale_service.complete_sale(
        cart, Payment("gcash", gcash_reference="REF-SALES")
    )
    sale_service.hold_cart(cart)
    return first, second


def test_history_filters_detail_payments_and_approved_refund_total(app):
    first, second = make_sales(app)
    line = refund_service.lookup_receipt(first.receipt_number).items[0]
    request = refund_service.create_request(
        first.receipt_number, [RefundLineInput(line.id, 1)], "Return"
    )
    auth_service.login("owner", "owner123")
    refund_service.approve(request.id, {request.items[0].id: False})
    screen = owner_screen(app, "Sales History")
    assert screen.tree.get_children() == (str(second.id), str(first.id))
    select_row(app, screen, first.id)
    detail = screen.detail.get("1.0", "end")
    assert "Ana Cruz" in detail and "Rubber Chew Toy" in detail
    assert "Cash received: ₱500.00" in detail and "Approved refunds: ₱150.00" in detail
    assert screen.tree.item(str(first.id), "values")[-1] == "₱150.00"
    select_row(app, screen, second.id)
    assert "GCash reference: REF-SALES" in screen.detail.get("1.0", "end")
    screen.method.set("GCash")
    screen.refresh()
    assert screen.tree.get_children() == (str(second.id),)
    screen.cashier.set(next(label for label in screen.cashiers if "(owner)" in label))
    screen.refresh()
    assert screen.tree.get_children() == ()
    assert "No completed sales" in screen.detail.get("1.0", "end")
    screen.cashier.set("All accounts")
    screen.method.set("All methods")
    screen.receipt_number.set(first.receipt_number.lower())
    screen.refresh()
    assert screen.tree.get_children() == (str(first.id),)


def test_invalid_filters_preserve_results_and_show_errors(app):
    first, second = make_sales(app)
    screen = owner_screen(app, "Sales History")
    screen.date_from.set("invalid")
    screen.refresh()
    assert "YYYY-MM-DD" in screen.status.get()
    assert len(screen.tree.get_children()) == 2
    screen.date_from.set((date.today() + timedelta(days=1)).isoformat())
    screen.date_to.set(date.today().isoformat())
    screen.refresh()
    assert "must not be after" in screen.status.get()
    screen.date_from.set(date.today().isoformat())
    screen.refresh()
    assert screen.tree.get_children() == (str(second.id), str(first.id))
    screen.receipt_number.set("%")
    screen.refresh()
    assert screen.tree.get_children() == ()
    assert screen.reprint_button.instate(["disabled"])


def test_reprint_writes_pdf_opens_viewer_and_does_not_charge_again(
    app, session_factory, tmp_path, monkeypatch
):
    first, _ = make_sales(app)
    screen = owner_screen(app, "Sales History")
    select_row(app, screen, first.id)
    monkeypatch.setattr(receipt_service, "RECEIPTS_DIR", tmp_path)
    with session_factory() as session:
        before = session.scalar(select(func.count()).select_from(StockMovement))
    with (
        patch.object(receipt_service.sys, "platform", "linux"),
        patch.object(receipt_service.subprocess, "Popen") as viewer,
    ):
        screen.reprint_button.invoke()
    path = tmp_path / f"{first.receipt_number}.pdf"
    assert path.read_bytes().startswith(b"%PDF-")
    assert viewer.call_args.args[0] == ["xdg-open", str(path)]
    assert "Receipt PDF opened" in screen.status.get()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(StockMovement)) == before
        assert (
            session.scalar(
                select(func.count()).select_from(Sale).where(Sale.status == "completed")
            )
            == 2
        )


def test_receipt_viewer_failure_retains_sale_selection_and_pdf(
    app, tmp_path, monkeypatch
):
    first, _ = make_sales(app)
    screen = owner_screen(app, "Sales History")
    select_row(app, screen, first.id)
    monkeypatch.setattr(receipt_service, "RECEIPTS_DIR", tmp_path)
    with (
        patch.object(receipt_service.sys, "platform", "linux"),
        patch.object(
            receipt_service.subprocess, "Popen", side_effect=OSError("No viewer")
        ),
    ):
        screen.reprint_button.invoke()
    assert "manually" in screen.status.get()
    assert screen.selected_sale_id == first.id
    assert (tmp_path / f"{first.receipt_number}.pdf").is_file()


def test_sales_history_reprint_accessible_at_minimum_window(app):
    first, _ = make_sales(app)
    app.geometry("1280x720")
    screen = owner_screen(app, "Sales History")
    select_row(app, screen, first.id)
    screen.form_canvas.yview_moveto(1)
    app.update()
    assert (
        screen.reprint_button.winfo_rooty() + screen.reprint_button.winfo_height()
        <= screen.form_canvas.winfo_rooty() + screen.form_canvas.winfo_height()
    )
    assert screen.tree.winfo_height() > 100
