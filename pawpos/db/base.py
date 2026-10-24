"""Lazy MySQL engine and atomic service session scopes."""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from pawpos.config import database_url


class Base(DeclarativeBase):
    pass


def make_engine() -> Engine:
    """Creating the engine does not connect until an operation needs it."""
    return create_engine(
        database_url(),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Commit a service operation in full, or roll it back and close."""
    with SessionLocal() as session:
        with session.begin():
            yield session


def init_db(bind: Engine | None = None) -> None:
    """Register all models before creating their tables."""
    import pawpos.models  # noqa: F401

    Base.metadata.create_all(bind if bind is not None else engine)


@dataclass(frozen=True)
class ConnectionCheck:
    success: bool
    message: str


def check_connection(bind: Engine | None = None) -> ConnectionCheck:
    """Report connectivity without exposing driver errors or credentials."""
    try:
        with (bind if bind is not None else engine).connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return ConnectionCheck(
            False,
            "Cannot connect to the database. Check MySQL is running, the database "
            "exists, and the DB settings in .env are correct.",
        )
    return ConnectionCheck(True, "Database connection successful.")
