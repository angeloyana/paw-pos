from unittest.mock import patch

import pytest

from pawpos.core.errors import AuthError
from pawpos.services import auth_service, user_service
from tests.test_catalog_ui import owner_screen, select


def add_cashier(screen, username="newcashier", password="first-pass"):
    screen.new()
    screen.username.set(username)
    screen.full_name.set("New Cashier")
    screen.password.set(password)
    screen.create_button.invoke()


def test_owner_create_cashier_disable_enable_and_reset_login(app):
    screen = owner_screen(app, "Users")
    add_cashier(screen)
    assert screen.status.get() == "Cashier created."
    assert screen.password.get() == ""
    cashier = next(
        user for user in user_service.list_users() if user.username == "newcashier"
    )
    select(app, screen, cashier.id)
    assert screen.username_entry.instate(["disabled"])
    with patch("pawpos.ui.owner.users.messagebox.askyesno", return_value=False):
        screen.toggle_button.invoke()
    assert next(
        user for user in user_service.list_users() if user.id == cashier.id
    ).is_active
    with patch("pawpos.ui.owner.users.messagebox.askyesno", return_value=True):
        screen.toggle_button.invoke()
    with pytest.raises(AuthError, match="disabled"):
        auth_service.login("newcashier", "first-pass")
    auth_service.login("owner", "owner123")
    select(app, screen, cashier.id)
    assert screen.toggle_button.cget("text") == "Enable cashier"
    screen.toggle_button.invoke()
    select(app, screen, cashier.id)
    screen.password.set("second-pass")
    screen.reset_button.invoke()
    assert screen.status.get() == "Password reset." and screen.password.get() == ""
    with pytest.raises(AuthError):
        auth_service.login("newcashier", "first-pass")
    assert auth_service.login("newcashier", "second-pass").id == cashier.id


def test_owner_disable_blocked_and_own_password_reset_available(app):
    screen = owner_screen(app, "Users")
    owner = next(user for user in user_service.list_users() if user.role == "owner")
    select(app, screen, owner.id)
    assert screen.toggle_button.instate(["disabled"])
    assert not screen.reset_button.instate(["disabled"])
    # Service protection also applies if the UI method is invoked directly.
    with patch("pawpos.ui.owner.users.messagebox.askyesno", return_value=True):
        screen.toggle_active()
    assert "own account" in screen.status.get()
    assert next(
        user for user in user_service.list_users() if user.id == owner.id
    ).is_active
    screen.password.set("changed-owner-pass")
    screen.reset_button.invoke()
    assert auth_service.login("owner", "changed-owner-pass").id == owner.id


def test_invalid_and_duplicate_creation_preserve_form_and_mask_password(app):
    screen = owner_screen(app, "Users")
    screen.username.set("newcashier")
    screen.password.set("keep-pass")
    screen.create_button.invoke()
    assert "Full name" in screen.status.get()
    assert (
        screen.username.get() == "newcashier" and screen.password.get() == "keep-pass"
    )
    assert screen.password_entry.cget("show") == "•"
    screen.username.set("OWNER")
    screen.full_name.set("Duplicate")
    screen.create_button.invoke()
    assert "already in use" in screen.status.get()
    assert len(user_service.list_users()) == 2
    assert "password" not in screen.tree.cget("columns")


def test_failed_reset_preserves_input_and_blank_reset_is_rejected(app):
    screen = owner_screen(app, "Users")
    cashier = next(user for user in user_service.list_users() if user.role == "cashier")
    select(app, screen, cashier.id)
    screen.reset_button.invoke()
    assert "Password is required" in screen.status.get()
    screen.password.set("keep-input")
    with patch.object(
        user_service, "reset_password", side_effect=RuntimeError("Write failed")
    ):
        screen.reset_button.invoke()
    assert screen.password.get() == "keep-input" and screen.user_id == cashier.id
    assert auth_service.login("cashier", "cashier123").id == cashier.id


def test_saved_account_refresh_failure_clears_password_and_prevents_duplicate(app):
    screen = owner_screen(app, "Users")
    with patch.object(screen, "_load", side_effect=RuntimeError("Read failed")):
        add_cashier(screen)
    assert "Cashier created" in screen.status.get()
    assert screen.password.get() == "" and screen.username.get() == ""
    screen.create_button.invoke()
    assert len(user_service.list_users()) == 3


def test_user_controls_scroll_into_view_at_minimum_window(app):
    app.geometry("1280x720")
    screen = owner_screen(app, "Users")
    screen.form_canvas.yview_moveto(1)
    app.update()
    assert (
        screen.reset_button.winfo_rooty() + screen.reset_button.winfo_height()
        <= screen.form_canvas.winfo_rooty() + screen.form_canvas.winfo_height()
    )
