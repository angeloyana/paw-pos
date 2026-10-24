import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from pawpos.core import session as login_session
from pawpos.db import base


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    base.init_db(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(base, "SessionLocal", factory)
    login_session.logout()
    yield factory
    login_session.logout()
    engine.dispose()
