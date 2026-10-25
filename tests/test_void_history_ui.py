import tkinter as tk
from datetime import date, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select

from pawpos.core import session as login_session
from pawpos.models import Product, Sale, StockMovement, User, VoidLog
from pawpos.services import (
    auth_service,
    customer_service,
    sale_service,
    void_history_service,
)
from pawpos.ui.void_history import VoidHistoryDialog, VoidHistoryScreen
from tests.test_catalog_ui import owner_screen
from tests.test_pos_ui import by_name, cashier_pos


def add_records(factory):
    with factory.begin() as session:
        users = session.scalars(select(User).order_by(User.id)).all()
        for i, user in enumerate(users):
            session.add(
                VoidLog(
                    user_id=user.id,
                    product_name="Historical product",
                    quantity="1.375",
                    amount="130.63",
                    void_scope="transaction",
                    reason=f"{user.full_name}: " + "reason " * 35,
                    created_at=datetime(2026, 10, 25 + i, 23, 59, 59),
                )
            )


def test_cashier_filter_reason_retry_and_session_isolation(app, session_factory):
    add_records(session_factory)
    pos = cashier_pos(app)
    dialog = VoidHistoryDialog(pos)
    form = dialog.form
    assert len(form.records) == 1
    row = next(iter(form.records.values()))
    assert row.user_id == login_session.current_user.id
    form.tree.selection_set(str(row.id))
    form.show_selected()
    assert form.detail.get("1.0", "end-1c") == row.reason
    assert str(form.detail.cget("state")) == "disabled"
    before = form.tree.get_children()
    with patch.object(
        void_history_service, "list_voids", side_effect=RuntimeError("private")
    ):
        form.refresh_button.invoke()
    assert form.tree.get_children() == before
    assert "retry" in form.status.get() and "private" not in form.status.get()
    assert form.detail.get("1.0", "end-1c") == row.reason
    form.date_from.set("2026-10-27")
    form.date_to.set("2026-10-26")
    form.refresh()
    assert "must not be after" in form.status.get()
    assert form.tree.get_children() == before
    form.date_to.set("")
    form.refresh()
    assert not form.records and "No void" in form.status.get()
    form.date_pickers[0].clear_button.invoke()
    form.refresh()
    assert len(form.records) == 1
    # The shared calendar adapter must pass both selection and cancellation through.
    with patch("pawpos.ui.widgets.date_picker._CalendarDialog") as calendar:
        calendar.return_value.selection = date(2026, 10, 26)
        form.date_pickers[0].open_calendar()
        calendar.return_value.selection = None
        form.date_pickers[0].open_calendar()
    assert form.date_from.get() == "2026-10-26"
    form.date_to.set("2026-10-26")
    form.refresh()
    assert form.tree.get_children() == before
    auth_service.login("owner", "owner123")
    watched = tk.BooleanVar(app)
    app.after(250, lambda: watched.set(True))
    app.wait_variable(watched)
    assert not form.records and not form.tree.get_children()
    assert form.detail.get("1.0", "end-1c") == ""
    form.refresh()
    assert not form.records and "Session changed" in form.status.get()
    dialog.destroy()


def test_owner_navigation_all_actors_and_disabled_access(app, session_factory):
    add_records(session_factory)
    pos = owner_screen(app, "POS")
    pos.add_product(by_name(pos, "Cat Feather Wand").id)
    pos.customer = customer_service.create_customer("Void history customer")
    pos.last_sale = object()
    before = (pos.cart.lines, pos.customer, pos.last_sale)
    app.screen.buttons["Void History"].invoke()
    app.update()
    form = app.screen.current_screen
    assert isinstance(form, VoidHistoryScreen)
    assert len(form.records) == 2
    owner_id = login_session.current_user.id
    with session_factory.begin() as session:
        cashier = session.scalar(select(User).where(User.role == "cashier"))
        cashier.is_active = False
    form.refresh()
    assert len(form.records) == 2
    # Downgrade the persisted role while the in-memory owner identity is stale.
    with session_factory.begin() as session:
        session.get(User, owner_id).role = "cashier"
    form.tree.selection_set(form.tree.get_children()[0])
    form.show_selected()
    assert not form.records and form.detail.get("1.0", "end-1c") == ""
    form.refresh()
    assert {r.user_id for r in form.records.values()} == {owner_id}
    with session_factory.begin() as session:
        session.get(User, owner_id).is_active = False
    form.show_selected()
    assert not form.records
    with session_factory.begin() as session:
        user = session.get(User, owner_id)
        user.is_active = True
        user.role = "owner"
    app.screen.buttons["POS"].invoke()
    assert app.screen.current_screen is pos
    assert (pos.cart.lines, pos.customer, pos.last_sale) == before


def test_new_void_paths_actor_snapshots_and_read_only(app, session_factory):
    pos = cashier_pos(app)
    product_id = by_name(pos, "Cat Feather Wand").id
    pos.add_product(product_id)
    sale_service.void_line(pos.cart, product_id, "Wrong item")
    pos.add_product(product_id)
    sale_service.void_all(pos.cart, "Customer left")
    pos.add_product(product_id)
    held = sale_service.hold_cart(pos.cart)
    original_actor = login_session.current_user.id
    auth_service.login("owner", "owner123")
    sale_service.cancel_held(held.id, "Held cancellation")
    with session_factory.begin() as session:
        session.get(Product, product_id).name = "Renamed after void"

    def snapshot():
        with session_factory() as session:
            return (
                tuple(
                    (r.id, r.user_id, r.reason, r.quantity, r.amount)
                    for r in session.scalars(select(VoidLog))
                ),
                tuple(
                    (p.id, p.stock_quantity) for p in session.scalars(select(Product))
                ),
                tuple((s.id, s.status) for s in session.scalars(select(Sale))),
                tuple(m.id for m in session.scalars(select(StockMovement))),
            )

    before = snapshot()
    form = VoidHistoryScreen(app)
    rows = list(form.records.values())
    assert [r.reason for r in rows] == [
        "Held cancellation",
        "Customer left",
        "Wrong item",
    ]
    assert rows[0].user_id != original_actor
    assert rows[1].user_id == original_actor
    assert all(r.product_name == "Cat Feather Wand" for r in rows)
    assert [r.scope for r in rows] == ["transaction", "transaction", "line"]
    for row in rows:
        form.tree.selection_set(str(row.id))
        form.show_selected()
        assert form.detail.get("1.0", "end-1c") == row.reason
    form.refresh()
    form.destroy()
    assert snapshot() == before


def test_owner_page_layout_live_theme_and_full_reason(app, session_factory):
    add_records(session_factory)
    form = owner_screen(app, "Void History")
    app.state("normal")
    app.geometry("1280x720+0+0")
    selected = form.tree.get_children()[0]
    form.tree.selection_set(selected)
    form.show_selected()
    reason = form.records[int(selected)].reason
    for theme in ("cosmo", "darkly"):
        app.apply_theme(theme)
        app.update()
        assert form.tree.selection() == (selected,)
        assert form.detail.get("1.0", "end-1c") == reason
        assert form.detail.cget("yscrollcommand")
        assert form.tree.cget("xscrollcommand")
        assert form.tree.cget("yscrollcommand")
        for widget in (form.detail, form.tree, form.refresh_button, *form.date_pickers):
            assert widget.winfo_ismapped()
            assert (
                widget.winfo_rootx() + widget.winfo_width()
                <= app.winfo_rootx() + app.winfo_width()
            )
            assert (
                widget.winfo_rooty() + widget.winfo_height()
                <= app.winfo_rooty() + app.winfo_height()
            )


@pytest.mark.parametrize("role", ["cashier", "owner"])
@pytest.mark.parametrize("theme", ["cosmo", "darkly"])
def test_modal_layout_keys_and_preserves_pos(app, role, theme):
    pos = cashier_pos(app) if role == "cashier" else owner_screen(app, "POS")
    app.state("normal")
    app.geometry("1280x720+0+0")
    app.apply_theme(theme)
    pos.add_product(by_name(pos, "Cat Feather Wand").id)
    pos.customer = customer_service.create_customer("Modal customer")
    pos.last_sale = object()
    before = (pos.cart.lines, pos.customer, pos.last_sale)
    pos.search_entry.focus_force()
    app.update()
    checked = []

    def interact():
        dialog = next(
            w for w in pos.winfo_children() if isinstance(w, VoidHistoryDialog)
        )
        if dialog.focus_get() is not dialog.first_input:
            app.after(10, interact)
            return
        assert dialog.grab_current() is dialog
        form = dialog.form
        for widget in (
            form.refresh_button,
            form.detail,
            form.tree,
            *form.date_pickers,
            pos.void_history_button,
            app.screen.buttons["Void History"] if role == "owner" else pos.search_entry,
        ):
            top = widget.winfo_toplevel()
            assert widget.winfo_ismapped()
            assert widget.winfo_rootx() >= top.winfo_rootx()
            assert widget.winfo_rooty() >= top.winfo_rooty()
            assert (
                widget.winfo_rootx() + widget.winfo_width()
                <= top.winfo_rootx() + top.winfo_width()
            )
            assert (
                widget.winfo_rooty() + widget.winfo_height()
                <= top.winfo_rooty() + top.winfo_height()
            )
        with patch.object(pos, "hold_current") as hold:
            assert pos.shortcut(None, hold) is None
            assert not hold.called
        dialog.first_input.event_generate("<Escape>")
        checked.append(True)

    app.after(150, interact)
    cleanup = app.after(
        4000,
        lambda: [
            w.destroy()
            for w in pos.winfo_children()
            if isinstance(w, VoidHistoryDialog)
        ],
    )
    pos.void_history_button.invoke()
    app.after_cancel(cleanup)
    restored = tk.BooleanVar(app)
    app.after(200, lambda: restored.set(True))
    app.wait_variable(restored)
    assert checked
    assert pos.focus_get() is pos.search_entry
    assert pos.grab_current() is None
    assert (pos.cart.lines, pos.customer, pos.last_sale) == before
