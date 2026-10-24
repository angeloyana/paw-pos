import tkinter as tk
from unittest.mock import patch

import pytest
from matplotlib.colors import to_hex

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError
from pawpos.services import auth_service, customer_service, settings_service
from pawpos.ui.settings_screen import SettingsDialog, SettingsScreen
from tests.test_catalog_ui import owner_screen
from tests.test_pos_ui import by_name, cashier_pos


def fill_password(form, current="owner123", new="new-password", confirmation=None):
    form.current_password.set(current)
    form.new_password.set(new)
    form.confirmation.set(new if confirmation is None else confirmation)


def test_owner_settings_preserves_pos_and_restores_theme_on_login(app):
    pos = owner_screen(app, "POS")
    pos.add_product(by_name(pos, "Cat Feather Wand").id)
    pos.customer = customer_service.create_customer("Customer")
    pos.last_sale = object()
    before = (pos.cart.lines, pos.customer, pos.last_sale)
    app.screen.buttons["Settings"].invoke()
    app.update()
    form = app.screen.current_screen
    assert isinstance(form, SettingsScreen)
    assert str(form.theme_selector.cget("state")) == "readonly"
    assert set(form.theme_selector.cget("values")) == set(
        settings_service.theme_names()
    )
    form.theme.set("darkly")
    form.apply_button.invoke()
    app.update()
    assert app.style.theme_use() == "darkly"
    assert pos.canvas.cget("background") == app.style.colors.bg
    app.screen.buttons["POS"].invoke()
    app.update()
    assert app.screen.current_screen is pos
    assert (pos.cart.lines, pos.customer, pos.last_sale) == before
    app.show_login()
    assert app.style.theme_use() == "cosmo"
    app.show_workspace(auth_service.login("cashier", "cashier123"))
    assert app.style.theme_use() == "cosmo"
    app.show_login()
    app.show_workspace(auth_service.login("owner", "owner123"))
    app.update()
    assert app.style.theme_use() == "darkly"
    chart = app.screen.current_screen.daily_chart
    assert to_hex(chart.figure.get_facecolor()) == app.style.colors.bg.lower()


def test_theme_write_failure_and_read_retry(app):
    form = owner_screen(app, "Settings")
    form.theme.set("darkly")
    with patch.object(settings_service, "set_theme", side_effect=RuntimeError("DB")):
        form.apply_button.invoke()
    assert app.style.theme_use() == "cosmo"
    assert settings_service.get_settings().theme == "cosmo"
    assert form.theme.get() == "darkly" and "Cannot complete" in form.status.get()
    with patch.object(settings_service, "get_settings", side_effect=RuntimeError("DB")):
        form.reload_button.invoke()
    assert form.theme.get() == "darkly" and "Cannot complete" in form.status.get()
    form.reload_button.invoke()
    assert form.theme.get() == "cosmo"


def test_password_errors_preserve_input_success_clears_and_keeps_session(app):
    form = owner_screen(app, "Settings")
    identity = login_session.current_user
    assert all(entry.cget("show") == "•" for entry in form.password_entries)
    fill_password(form, current="wrong")
    form.change_button.invoke()
    assert "Current password" in form.status.get()
    assert form.new_password.get() == "new-password"
    fill_password(form, confirmation="mismatch")
    form.change_button.invoke()
    assert "do not match" in form.status.get()
    fill_password(form)
    with patch.object(auth_service, "change_password", side_effect=RuntimeError("DB")):
        form.change_button.invoke()
    assert form.current_password.get() == "owner123"
    form.change_button.invoke()
    assert form.status.get() == "Password changed."
    assert not any(
        field.get()
        for field in (form.current_password, form.new_password, form.confirmation)
    )
    assert login_session.current_user == identity
    assert settings_service.get_settings().theme == "cosmo"
    with pytest.raises(AuthError):
        auth_service.login("owner", "owner123")
    assert auth_service.login("owner", "new-password") == identity


def test_cashier_modal_entry_focus_escape_and_pos_state(app):
    pos = cashier_pos(app)
    pos.add_product(by_name(pos, "Cat Feather Wand").id)
    pos.customer = customer_service.create_customer("Customer")
    pos.last_sale = object()
    before = (pos.cart.lines, pos.customer, pos.last_sale)
    pos.search_entry.focus_force()
    app.update()
    checked = []

    def interact():
        dialog = next(w for w in pos.winfo_children() if isinstance(w, SettingsDialog))
        form = dialog.form
        assert dialog.grab_current() is dialog
        assert dialog.focus_get() is dialog.first_input
        form.theme.set("darkly")
        form.apply_button.invoke()
        fill_password(form, current="cashier123")
        form.change_button.invoke()
        assert form.status.get() == "Password changed."
        # Root shortcuts must not act while focus is in Settings.
        with patch.object(pos, "hold_current") as hold:
            form.theme_selector.event_generate("<F4>")
            assert pos.shortcut(None, hold) is None
            assert not hold.called
        app.update()
        assert form.change_button.winfo_rooty() + form.change_button.winfo_height() < (
            dialog.winfo_rooty() + dialog.winfo_height()
        )
        form.theme_selector.event_generate("<Escape>")
        checked.append(True)

    app.after(150, interact)
    # Prevent a failed callback assertion from leaving wait_window blocked.
    cleanup = app.after(
        4000,
        lambda: [
            w.destroy() for w in pos.winfo_children() if isinstance(w, SettingsDialog)
        ],
    )
    pos.settings_button.invoke()
    app.after_cancel(cleanup)
    # Window-manager focus restoration completes asynchronously on X11.
    restored = tk.BooleanVar(app)
    app.after(200, lambda: restored.set(True))
    app.wait_variable(restored)
    assert checked
    assert pos.focus_get() is pos.search_entry
    assert (pos.cart.lines, pos.customer, pos.last_sale) == before
    assert app.style.theme_use() == "darkly"
    assert login_session.current_user.username == "cashier"
    assert auth_service.login("cashier", "new-password").role == "cashier"


def test_all_builtin_themes_restyle_charts_without_replacing_canvas(app):
    dashboard = owner_screen(app, "Dashboard")
    chart = dashboard.daily_chart
    canvas = chart.canvas
    for theme in settings_service.theme_names():
        app.apply_theme(theme)
        app.update()
        assert app.style.theme_use() == theme
        assert chart.canvas is canvas
        assert to_hex(chart.figure.get_facecolor()) == app.style.colors.bg.lower()
        assert to_hex(chart.axes.get_facecolor()) == app.style.colors.bg.lower()
        assert to_hex(chart.axes.patches[0].get_facecolor()) == (
            app.style.colors.primary.lower()
        )
    app.apply_theme("unsupported")
    assert app.style.theme_use() == "cosmo"


def test_login_theme_read_failure_is_visible_and_retryable(app):
    identity = auth_service.login("cashier", "cashier123")
    with patch.object(settings_service, "get_settings", side_effect=RuntimeError("DB")):
        app.show_workspace(identity)
    assert "Settings to retry" in app.screen.status.get()
    assert app.style.theme_use() == "cosmo"
    dialog = SettingsDialog(app.screen)
    assert dialog.form.theme.get() == "cosmo"
    assert "Cannot" not in dialog.form.status.get()
    dialog.destroy()


def test_owner_settings_controls_fit_minimum_window_and_navigation_clears_secrets(app):
    app.geometry("1280x720")
    form = owner_screen(app, "Settings")
    fill_password(form)
    app.update()
    assert form.change_button.winfo_rooty() + form.change_button.winfo_height() <= (
        app.winfo_rooty() + app.winfo_height()
    )
    app.screen.buttons["Dashboard"].invoke()
    assert form.current_password.get() == ""
    assert form.new_password.get() == ""
