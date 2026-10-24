"""The documented ten-step demo against a reopened, disposable SQLite database."""

from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from ttkbootstrap import Style

from pawpos.db import base
from pawpos.db.seed import seed_database
from pawpos.models import Product, RefundRequest, Sale, StockMovement, VoidLog
from pawpos.services import receipt_service, sale_service, user_service
from pawpos.ui.app import PawPOSApp
from pawpos.ui.dialogs.customer_picker import CustomerPicker
from pawpos.ui.dialogs.held_list import HeldListDialog
from pawpos.ui.dialogs.payment import PaymentDialog
from pawpos.ui.dialogs.receipt_preview import ReceiptPreview
from pawpos.ui.dialogs.refund_request import RefundRequestDialog
from pawpos.ui.dialogs.void import VoidDialog
from pawpos.ui.dialogs.weight import WeightDialog


def login(app, username, password):
    form = app.screen
    form.username.set(username)
    form.password.set(password)
    form.login_button.invoke()
    app.update()
    assert app.screen is not form
    return app.screen


def page(app, name):
    app.screen.buttons[name].invoke()
    app.update()
    return app.screen.current_screen


def select_row(app, tree, row_id):
    tree.selection_set(str(row_id))
    app.update()


def test_documented_demo_through_restart_refund_reports_and_accounts(
    app, tmp_path, monkeypatch
):
    path = tmp_path / "demo.sqlite"
    engines = []

    def open_store():
        engine = create_engine(f"sqlite+pysqlite:///{path}")
        engines.append(engine)

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        base.init_db(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        monkeypatch.setattr(base, "SessionLocal", factory)
        return factory

    factory = open_store()
    seed_database()
    monkeypatch.setattr(receipt_service, "RECEIPTS_DIR", tmp_path / "receipts")
    current_app = app
    try:
        # 1. Piece/kg entry, edit/remove, and an optional customer.
        pos = login(app, "cashier", "cashier123")
        products = {p.name: p for p in pos.products.values()}
        food = products["Dog Food Loose (Adult)"]
        toy = products["Rubber Chew Toy"]
        pouch = products["Whiskas Pouch 85g"]

        def amount(dialog, value):
            dialog.value.set(value)
            dialog.confirm_button.invoke()
            return dialog.result

        with patch.object(WeightDialog, "show", lambda dialog: amount(dialog, "1.5")):
            pos.cards[food.id].button.invoke()
        pos.cards[toy.id].button.invoke()
        pos.cards[pouch.id].button.invoke()
        pos.cards[pouch.id].button.invoke()
        select_row(app, pos.table, pouch.id)
        with patch.object(WeightDialog, "show", lambda dialog: amount(dialog, "3")):
            pos.edit_button.invoke()
        select_row(app, pos.table, toy.id)
        pos.remove_button.invoke()

        def customer(dialog):
            dialog.name.set("Demo Customer")
            dialog.contact.set("Demo contact")
            dialog.create()
            return dialog.result

        with patch.object(CustomerPicker, "show", customer):
            pos.select_customer()
        draft, customer_id = pos.cart.lines, pos.customer.id
        assert pos.cart.total == Decimal("226.50")

        # 2. Hold, close the app/engine, reopen the on-disk store, and resume.
        pos.hold_button.invoke()
        held = sale_service.list_held()[0]
        assert pos.cart.lines == ()
        app.close()
        engines[0].dispose()
        Style.instance = None
        factory = open_store()
        current_app = PawPOSApp()
        current_app.report_callback_exception = app.report_callback_exception
        current_app.update()
        pos = login(current_app, "cashier", "cashier123")

        def resume(dialog):
            dialog.table.selection_set(str(held.id))
            dialog.resume_button.invoke()
            return dialog.result

        with patch.object(HeldListDialog, "show", resume):
            pos.held_button.invoke()
        assert pos.cart.lines == draft and pos.customer.id == customer_id
        assert sale_service.list_held() == []

        # 3. Reasoned void before payment; stock remains unchanged.
        select_row(current_app, pos.table, pouch.id)

        def void(dialog):
            dialog.reason_choice.set("Customer changed mind")
            dialog.confirm_button.invoke()
            return dialog.result

        with patch.object(VoidDialog, "show", void):
            pos.void_button.invoke()
        assert len(pos.cart.lines) == 1 and pos.cart.total == Decimal("142.50")
        with factory() as session:
            assert session.get(Product, food.id).stock_quantity == 50
            assert session.get(Product, pouch.id).stock_quantity == 60
            assert session.scalar(select(func.count()).select_from(VoidLog)) == 1

        # 4. GCash payment, real receipt PDF, and OS viewer handoff.
        def pay(dialog):
            dialog.method.set("gcash")
            dialog.reference.set("DEMO-GCASH-001")
            dialog.confirm_button.invoke()
            return dialog.result

        def preview(dialog):
            dialog.print_pdf()
            assert not dialog.error.get()
            dialog.destroy()

        with (
            patch.object(PaymentDialog, "show", pay),
            patch.object(ReceiptPreview, "show", preview),
            patch.object(receipt_service.sys, "platform", "linux"),
            patch.object(receipt_service.subprocess, "Popen") as viewer,
        ):
            pos.pay_button.invoke()
        completed = pos.last_sale
        pdf = tmp_path / "receipts" / f"{completed.receipt_number}.pdf"
        assert pdf.read_bytes().startswith(b"%PDF-")
        assert viewer.call_args.args[0] == ["xdg-open", str(pdf)]
        assert pos.cart.lines == () and pos.customer is None

        # 5. Out-of-stock cards cannot add products.
        empty = products["Flea and Tick Spray"]
        assert pos.cards[empty.id].button.instate(["disabled"])
        pos.cards[empty.id].button.invoke()
        assert pos.cart.lines == ()

        # 6. Opened food is blocked; an unopened return becomes pending.
        def request(dialog):
            dialog.receipt_number.set(completed.receipt_number)
            dialog.load()
            _, selected, quantity, opened = next(iter(dialog.rows.values()))
            selected.set(True)
            quantity.set("0.5")
            opened.set(True)
            dialog.reason.set("Return unopened food")
            dialog.submit_button.invoke()
            assert "Opened food" in dialog.error.get() and dialog.result is None
            opened.set(False)
            dialog.submit_button.invoke()
            return dialog.result

        with patch.object(RefundRequestDialog, "show", request):
            pos.refund_button.invoke()
        assert "owner approval" in pos.status.get()

        # 7. Separate owner login, approval, and linked refund stock history.
        pos.logout_button.invoke()
        login(current_app, "owner", "owner123")
        refunds = page(current_app, "Refunds")
        request_id = int(refunds.trees["Pending"].get_children()[0])
        select_row(current_app, refunds.trees["Pending"], request_id)
        next(iter(refunds.resellable.values())).set("Yes")
        with patch("pawpos.ui.owner.refunds.messagebox.askyesno", return_value=True):
            refunds.approve_button.invoke()
        inventory = page(current_app, "Inventory")
        inventory.history_type.set("refund")
        inventory.refresh_history()
        movement = inventory.history_tree.item(
            inventory.history_tree.get_children()[0], "values"
        )
        assert movement[3] == "+0.5 kg" and movement[5] == f"refund #{request_id}"

        # 8. Receiving makes a previously low product leave the dashboard list.
        low = products["Cat Feather Wand"]
        inventory.receive_product.set(
            next(label for label, p in inventory.products.items() if p.id == low.id)
        )
        inventory.prefill_supplier()
        inventory.receive_quantity.set("3")
        inventory.receive_note.set("Demo delivery")
        inventory.receive_button.invoke()
        assert inventory.status.get() == "Stock received."

        # 9. Dashboard arithmetic, saved customer purchases, history, and reprint.
        dashboard = page(current_app, "Dashboard")
        assert dashboard.values["net_sales"].get() == "₱95.00"
        assert dashboard.values["transactions"].get() == "1"
        assert str(low.id) not in dashboard.low_tree.get_children()
        assert len(dashboard.best_chart.axes.patches) == 1
        customers = page(current_app, "Customers")
        select_row(current_app, customers.tree, customer_id)
        assert customers.purchases_tree.get_children() == (str(completed.id),)
        history = page(current_app, "Sales History")
        select_row(current_app, history.tree, completed.id)
        assert history.tree.item(str(completed.id), "values")[-1] == "₱47.50"
        with (
            patch.object(receipt_service.sys, "platform", "linux"),
            patch.object(receipt_service.subprocess, "Popen") as viewer,
        ):
            history.reprint_button.invoke()
        assert viewer.call_args.args[0] == ["xdg-open", str(pdf)]

        # 10. Add/disable a cashier and confirm an actual login attempt fails.
        users = page(current_app, "Users")
        users.username.set("democashier")
        users.full_name.set("Demo Cashier")
        users.password.set("demo-test-pass")
        users.create_button.invoke()
        cashier = next(
            user for user in user_service.list_users() if user.username == "democashier"
        )
        select_row(current_app, users.tree, cashier.id)
        with patch("pawpos.ui.owner.users.messagebox.askyesno", return_value=True):
            users.toggle_button.invoke()
        current_app.screen.logout_button.invoke()
        form = current_app.screen
        form.username.set("democashier")
        form.password.set("demo-test-pass")
        form.login_button.invoke()
        assert current_app.screen is form and "disabled" in form.error.get()
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Sale)) == 1
            assert session.get(Product, food.id).stock_quantity == 49
            assert session.get(RefundRequest, request_id).status == "approved"
            changes = session.scalars(
                select(StockMovement.quantity_change)
                .where(StockMovement.product_id == food.id)
                .order_by(StockMovement.id)
            ).all()
            assert changes == [Decimal("50"), Decimal("-1.5"), Decimal("0.5")]
    finally:
        if current_app is not app:
            current_app.close()
        Style.instance = None
        for engine in engines:
            engine.dispose()
