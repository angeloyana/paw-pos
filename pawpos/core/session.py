"""In-memory login state; no database sessions or credentials are stored here."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    full_name: str
    role: Literal["owner", "cashier"]


current_user: CurrentUser | None = None


def set_current_user(user: CurrentUser | None) -> None:
    global current_user
    current_user = user


def logout() -> None:
    set_current_user(None)
