from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from pawpos.models import Product, Sale, StockMovement
from pawpos.services import (
    auth_service,
    customer_service,
    receipt_service,
    sale_service,
)
from pawpos.ui.dialogs.payment import PaymentDialog
from pawpos.ui.dialogs.receipt_preview import ReceiptPreview


def pos(app):
    app.show_workspace(auth_service.login("cashier", "cashier123"))
    app.update()
    return app.screen


def add_toy(screen):
    toy = next(
        row for row in screen.products.values() if row.name == "Cat Feather Wand"
    )
    screen.add_product(toy.id)
    return toy


def test_live_tender_validation_method_switch_quick_amount_and_cancel(app):
    screen = pos(app)
    add_toy(screen)
    dialog = PaymentDialog(screen, screen.cart)
    assert dialog.confirm_button.instate(["disabled"])
    for value in ("", "84.99", "100.001", "NaN", "abc"):
        dialog.amount.set(value)
        assert dialog.confirm_button.instate(["disabled"])
    dialog.amount.set("100")
    assert dialog.change.get() == "Change: ₱15.00"
    assert not dialog.confirm_button.instate(["disabled"])
    quick_buttons = dialog.cash_frame.winfo_children()[2].winfo_children()
    quick_buttons[0].invoke()
    assert dialog.amount.get() == "85.00"
    assert dialog.change.get() == "Change: ₱0.00"
    dialog.method.set("gcash")
    assert dialog.first_input == dialog.reference_entry
    assert dialog.confirm_button.instate(["disabled"])
    dialog.reference.set(" " * 5)
    assert dialog.confirm_button.instate(["disabled"])
    dialog.reference.set("REF-123")
    assert not dialog.confirm_button.instate(["disabled"])
    assert dialog.change.get() == ""
    dialog.reference.set("x" * 51)
    assert dialog.confirm_button.instate(["disabled"])
    dialog.destroy()
    assert screen.cart.total == 85


def test_modal_takes_keyboard_focus_and_restores_owner_focus(app):
    screen = pos(app)
    add_toy(screen)
    screen.search_entry.focus_force()
    app.update()
    dialog = PaymentDialog(screen, screen.cart)
    focused = []

    def cancel_from_keyboard():
        # Native activation/focus events may follow the first timer on Windows.
        if app.focus_get() != dialog.first_input:
            app.after(10, cancel_from_keyboard)
            return
        focused.append(app.focus_get())
        dialog.event_generate("<Escape>")

    watchdog = app.after(2000, dialog.destroy)
    app.after(100, cancel_from_keyboard)
    assert dialog.show() is None
    app.after_cancel(watchdog)
    app.update()
    assert focused == [dialog.first_input]
    assert app.focus_get() == screen.search_entry
    assert app.grab_current() is None


@pytest.mark.parametrize("method", ["cash", "gcash"])
def test_full_payment_receipt_pdf_and_cart_reset(
    app, session_factory, tmp_path, method
):
    screen = pos(app)
    toy = add_toy(screen)
    screen.add_product(toy.id)
    screen.add_product(toy.id)
    food = next(
        row
        for row in screen.products.values()
        if row.unit_type == "kg" and row.unit_price == 95
    )
    screen.cart.add_weight(
        food.id, food.name, food.unit_price, "1.375", stock_quantity=food.stock_quantity
    )
    screen.render_cart()
    customer = customer_service.create_customer("Test Customer")
    screen.customer = customer
    screen.customer_text.set(customer.name)
    preview_text = []

    def close_stalled_dialogs():
        for child in screen.winfo_children():
            if isinstance(child, (PaymentDialog, ReceiptPreview)):
                child.destroy()

    watchdog = app.after(5000, close_stalled_dialogs)

    def confirm_payment():
        dialog = next(
            child
            for child in screen.winfo_children()
            if isinstance(child, PaymentDialog)
        )
        if method == "cash":
            dialog.amount.set("500")
        else:
            dialog.method.set("gcash")
            dialog.reference.set("REF-001")
        dialog.event_generate("<Return>")
        app.after(100, close_preview)

    def close_preview():
        preview = next(
            child
            for child in screen.winfo_children()
            if isinstance(child, ReceiptPreview)
        )
        preview_text.append(preview.text.get("1.0", "end"))
        assert str(preview.text.cget("state")) == "disabled"
        preview.first_input.invoke()
        assert "PDF opened:" in preview.message.get()
        preview.destroy()

    with (
        patch.object(receipt_service, "RECEIPTS_DIR", tmp_path),
        patch.object(receipt_service.sys, "platform", "linux"),
        patch.object(receipt_service.subprocess, "Popen") as opener,
    ):
        app.after(100, confirm_payment)
        screen.pay_button.invoke()
    app.after_cancel(watchdog)
    assert screen.cart.lines == () and screen.customer is None
    assert (
        screen.customer_text.get() == "Walk-in" and screen.total_text.get() == "₱0.00"
    )
    assert screen.pay_button.instate(["disabled"])
    assert not screen.last_receipt_button.instate(["disabled"])
    assert screen.cards[toy.id].button.instate(["disabled"])
    assert (
        "TOTAL: ₱385.63" in preview_text[0]
        and "Customer: Test Customer" in preview_text[0]
    )
    assert "1.375 kg" in preview_text[0]
    pdf = tmp_path / f"{screen.last_sale.receipt_number}.pdf"
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert opener.call_args.args[0] == ["xdg-open", str(pdf)]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Sale)) == 1
        sale = session.get(Sale, screen.last_sale.id)
        assert sale.payment_method == method and sale.customer_id == customer.id
        assert sale.total == Decimal("385.63")
        assert session.get(Product, toy.id).stock_quantity == 0
        assert session.get(Product, food.id).stock_quantity == Decimal("48.625")
        movements = session.scalars(
            select(StockMovement).where(
                StockMovement.reference_id == sale.id,
                StockMovement.movement_type == "sale",
            )
        ).all()
        assert len(movements) == 2
    # Reopening the last receipt never charges or deducts stock again.
    with patch.object(ReceiptPreview, "show", lambda self: self.destroy()):
        screen.last_receipt_button.invoke()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Sale)) == 1


def test_cancel_payment_preserves_cart_and_customer(app, session_factory):
    screen = pos(app)
    add_toy(screen)
    screen.customer = customer_service.create_customer("Test Customer")
    before = screen.cart.lines

    def cancel():
        dialog = next(
            child
            for child in screen.winfo_children()
            if isinstance(child, PaymentDialog)
        )
        dialog.event_generate("<Escape>")

    app.after(100, cancel)
    screen.pay_button.invoke()
    assert screen.cart.lines == before and screen.customer.name == "Test Customer"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Sale)) == 0


def test_failed_sale_keeps_payment_dialog_and_cart_for_correction(app, session_factory):
    screen = pos(app)
    toy = add_toy(screen)
    with session_factory.begin() as session:
        session.get(Product, toy.id).stock_quantity = 0
    before = screen.cart.lines
    dialog = PaymentDialog(screen, screen.cart)
    dialog.amount.set("100")
    dialog.confirm()
    assert dialog.result is None and dialog.winfo_exists()
    assert "Not enough stock" in dialog.error.get()
    assert screen.cart.lines == before
    assert not dialog.submitting
    with patch.object(
        sale_service, "complete_sale", side_effect=RuntimeError("private detail")
    ):
        dialog.confirm()
    assert (
        "Cannot complete" in dialog.error.get()
        and "private detail" not in dialog.error.get()
    )
    dialog.destroy()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Sale)) == 0


def test_committed_sale_survives_preview_failure_without_duplicate_payment(
    app, session_factory
):
    screen = pos(app)
    add_toy(screen)

    def accept(dialog):
        dialog.amount.set("100")
        dialog.confirm()
        dialog.confirm()  # A queued second confirmation must not complete another sale.
        return dialog.result

    with (
        patch.object(PaymentDialog, "show", accept),
        patch.object(
            receipt_service, "build_receipt", side_effect=RuntimeError("private detail")
        ),
    ):
        screen.pay()
    assert screen.cart.lines == ()
    assert (
        "is complete" in screen.status.get() and "Last receipt" in screen.status.get()
    )
    assert "private detail" not in screen.status.get()
    with patch.object(ReceiptPreview, "show", lambda self: self.destroy()):
        screen.open_last_receipt()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Sale)) == 1


def test_print_failure_does_not_close_preview_or_repeat_sale(app):
    screen = pos(app)
    add_toy(screen)
    sale = sale_service.complete_sale(screen.cart, sale_service.Payment("cash", 100))
    preview = ReceiptPreview(screen, receipt_service.build_receipt(sale.id))
    with patch.object(
        receipt_service, "print_receipt", side_effect=OSError("private path")
    ):
        preview.print_pdf()
    assert preview.winfo_exists()
    assert "Cannot complete" in preview.error.get()
    assert "private path" not in preview.error.get()
    preview.destroy()
