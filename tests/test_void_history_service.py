from dataclasses import FrozenInstanceError
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError, ValidationError
from pawpos.core.session import CurrentUser
from pawpos.models import User, VoidLog
from pawpos.services import void_history_service as history


def sign_in(user_id, role="cashier"):
    login_session.set_current_user(CurrentUser(user_id, "test", "Test", role))


@pytest.fixture
def history_db(session_factory):
    with session_factory.begin() as session:
        for ident, role in ((1, "owner"), (2, "cashier"), (3, "cashier")):
            session.add(
                User(
                    id=ident,
                    username=f"u{ident}",
                    full_name=f"User {ident}",
                    password_hash="unused",
                    role=role,
                )
            )
        session.flush()
        for ident, actor, when in (
            (1, 2, datetime(2026, 10, 25, 23, 59, 59, 999999)),
            (2, 2, datetime(2026, 10, 26)),
            (3, 3, datetime(2026, 10, 26)),
            (4, 1, datetime(2026, 10, 27)),
        ):
            session.add(
                VoidLog(
                    id=ident,
                    user_id=actor,
                    product_name="Saved name",
                    quantity=Decimal("1.375"),
                    amount=Decimal("130.63"),
                    void_scope="line" if ident == 1 else "transaction",
                    reason="Full reason " + "x" * 240,
                    created_at=when,
                )
            )
    sign_in(2)
    return session_factory


def test_scoped_immutable_snapshots_and_owner_disabled_history(history_db):
    rows = history.list_voids()
    assert [row.id for row in rows] == [2, 1]
    assert rows[1].scope == "line" and rows[0].scope == "transaction"
    assert rows[0].product_name == "Saved name"
    assert rows[0].quantity == Decimal("1.375")
    assert rows[0].amount == Decimal("130.63")
    assert len(rows[0].reason) == 252
    with pytest.raises(FrozenInstanceError):
        rows[0].reason = "changed"
    sign_in(3)
    assert [row.id for row in history.list_voids()] == [3]
    with history_db.begin() as session:
        session.get(User, 3).is_active = False
    sign_in(1)
    assert history.get_access() == (1, "owner")
    assert [row.id for row in history.list_voids()] == [4, 3, 2, 1]
    assert history.list_voids()[1].actor_name == "User 3"
    with history_db() as session:
        assert len(session.scalars(select(VoidLog)).all()) == 4
        assert session.get(VoidLog, 1).reason == rows[1].reason


@pytest.mark.parametrize(
    "start,end,expected",
    [
        (None, None, [2, 1]),
        (date(2026, 10, 26), None, [2]),
        (None, date(2026, 10, 25), [1]),
        (date(2026, 10, 25), date(2026, 10, 25), [1]),
        (date(2026, 10, 26), date(2026, 10, 26), [2]),
        (date(2026, 10, 28), None, []),
    ],
)
def test_inclusive_dates(history_db, start, end, expected):
    assert [r.id for r in history.list_voids(date_from=start, date_to=end)] == expected


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-10-25", None),
        (None, datetime(2026, 10, 25)),
        (date(2026, 10, 26), date(2026, 10, 25)),
    ],
)
def test_invalid_dates(history_db, start, end):
    with pytest.raises(ValidationError):
        history.list_voids(date_from=start, date_to=end)


@pytest.mark.parametrize("state", ["logout", "missing", "disabled"])
def test_access_denial(history_db, state):
    if state == "logout":
        login_session.logout()
    elif state == "missing":
        sign_in(999)
    else:
        with history_db.begin() as session:
            session.get(User, 2).is_active = False
    for read in (history.list_voids, history.get_access):
        with pytest.raises(AuthError):
            read()


def test_persisted_role_overrides_stale_session(history_db):
    sign_in(2, "owner")
    assert [r.id for r in history.list_voids()] == [2, 1]
    assert history.get_access() == (2, "cashier")
