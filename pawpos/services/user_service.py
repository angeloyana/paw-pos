"""Owner operations on accounts, returning no password hashes."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from pawpos.core.errors import BusinessRuleError, NotFoundError, ValidationError
from pawpos.core.security import hash_password
from pawpos.db.base import session_scope
from pawpos.models import User
from pawpos.services.auth_service import _require_owner


@dataclass(frozen=True)
class UserDetails:
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool


def _details(user: User) -> UserDetails:
    return UserDetails(
        user.id, user.username, user.full_name, user.role, user.is_active
    )


def _required_text(value: str, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} is required.")
    value = value.strip()
    if len(value) > limit:
        raise ValidationError(f"{label} must be at most {limit} characters.")
    return value


def create_cashier(username: str, full_name: str, password: str) -> UserDetails:
    """Create an active cashier with a unique normalized username."""
    try:
        with session_scope() as session:
            _require_owner(session)
            username = _required_text(username, "Username", 50).casefold()
            username = _required_text(username, "Username", 50)
            full_name = _required_text(full_name, "Full name", 100)
            if (
                session.scalar(select(User.id).where(User.username == username))
                is not None
            ):
                raise ValidationError("Username is already in use.")
            user = User(
                username=username,
                full_name=full_name,
                role="cashier",
                password_hash=hash_password(password),
            )
            session.add(user)
            session.flush()
            result = _details(user)
    except IntegrityError:
        raise ValidationError("Username is already in use.") from None
    return result


def list_users() -> list[UserDetails]:
    """List accounts for owner administration."""
    with session_scope() as session:
        _require_owner(session)
        return [
            _details(user)
            for user in session.scalars(select(User).order_by(User.username))
        ]


def set_active(user_id: int, is_active: bool) -> UserDetails:
    """Enable or disable a cashier while retaining their historical records."""
    with session_scope() as session:
        owner = _require_owner(session)
        if not isinstance(is_active, bool):
            raise ValidationError("Account status must be enabled or disabled.")
        user = session.get(User, user_id)
        if user is None:
            raise NotFoundError("Account not found.")
        if user.id == owner.id and not is_active:
            raise BusinessRuleError("You cannot disable your own account.")
        if user.role != "cashier":
            raise BusinessRuleError("Only cashier accounts can be enabled or disabled.")
        user.is_active = is_active
        return _details(user)


def reset_password(user_id: int, password: str) -> None:
    """Set a new bcrypt password; owners may also change their seeded password."""
    with session_scope() as session:
        _require_owner(session)
        user = session.get(User, user_id)
        if user is None:
            raise NotFoundError("Account not found.")
        user.password_hash = hash_password(password)
