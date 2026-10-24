from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import event, func, select

from pawpos.models import Product, RefundRequest, StockMovement
from pawpos.services import auth_service, product_service, refund_service, sale_service
from pawpos.services.cart import Cart
from pawpos.services.sale_service import Payment
from pawpos.ui.dialogs.receipt_preview import ReceiptPreview
from pawpos.ui.dialogs.refund_request import RefundRequestDialog
from pawpos.ui.owner.refunds import RefundsScreen
from tests.test_catalog_ui import owner_screen


def sale(app):
    app.show_workspace(auth_service.login("cashier", "cashier123"))
    app.update()
    products = product_service.list_products()
    toy = next(p for p in products if p.name == "Rubber Chew Toy")
    food = next(p for p in products if p.name == "Dog Food Loose (Adult)")
    cart = Cart()
    cart.add_piece(
        toy.id, toy.name, toy.unit_price, 2, stock_quantity=toy.stock_quantity
    )
    cart.add_weight(
        food.id, food.name, food.unit_price, "1.375", stock_quantity=food.stock_quantity
    )
    completed = sale_service.complete_sale(cart, Payment("cash", 500))
    return completed, toy, food


def load_dialog(app, completed):
    dialog = RefundRequestDialog(app.screen)
    dialog.receipt_number.set(completed.receipt_number)
    dialog.load()
    assert not dialog.error.get()
    return dialog


def enter_line(dialog, unit="piece", amount="1", opened=False):
    item, selected, qty, is_opened = next(
        row for row in dialog.rows.values() if row[0].unit_type == unit
    )
    selected.set(True)
    qty.set(amount)
    is_opened.set(opened)
    return item


def submit_request(app, completed, **kwargs):
    dialog = load_dialog(app, completed)
    enter_line(dialog, **kwargs)
    dialog.reason.set("Return")
    dialog.submit()
    assert dialog.result is not None
    return dialog.result


def select_refund(app, screen, request_id, tab="Pending"):
    screen.notebook.select(0 if tab == "Pending" else 1)
    app.update()
    screen.trees[tab].selection_set(str(request_id))
    app.update()
    assert screen.selected.id == request_id


def test_cashier_request_owner_approval_badge_and_inventory_history(
    app, session_factory
):
    completed, toy, food = sale(app)
    pos = app.screen
    pos.add_product(toy.id)
    cart_before = pos.cart.lines

    def request(dialog):
        dialog.receipt_number.set(completed.receipt_number)
        dialog.load()
        enter_line(dialog, amount="1")
        enter_line(dialog, "kg", "1.375")
        assert dialog.total.get() == "Requested total: ₱280.63"
        dialog.reason.set("Returned unopened")
        dialog.submit_button.invoke()
        return dialog.result

    with patch.object(RefundRequestDialog, "show", request):
        pos.refund_button.invoke()
    assert "owner approval" in pos.status.get()
    assert pos.cart.lines == cart_before
    screen = owner_screen(app, "Refunds")
    assert isinstance(screen, RefundsScreen)
    assert app.screen.buttons["Refunds"].cget("text") == "Refunds (1)"
    request_id = int(screen.trees["Pending"].get_children()[0])
    select_refund(app, screen, request_id)
    for item in screen.selected.items:
        screen.resellable[item.id].set("Yes" if item.unit_type == "kg" else "No")
    with patch("pawpos.ui.owner.refunds.messagebox.askyesno", return_value=True):
        screen.approve_button.invoke()
    assert not screen.trees["Pending"].get_children()
    assert app.screen.buttons["Refunds"].cget("text") == "Refunds (0)"
    select_refund(app, screen, request_id, "History")
    assert (
        screen.selected.status == "approved"
        and screen.selected.reviewer == "Shop Owner"
    )
    assert screen.approve_button.instate(["disabled"])
    with session_factory() as session:
        assert session.get(Product, toy.id).stock_quantity == toy.stock_quantity - 2
        assert session.get(Product, food.id).stock_quantity == food.stock_quantity
        rows = session.scalars(
            select(StockMovement).where(StockMovement.movement_type == "refund")
        ).all()
        assert len(rows) == 1 and rows[0].quantity_change == Decimal("1.375")
    app.screen.buttons["Inventory"].invoke()
    history = app.screen.current_screen
    history.history_type.set("refund")
    history.refresh_history()
    values = history.history_tree.item(history.history_tree.get_children()[0], "values")
    assert values[3] == "+1.375 kg" and values[5] == f"refund #{request_id}"


def test_request_validation_keeps_inputs_and_receipt_edit_invalidates_load(app):
    completed, _, _ = sale(app)
    dialog = load_dialog(app, completed)
    enter_line(dialog, "kg", "0.5", True)
    dialog.reason.set("Opened bag")
    dialog.submit()
    assert "Opened food" in dialog.error.get()
    assert dialog.reason.get() == "Opened bag" and dialog.result is None
    dialog.receipt_number.set("missing")
    assert dialog.submit_button.instate(["disabled"]) and dialog.rows == {}
    dialog.load()
    assert "not found" in dialog.error.get()
    dialog.destroy()


def test_owner_rejection_requires_note_and_confirmation_then_releases_quantity(app):
    completed, _, _ = sale(app)
    result = submit_request(app, completed)
    screen = owner_screen(app, "Refunds")
    select_refund(app, screen, result.id)
    screen.reject_button.invoke()
    assert "note is required" in screen.status.get()
    screen.note.set("Return does not match receipt")
    with patch("pawpos.ui.owner.refunds.messagebox.askyesno", return_value=False):
        screen.reject_button.invoke()
    assert refund_service.pending_refund_count() == 1
    with patch("pawpos.ui.owner.refunds.messagebox.askyesno", return_value=True):
        screen.reject_button.invoke()
    select_refund(app, screen, result.id, "History")
    assert screen.selected.review_note == "Return does not match receipt"
    assert refund_service.remaining_refundable(result.items[0].sale_item_id) == 2
    assert "Return does not match receipt" in screen.detail.get()


def test_failed_request_keeps_input_and_failed_review_keeps_pending_flags(
    app, session_factory
):
    completed, _, _ = sale(app)
    dialog = load_dialog(app, completed)
    enter_line(dialog)
    dialog.reason.set("Return")

    def fail(_session):
        raise RuntimeError("Commit failed")

    event.listen(session_factory, "before_commit", fail)
    try:
        dialog.submit()
    finally:
        event.remove(session_factory, "before_commit", fail)
    assert dialog.result is None and dialog.winfo_exists()
    assert dialog.reason.get() == "Return"
    dialog.submit()
    result = dialog.result
    screen = owner_screen(app, "Refunds")
    select_refund(app, screen, result.id)
    variable = next(iter(screen.resellable.values()))
    variable.set("Yes")
    event.listen(session_factory, "before_commit", fail)
    try:
        with patch("pawpos.ui.owner.refunds.messagebox.askyesno", return_value=True):
            screen.approve_button.invoke()
    finally:
        event.remove(session_factory, "before_commit", fail)
    assert screen.selected.id == result.id and variable.get() == "Yes"
    assert refund_service.list_pending()[0].items[0].resellable is None


def test_reprint_uses_loaded_receipt_without_new_sale_or_refund(app, session_factory):
    completed, _, _ = sale(app)
    dialog = load_dialog(app, completed)
    receipts = []

    def preview(window):
        receipts.append(window.receipt)
        window.destroy()

    with patch.object(ReceiptPreview, "show", preview):
        dialog.reprint_button.invoke()
    # Receipt preview uses the existing sale; it does not create a request.
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(RefundRequest)) == 0
    assert len(receipts) == 1 and receipts[0].sale_id == completed.id
    assert receipts[0].receipt_number == completed.receipt_number
    assert dialog.result is None
    dialog.destroy()


def test_owner_pos_request_updates_badge_without_losing_cart(app):
    completed, _, _ = sale(app)
    pos = owner_screen(app, "POS")

    def request(dialog):
        dialog.receipt_number.set(completed.receipt_number)
        dialog.load()
        enter_line(dialog)
        dialog.reason.set("Return")
        dialog.submit()
        return dialog.result

    with patch.object(RefundRequestDialog, "show", request):
        pos.refund_button.invoke()
    app.update()
    assert app.screen.buttons["Refunds"].cget("text") == "Refunds (1)"


def test_request_modal_escape_and_minimum_window_review_controls(app):
    completed, _, _ = sale(app)
    dialog = load_dialog(app, completed)
    app.after(100, lambda: dialog.event_generate("<Escape>"))
    assert dialog.show() is None
    result = submit_request(app, completed)
    app.geometry("1280x720")
    screen = owner_screen(app, "Refunds")
    select_refund(app, screen, result.id)
    app.update()
    assert (
        screen.reject_button.winfo_rooty() + screen.reject_button.winfo_height()
        <= app.winfo_rooty() + app.winfo_height()
    )
    assert screen.trees["Pending"].winfo_height() >= 90


def test_committed_review_refresh_failure_disables_resubmission(app):
    completed, _, _ = sale(app)
    result = submit_request(app, completed)
    screen = owner_screen(app, "Refunds")
    select_refund(app, screen, result.id)
    with (
        patch.object(screen, "_load", side_effect=RuntimeError("Read failed")),
        patch("pawpos.ui.owner.refunds.messagebox.askyesno", return_value=True),
    ):
        screen.approve_button.invoke()
    assert "Review saved" in screen.status.get()
    assert screen.selected is None and screen.approve_button.instate(["disabled"])
    assert refund_service.list_history()[0].status == "approved"
