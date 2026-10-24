import tkinter as tk
import traceback

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from ttkbootstrap import Style

from pawpos.core import session as login_session
from pawpos.db import base
from pawpos.db.seed import seed_database


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


@pytest.fixture
def app(session_factory):
    from pawpos.ui.app import PawPOSApp

    try:
        probe = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Desktop display unavailable: {error}")
    probe.destroy()
    # ttkbootstrap caches the first root's Style; each test owns a fresh root.
    Style.instance = None
    seed_database()
    app = PawPOSApp()
    callback_errors = []
    app.report_callback_exception = lambda *error: callback_errors.append(
        "".join(traceback.format_exception(*error))
    )
    app.update()
    yield app
    try:
        app.close()
    except tk.TclError:
        pass
    Style.instance = None
    assert not callback_errors, f"Unexpected Tk callback errors: {callback_errors}"
