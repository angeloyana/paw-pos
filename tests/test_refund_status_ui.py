from unittest.mock import patch

from sqlalchemy import event

from pawpos.services import auth_service, refund_service
from pawpos.services import refund_tracking_service as tracking
from pawpos.ui.dialogs.refund_status import PayoutDialog, RefundStatusDialog
from tests.test_catalog_ui import owner_screen
from tests.test_refund_ui import sale, submit_request


def reviewed(app, *, reject=False):
    completed, toy, _ = sale(app)
    result = submit_request(app, completed)
    auth_service.login("owner", "owner123")
    if reject:
        refund_service.reject(result.id, "Wrong item")
    else:
        refund_service.approve(result.id, {item.id: False for item in result.items})
    app.show_workspace(auth_service.login("cashier", "cashier123"))
    app.update()
    return result, toy


def select(app, dialog, request_id):
    dialog.tree.selection_set(str(request_id))
    # Tree events are delivered even while withdrawn; select explicitly too.
    dialog.select()
    app.update()
    assert dialog.selected.request.id == request_id


def test_cashier_notices_details_payout_and_cart_preserved(app):
    result, toy = reviewed(app)
    pos = app.screen
    pos.add_product(toy.id)
    cart = pos.cart.lines
    pos.refresh_refund_notices()
    assert "approved" in pos.refund_notice.get()
    assert "1 unread" in pos.refund_status_button.cget("text")
    dialog = RefundStatusDialog(pos, unread_only=True)
    select(app, dialog, result.id)
    assert tracking.unread_notices() == []
    assert "Shop Owner" in dialog.detail.get("1.0", "end")
    assert dialog.payout_button.instate(["!disabled"])
    assert not dialog.correct_button.winfo_ismapped()

    def pay(window):
        window.method.set("gcash")
        window.reference.set("GC-123")
        window.save()
        return window.result

    with (
        patch.object(PayoutDialog, "show", pay),
        patch("pawpos.ui.dialogs.refund_status.messagebox.askyesno", return_value=True),
    ):
        dialog.payout_button.invoke()
    assert not dialog.error.get()
    assert dialog.selected is None
    assert tracking.get_refund(result.id).payout.reference == "GC-123"
    assert pos.cart.lines == cart
    dialog.destroy()
    pos.refresh_refund_notices()
    assert pos.refund_status_button.cget("text") == "Refunds"


def test_rejected_decision_and_filters(app):
    result, _ = reviewed(app, reject=True)
    dialog = RefundStatusDialog(app.screen)
    select(app, dialog, result.id)
    assert "Wrong item" in dialog.detail.get("1.0", "end")
    assert dialog.payout_button.instate(["disabled"])
    dialog.filter.set("Approved — awaiting payout")
    dialog.refresh()
    assert dialog.tree.get_children() == ()
    dialog.filter.set("Rejected")
    dialog.receipt.set("%")
    dialog.refresh()
    assert not dialog.tree.get_children()
    dialog.receipt.set(result.receipt_number)
    dialog.refresh()
    assert dialog.tree.get_children() == (str(result.id),)
    dialog.destroy()


def test_payout_validation_cancellation_and_failed_save_retain_inputs(
    app, session_factory
):
    result, _ = reviewed(app)
    dialog = PayoutDialog(app.screen, tracking.get_refund(result.id))
    dialog.method.set("gcash")
    with patch("pawpos.ui.dialogs.refund_status.messagebox.askyesno") as confirm:
        dialog.save()
    confirm.assert_not_called()
    assert "reference is required" in dialog.error.get()
    dialog.reference.set("REF")
    with patch(
        "pawpos.ui.dialogs.refund_status.messagebox.askyesno", return_value=False
    ):
        dialog.save()
    assert dialog.winfo_exists() and dialog.result is None

    def fail(_session):
        raise RuntimeError("Cannot commit")

    event.listen(session_factory, "before_commit", fail)
    try:
        with patch(
            "pawpos.ui.dialogs.refund_status.messagebox.askyesno", return_value=True
        ):
            dialog.save()
    finally:
        event.remove(session_factory, "before_commit", fail)
    assert dialog.result is None and dialog.reference.get() == "REF"
    assert tracking.get_refund(result.id).status == "awaiting_payout"
    dialog.destroy()


def test_saved_payout_refresh_failure_disables_repeat_actions(app):
    result, _ = reviewed(app)
    dialog = RefundStatusDialog(app.screen)
    select(app, dialog, result.id)

    def pay(window):
        window.save()
        return window.result

    with (
        patch.object(PayoutDialog, "show", pay),
        patch("pawpos.ui.dialogs.refund_status.messagebox.askyesno", return_value=True),
        patch.object(tracking, "list_refunds", side_effect=RuntimeError("Read failed")),
    ):
        dialog.payout_button.invoke()
    assert "Payment details saved" in dialog.error.get()
    assert dialog.selected is None and dialog.payout_button.instate(["disabled"])
    assert tracking.get_refund(result.id).status == "paid"
    dialog.destroy()


def test_stale_unpaid_selection_cannot_record_again(app):
    result, _ = reviewed(app)
    dialog = RefundStatusDialog(app.screen)
    select(app, dialog, result.id)
    tracking.record_payout(result.id, "cash")
    with patch.object(PayoutDialog, "show") as payout:
        dialog.payout_button.invoke()
    payout.assert_not_called()
    assert "status changed" in dialog.error.get()
    assert dialog.payout_button.instate(["disabled"])
    dialog.destroy()


def test_owner_opens_payment_details_and_corrects_with_audit(app):
    result, _ = reviewed(app)
    tracking.record_payout(result.id, "cash")
    screen = owner_screen(app, "Refunds")
    dialog = RefundStatusDialog(screen, owner=True, initial_id=result.id)
    select(app, dialog, result.id)
    assert dialog.correct_button.instate(["!disabled"])

    def correct(window):
        window.method.set("gcash")
        window.reference.set("CORRECT")
        window.reason.set("Wrong method")
        window.save()
        return window.result

    with (
        patch.object(PayoutDialog, "show", correct),
        patch("pawpos.ui.dialogs.refund_status.messagebox.askyesno", return_value=True),
    ):
        dialog.correct_button.invoke()
    select(app, dialog, result.id)
    assert "Correction by Shop Owner" in dialog.detail.get("1.0", "end")
    assert "Wrong method" in dialog.detail.get("1.0", "end")
    assert "recorded by Cashier" in dialog.detail.get("1.0", "end")
    dialog.destroy()
    with patch.object(RefundStatusDialog, "show", lambda window: window.destroy()):
        screen.payouts_button.invoke()


def test_refresh_failure_retains_rows_and_notice_count_then_recovers(app):
    result, _ = reviewed(app)
    pos = app.screen
    dialog = RefundStatusDialog(pos)
    rows = dialog.tree.get_children()
    with patch.object(
        tracking, "list_refunds", side_effect=RuntimeError("Read failed")
    ):
        dialog.refresh()
    assert dialog.tree.get_children() == rows
    with patch.object(
        tracking, "unread_notices", side_effect=RuntimeError("Read failed")
    ):
        pos.refresh_refund_notices()
    assert "1 unread" in pos.refund_status_button.cget("text")
    assert "retry" in pos.refund_notice.get()
    pos.notice_retry.invoke()
    assert "approved" in pos.refund_notice.get()
    dialog.destroy()


def test_notice_poll_is_cancelled_on_logout(app):
    reviewed(app)
    pos = app.screen
    scheduled = pos._notice_after
    assert scheduled in app.tk.call("after", "info")
    pos.logout_button.invoke()
    app.update()
    assert scheduled not in app.tk.call("after", "info")
    assert pos._notice_after is None


def test_status_dialog_fits_minimum_size_and_escape_closes(app):
    reviewed(app)
    dialog = RefundStatusDialog(app.screen)
    dialog.geometry("850x550")

    def close():
        assert (
            dialog.payout_button.winfo_rooty() + dialog.payout_button.winfo_height()
            <= dialog.winfo_rooty() + dialog.winfo_height()
        )
        dialog.event_generate("<Escape>")

    app.after(200, close)
    assert dialog.show() is None


def test_scheduled_notice_poll_detects_decision_without_reopening_workspace(app):
    completed, _, _ = sale(app)
    result = submit_request(app, completed)
    pos = app.screen
    assert pos.refund_status_button.cget("text") == "Refunds"
    auth_service.login("owner", "owner123")
    refund_service.approve(result.id, {item.id: False for item in result.items})
    auth_service.login("cashier", "cashier123")
    scheduled = pos._notice_after
    script, _kind = app.tk.call("after", "info", scheduled)
    app.tk.call("after", "cancel", scheduled)
    app.tk.call(script)
    assert "approved" in pos.refund_notice.get()
    assert "1 unread" in pos.refund_status_button.cget("text")
    assert pos._notice_after != scheduled
    assert pos._notice_after in app.tk.call("after", "info")
