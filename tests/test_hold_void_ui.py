from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import func, select
from ttkbootstrap import Style

from pawpos.models import Product, Sale, StockMovement, VoidLog
from pawpos.services import auth_service, customer_service, sale_service
from pawpos.ui.app import PawPOSApp
from pawpos.ui.dialogs.held_list import HeldListDialog
from pawpos.ui.dialogs.payment import PaymentDialog
from pawpos.ui.dialogs.receipt_preview import ReceiptPreview
from pawpos.ui.dialogs.void import VoidDialog


def pos(app):
    app.show_workspace(auth_service.login("cashier", "cashier123"))
    app.update()
    return app.screen


def fill_cart(screen):
    toy = next(
        row for row in screen.products.values() if row.name == "Cat Feather Wand"
    )
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
    screen.customer = customer_service.create_customer("Test Customer")
    screen.customer_text.set(screen.customer.name)
    return toy


def test_hold_f4_and_resume_after_recreating_app(app, session_factory):
    screen = pos(app)
    fill_cart(screen)
    original = screen.cart.lines
    customer = screen.customer
    screen.search_entry.focus_force()
    app.update()
    app.event_generate("<F4>")
    app.update()
    assert screen.cart.lines == () and screen.customer is None
    assert (
        screen.customer_text.get() == "Walk-in" and screen.total_text.get() == "₱0.00"
    )
    held = sale_service.list_held()[0]
    app.close()
    Style.instance = None
    reopened = PawPOSApp()
    reopened.report_callback_exception = app.report_callback_exception
    try:
        screen = pos(reopened)

        def choose(dialog):
            assert dialog.table.get_children() == (str(held.id),)
            values = dialog.table.item(str(held.id), "values")
            assert (
                values[1] == "2"
                and values[2] == "₱215.63"
                and values[3] == customer.name
            )
            dialog.table.selection_set(str(held.id))
            dialog.resume_button.invoke()
            return dialog.result

        with patch.object(HeldListDialog, "show", choose):
            screen.open_held()
        assert screen.cart.lines == original and screen.customer == customer
        assert screen.total_text.get() == "₱215.63"
        assert sale_service.list_held() == []
        with session_factory() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(StockMovement)
                    .where(StockMovement.movement_type == "sale")
                )
                == 0
            )

        def void_selected(dialog):
            dialog.reason_choice.set("Wrong item")
            dialog.confirm()
            return dialog.result

        screen.table.selection_set(str(original[0].product_id))
        with patch.object(VoidDialog, "show", void_selected):
            screen.void_current()

        def pay(dialog):
            dialog.method.set("gcash")
            dialog.reference.set("TEST-HELD-SALE")
            dialog.confirm()
            return dialog.result

        with (
            patch.object(PaymentDialog, "show", pay),
            patch.object(ReceiptPreview, "show", lambda dialog: dialog.destroy()),
        ):
            screen.pay()
        assert screen.cart.lines == () and screen.customer is None
        with session_factory() as session:
            sales = session.scalars(select(Sale)).all()
            assert len(sales) == 1 and sales[0].status == "completed"
            assert (
                sales[0].total == Decimal("130.63")
                and sales[0].customer_id == customer.id
            )
            assert session.get(Product, original[0].product_id).stock_quantity == 3
            assert session.get(
                Product, original[1].product_id
            ).stock_quantity == Decimal("48.625")
            assert session.scalar(select(func.count()).select_from(VoidLog)) == 1
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(StockMovement)
                    .where(StockMovement.movement_type == "sale")
                )
                == 1
            )
    finally:
        reopened.close()
        Style.instance = None


def test_active_cart_cannot_be_overwritten_and_held_cancel_preserves_it(app):
    screen = pos(app)
    fill_cart(screen)
    held = sale_service.hold_cart(screen.cart, customer_id=screen.customer.id)
    before = screen.cart.lines
    dialog = HeldListDialog(screen, can_resume=False)
    assert dialog.resume_button.instate(["disabled"])
    dialog.table.selection_set(str(held.id))
    dialog.resume()
    assert "Hold or empty" in dialog.error.get()
    assert dialog.result is None

    def cancel(void):
        void.reason_choice.set("Customer changed mind")
        void.confirm()
        return void.result

    with patch.object(VoidDialog, "show", cancel):
        dialog.cancel_selected()
    assert dialog.table.get_children() == ()
    assert screen.cart.lines == before and screen.customer is not None
    dialog.destroy()


def test_void_dialog_validation_cancel_line_and_transaction(app, session_factory):
    screen = pos(app)
    toy = fill_cart(screen)
    calls = []
    dialog = VoidDialog(screen, lambda scope, reason: calls.append((scope, reason)))
    assert dialog.confirm_button.instate(["disabled"])
    dialog.reason_choice.set("Other")
    dialog.other.set(" ")
    assert dialog.confirm_button.instate(["disabled"])
    dialog.other.set("x" * 256)
    assert dialog.confirm_button.instate(["disabled"])
    dialog.other.set(" Wrong size ")
    assert not dialog.confirm_button.instate(["disabled"])
    dialog.confirm()
    dialog.confirm()
    assert calls == [("line", "Wrong size")]
    before = screen.cart.lines
    with patch.object(VoidDialog, "show", lambda self: self.destroy()):
        screen.void_current()
    assert screen.cart.lines == before
    screen.table.selection_set(str(toy.id))

    def void_line(dialog):
        assert dialog.scope.get() == "line"
        dialog.reason_choice.set("Wrong item")
        dialog.confirm()
        return dialog.result

    with patch.object(VoidDialog, "show", void_line):
        screen.void_current()
    assert len(screen.cart.lines) == 1 and screen.customer is not None
    assert screen.total_text.get() == "₱130.63"

    def void_all(dialog):
        dialog.scope.set("transaction")
        dialog.reason_choice.set("Other")
        dialog.other.set("Customer left")
        dialog.confirm()
        return dialog.result

    with patch.object(VoidDialog, "show", void_all):
        screen.void_current()
    assert screen.cart.lines == () and screen.customer is None
    assert screen.total_text.get() == "₱0.00"
    with session_factory() as session:
        logs = session.scalars(select(VoidLog).order_by(VoidLog.id)).all()
        assert [(row.void_scope, row.reason, row.amount) for row in logs] == [
            ("line", "Wrong item", Decimal("85")),
            ("transaction", "Customer left", Decimal("130.63")),
        ]


def test_hold_and_void_failures_preserve_cart_and_show_generic_error(app):
    screen = pos(app)
    fill_cart(screen)
    before = screen.cart.lines
    customer = screen.customer
    with patch.object(
        sale_service, "hold_cart", side_effect=RuntimeError("private detail")
    ):
        screen.hold_current()
    assert screen.cart.lines == before and screen.customer == customer
    assert (
        "Cannot complete" in screen.status.get()
        and "private detail" not in screen.status.get()
    )
    dialog = VoidDialog(
        screen,
        lambda _scope, reason: sale_service.void_all(screen.cart, reason),
        allow_line=False,
    )
    dialog.reason_choice.set("Wrong item")
    with patch.object(
        sale_service, "void_all", side_effect=RuntimeError("private detail")
    ):
        dialog.confirm()
    assert dialog.result is None and dialog.winfo_exists() and not dialog.submitting
    assert (
        "Cannot complete" in dialog.error.get()
        and "private detail" not in dialog.error.get()
    )
    assert screen.cart.lines == before
    dialog.destroy()


def test_nested_held_cancellation_restores_modal_grab_and_logs(app, session_factory):
    screen = pos(app)
    fill_cart(screen)
    screen.hold_current()
    held = sale_service.list_held()[0]
    outer = HeldListDialog(screen)
    timed_out = []

    def watchdog():
        timed_out.append(True)
        for child in outer.winfo_children():
            if isinstance(child, VoidDialog):
                child.destroy()
        outer.destroy()

    timer = app.after(5000, watchdog)

    def confirm_reason():
        inner = next(
            child for child in outer.winfo_children() if isinstance(child, VoidDialog)
        )
        assert app.grab_current() == inner
        inner.reason_choice.set("Wrong weight")
        inner.first_input.focus_force()
        app.update()
        inner.first_input.event_generate("<Return>")

    def cancel():
        outer.table.selection_set(str(held.id))
        app.after(100, confirm_reason)
        outer.cancel_button.invoke()
        assert app.grab_current() == outer
        assert outer.table.get_children() == ()

        def close_parent():
            outer.table.focus_force()
            outer.table.event_generate("<Escape>")

        outer.after(100, close_parent)

    app.after(100, cancel)
    assert outer.show() is None
    app.after_cancel(timer)
    assert not timed_out
    assert app.grab_current() is None
    with session_factory() as session:
        assert session.get(Sale, held.id) is None
        logs = session.scalars(select(VoidLog)).all()
        assert len(logs) == 2
        assert all(
            row.reason == "Wrong weight" and row.void_scope == "transaction"
            for row in logs
        )


def test_held_empty_state_selection_errors_and_cancel_are_safe(app):
    screen = pos(app)
    dialog = HeldListDialog(screen)
    assert "No held transactions" in dialog.message.get()
    assert dialog.resume_button.instate(["disabled"])
    assert dialog.cancel_button.instate(["disabled"])
    dialog.resume()
    assert "Select a held transaction" in dialog.error.get()
    dialog.destroy()
    fill_cart(screen)
    held = sale_service.hold_cart(screen.cart)
    dialog = HeldListDialog(screen)
    dialog.table.selection_set(str(held.id))
    with patch.object(VoidDialog, "show", lambda self: self.destroy()):
        dialog.cancel_selected()
    assert sale_service.list_held() == [held]
    dialog.destroy()
