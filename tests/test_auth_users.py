from dataclasses import asdict

import pytest
from sqlalchemy import MetaData, String, create_engine, select
from sqlalchemy.orm import sessionmaker

from pawpos.core import session as login_session
from pawpos.core.errors import (
    AuthError,
    BusinessRuleError,
    NotFoundError,
    ValidationError,
)
from pawpos.core.security import hash_password
from pawpos.db import base
from pawpos.db.seed import seed_database
from pawpos.models import User
from pawpos.services import auth_service, user_service


@pytest.fixture
def accounts(session_factory):
    seed_database()
    return session_factory


@pytest.mark.parametrize(
    "username,password,role",
    [
        ("owner", "owner123", "owner"),
        ("cashier", "cashier123", "cashier"),
        (" owner ", "owner123", "owner"),
    ],
)
def test_login_returns_detached_identity_without_hash(
    accounts, username, password, role
):
    identity = auth_service.login(username, password)
    assert identity.role == role
    assert login_session.current_user == identity
    assert "password_hash" not in asdict(identity)
    auth_service.logout()
    assert login_session.current_user is None


@pytest.mark.parametrize(
    "username,password",
    [
        ("owner", "wrong"),
        ("OWNER", "owner123"),
        ("Owner", "owner123"),
        (" OWNER ", "owner123"),
        ("missing", "owner123"),
        ("", ""),
        ("owner", "a" * 73),
        (None, "owner123"),
        ("owner", None),
    ],
)
def test_failed_login_leaves_no_previous_identity(accounts, username, password):
    auth_service.login("owner", "owner123")
    with pytest.raises(AuthError):
        auth_service.login(username, password)
    assert login_session.current_user is None


def test_cashier_create_disable_enable_and_password_reset(accounts):
    auth_service.login("owner", "owner123")
    cashier = user_service.create_cashier(" NewCashier ", " New Person ", "first-pass")
    assert cashier.username == "NewCashier"
    assert cashier.full_name == "New Person"
    assert cashier.role == "cashier" and cashier.is_active
    assert "password_hash" not in asdict(cashier)
    assert len(user_service.list_users()) == 3
    user_service.set_active(cashier.id, False)
    with pytest.raises(AuthError, match="disabled"):
        auth_service.login("NewCashier", "first-pass")
    auth_service.login("owner", "owner123")
    user_service.set_active(cashier.id, True)
    user_service.reset_password(cashier.id, "second-pass")
    with pytest.raises(AuthError):
        auth_service.login("NewCashier", "first-pass")
    assert auth_service.login("NewCashier", "second-pass").id == cashier.id


def test_mixed_case_username_requires_exact_case_and_trims_whitespace(accounts):
    auth_service.login("owner", "owner123")
    cashier = user_service.create_cashier(" Alice ", "Alice", "first-pass")
    assert cashier.username == "Alice"
    with accounts() as session:
        assert session.get(User, cashier.id).username == "Alice"
    for username in ("alice", "ALICE"):
        assert auth_service.login(" Alice ", "first-pass").id == cashier.id
        with pytest.raises(AuthError, match="^Incorrect username or password\\.$"):
            auth_service.login(username, "first-pass")
        assert login_session.current_user is None


@pytest.mark.parametrize(
    "existing,duplicate",
    [("Alice", "alice"), ("Alice", "ALICE"), ("Straße", "STRASSE")],
)
def test_casefold_duplicate_creation_leaves_original_account_unchanged(
    accounts, existing, duplicate
):
    auth_service.login("owner", "owner123")
    cashier = user_service.create_cashier(existing, "Original", "first-pass")
    with pytest.raises(ValidationError, match="Username is already in use"):
        user_service.create_cashier(duplicate, "Duplicate", "other-pass")
    assert len(user_service.list_users()) == 3
    assert auth_service.login(existing, "first-pass").id == cashier.id


@pytest.mark.parametrize("stored,incorrect", [("owner", "OWNER"), ("Owner", "owner")])
def test_login_rejects_case_mismatch_with_case_insensitive_database(
    monkeypatch, stored, incorrect
):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    table = User.__table__.to_metadata(MetaData())
    table.c.username.type = String(50, collation="NOCASE")
    table.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(base, "SessionLocal", factory)
    try:
        with factory.begin() as session:
            session.add(
                User(
                    username=stored,
                    full_name="Owner",
                    role="owner",
                    password_hash=hash_password("first-pass"),
                )
            )
        with factory() as session:
            assert (
                session.scalar(select(User.username).where(User.username == incorrect))
                == stored
            )
        assert auth_service.login(stored, "first-pass").username == stored
        with pytest.raises(AuthError, match="^Incorrect username or password\\.$"):
            auth_service.login(incorrect, "first-pass")
        assert login_session.current_user is None
    finally:
        auth_service.logout()
        engine.dispose()


@pytest.mark.parametrize("actor", [None, "cashier", "disabled-owner"])
def test_account_management_rejects_nonowners_and_disabled_owners(accounts, actor):
    if actor:
        auth_service.login(
            "owner" if actor == "disabled-owner" else actor,
            "owner123" if actor == "disabled-owner" else "cashier123",
        )
    if actor == "disabled-owner":
        with accounts.begin() as session:
            session.scalar(
                select(User).where(User.username == "owner")
            ).is_active = False
    for operation in (
        lambda: user_service.create_cashier("forbidden", "Forbidden", "password"),
        user_service.list_users,
        lambda: user_service.set_active(2, False),
        lambda: user_service.reset_password(2, "changed"),
    ):
        with pytest.raises(AuthError):
            operation()
    with accounts() as session:
        assert session.scalar(select(User).where(User.username == "forbidden")) is None
        assert session.get(User, 2).is_active


def test_owner_cannot_disable_self_and_can_change_seeded_password(accounts):
    owner = auth_service.login("owner", "owner123")
    with pytest.raises(BusinessRuleError, match="own account"):
        user_service.set_active(owner.id, False)
    user_service.reset_password(owner.id, "new-owner-password")
    assert auth_service.login("owner", "new-owner-password").id == owner.id


@pytest.mark.parametrize(
    "username,full_name,password",
    [
        ("OWNER", "Duplicate", "password"),
        ("", "Name", "password"),
        ("a" * 51, "Name", "password"),
        ("new", "", "password"),
        ("new", "N" * 101, "password"),
        ("new", "Name", ""),
        ("new", "Name", "🐾" * 19),
    ],
)
def test_invalid_creation_leaves_database_unchanged(
    accounts, username, full_name, password
):
    auth_service.login("owner", "owner123")
    with pytest.raises(ValidationError):
        user_service.create_cashier(username, full_name, password)
    assert len(user_service.list_users()) == 2


def test_missing_accounts_and_invalid_status_have_expected_errors(accounts):
    auth_service.login("owner", "owner123")
    with pytest.raises(NotFoundError):
        user_service.set_active(999, False)
    with pytest.raises(NotFoundError):
        user_service.reset_password(999, "password")
    with pytest.raises(ValidationError):
        user_service.set_active(2, "false")
