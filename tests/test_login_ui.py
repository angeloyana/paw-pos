from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError

from pawpos.core import session as login_session
from pawpos.services import auth_service, user_service
from pawpos.ui.login_screen import LoginScreen
from pawpos.ui.owner.shell import OwnerShell
from pawpos.ui.placeholder_screen import PlaceholderScreen


@pytest.mark.parametrize(
    "username,password,heading",
    [
        ("owner", "owner123", "Owner dashboard"),
        ("cashier", "cashier123", "Cashier POS"),
    ],
)
def test_login_routes_by_role_and_logout_clears_state(app, username, password, heading):
    form = app.screen
    assert isinstance(form, LoginScreen)
    form.username.set(username)
    form.password.set(password)
    form.login_button.invoke()
    app.update()
    assert isinstance(
        app.screen, OwnerShell if username == "owner" else PlaceholderScreen
    )
    assert app.screen.heading == heading
    assert login_session.current_user.username == username
    app.screen.logout_button.invoke()
    app.update()
    assert isinstance(app.screen, LoginScreen)
    assert app.screen.username.get() == ""
    assert app.screen.password.get() == ""
    assert login_session.current_user is None


def test_wrong_password_and_disabled_user_stay_on_login(app):
    form = app.screen
    form.username.set("cashier")
    form.password.set("wrong")
    form.login_button.invoke()
    assert app.screen is form
    assert "Incorrect" in form.error.get()
    assert form.password.get() == ""
    auth_service.login("owner", "owner123")
    user_service.set_active(2, False)
    auth_service.logout()
    form.password.set("cashier123")
    form.login_button.invoke()
    assert app.screen is form
    assert "disabled" in form.error.get()
    assert login_session.current_user is None


def test_unexpected_error_is_generic_and_login_can_be_retried(app):
    form = app.screen
    form.username.set("owner")
    form.password.set("owner123")
    with patch(
        "pawpos.ui.login_screen.auth_service.login",
        side_effect=OperationalError("", {}, Exception("private detail")),
    ):
        form.login_button.invoke()
    assert "Cannot sign in" in form.error.get()
    assert "private detail" not in form.error.get()
    assert str(form.login_button.cget("state")) == "normal"
    assert form.password.get() == ""
    form.password.set("owner123")
    form.login_button.invoke()
    assert isinstance(app.screen, OwnerShell)


def test_closing_window_clears_login_state(app):
    auth_service.login("owner", "owner123")
    app.close()
    assert login_session.current_user is None
