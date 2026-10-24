from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError, ValidationError
from pawpos.db import base
from pawpos.db.seed import seed_database
from pawpos.models import User, UserSettings
from pawpos.services import auth_service, settings_service


@pytest.fixture
def accounts(session_factory):
    seed_database()
    return session_factory


def test_theme_is_per_account_and_survives_seed(accounts):
    auth_service.login("owner", "owner123")
    assert settings_service.get_settings().theme == "cosmo"
    assert settings_service.set_theme("darkly").theme == "darkly"
    auth_service.login("cashier", "cashier123")
    assert settings_service.get_settings().theme == "cosmo"
    settings_service.set_theme("flatly")
    assert seed_database() is False
    auth_service.login("owner", "owner123")
    assert settings_service.get_settings().theme == "darkly"
    with accounts() as session:
        assert len(session.scalars(select(UserSettings)).all()) == 2


def test_unknown_saved_theme_defaults_and_invalid_save_preserves_value(accounts):
    owner = auth_service.login("owner", "owner123")
    with accounts.begin() as session:
        session.add(UserSettings(user_id=owner.id, theme="retired"))
    assert settings_service.get_settings().theme == "cosmo"
    for theme in ("retired", "", None, ["cosmo"]):
        with pytest.raises(ValidationError):
            settings_service.set_theme(theme)
    with accounts() as session:
        assert session.get(UserSettings, owner.id).theme == "retired"


@pytest.mark.parametrize("username", ["owner", "cashier"])
def test_password_change_keeps_session_and_changes_only_current_account(
    accounts, username
):
    current = f"{username}123"
    identity = auth_service.login(username, current)
    auth_service.change_password(current, "new-password", "new-password")
    assert login_session.current_user == identity
    with pytest.raises(AuthError):
        auth_service.login(username, current)
    assert auth_service.login(username, "new-password") == identity
    other = "cashier" if username == "owner" else "owner"
    assert auth_service.login(other, f"{other}123").username == other


@pytest.mark.parametrize(
    "current,new,confirmation,message",
    [
        ("wrong", "new", "new", "Current password"),
        ("owner123", "new", "different", "do not match"),
        ("owner123", "", "", "required"),
        ("owner123", "  ", "  ", "required"),
        ("owner123", "🐾" * 19, "🐾" * 19, "72 UTF-8 bytes"),
    ],
)
def test_password_validation_preserves_existing_password(
    accounts, current, new, confirmation, message
):
    auth_service.login("owner", "owner123")
    with pytest.raises(ValidationError, match=message):
        auth_service.change_password(current, new, confirmation)
    assert auth_service.login("owner", "owner123").role == "owner"


@pytest.mark.parametrize("actor", [None, "owner", "cashier"])
def test_settings_and_password_recheck_active_access(accounts, actor):
    if actor:
        user = auth_service.login(actor, f"{actor}123")
        with accounts.begin() as session:
            session.get(User, user.id).is_active = False
    for operation in (
        settings_service.get_settings,
        lambda: settings_service.set_theme("darkly"),
        lambda: auth_service.change_password("owner123", "new", "new"),
    ):
        with pytest.raises(AuthError):
            operation()


def test_write_failures_roll_back_password_and_theme(accounts, monkeypatch):
    auth_service.login("owner", "owner123")
    settings_service.set_theme("cosmo")

    @contextmanager
    def failing_scope():
        with accounts() as session, session.begin():
            yield session
            session.flush()
            raise RuntimeError("Commit failed")

    with monkeypatch.context() as changes:
        changes.setattr(settings_service, "session_scope", failing_scope)
        changes.setattr(auth_service, "session_scope", failing_scope)
        with pytest.raises(RuntimeError):
            settings_service.set_theme("darkly")
        with pytest.raises(RuntimeError):
            auth_service.change_password("owner123", "new", "new")
    assert settings_service.get_settings().theme == "cosmo"
    assert auth_service.login("owner", "owner123").role == "owner"


def test_theme_survives_database_reopen(tmp_path, monkeypatch):
    url = f"sqlite+pysqlite:///{tmp_path / 'settings.db'}"
    engine = create_engine(url)
    base.init_db(engine)
    monkeypatch.setattr(base, "SessionLocal", sessionmaker(bind=engine))
    seed_database()
    auth_service.login("cashier", "cashier123")
    settings_service.set_theme("darkly")
    auth_service.logout()
    engine.dispose()
    reopened = create_engine(url)
    try:
        monkeypatch.setattr(base, "SessionLocal", sessionmaker(bind=reopened))
        auth_service.login("cashier", "cashier123")
        assert settings_service.get_settings().theme == "darkly"
    finally:
        auth_service.logout()
        reopened.dispose()
