from pawpos.services import auth_service
from pawpos.ui.dialogs.customer_picker import CustomerPicker
from tests.test_catalog_ui import owner_screen


def test_shortcut_tooltips_close_and_cancel_pending_hover_on_navigation(app):
    pos = owner_screen(app, "POS")
    for widget, shortcut in (
        (pos.search_entry, "F2"),
        (pos.hold_button, "F4"),
        (pos.pay_button, "F5"),
        (pos.void_button, "F6"),
        (pos.held_button, "F8"),
        (pos.edit_button, "Enter"),
        (pos.remove_button, "Delete"),
    ):
        assert shortcut in widget.tooltip.text
    pos.hold_button.tooltip.show_tip()
    app.update()
    assert pos.hold_button.tooltip.toplevel.winfo_exists()
    pos.pay_button.tooltip.schedule()
    app.screen.buttons["Dashboard"].invoke()
    app.update()
    assert pos.hold_button.tooltip.toplevel is None
    assert pos.pay_button.tooltip.id is None
    # A pending hover must also be cancelled when logging out destroys the POS.
    app.screen.buttons["POS"].invoke()
    app.update()
    tooltip = pos.pay_button.tooltip
    tooltip.schedule()
    app.screen.logout_button.invoke()
    app.update()
    assert tooltip.id is None and tooltip.toplevel is None


def test_customer_picker_explains_empty_results_and_walkin(app):
    app.show_workspace(auth_service.login("cashier", "cashier123"))
    picker = CustomerPicker(app.screen)
    assert "No saved customers" in picker.message.get()
    picker.search.set("Missing")
    assert "No customers match" in picker.message.get()
    picker.walk_in()
    assert picker.result is False
