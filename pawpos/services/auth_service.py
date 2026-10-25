"""Authentication and service-side owner authorization."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError, ValidationError
from pawpos.core.security import hash_password, verify_password
from pawpos.core.session import CurrentUser
from pawpos.db.base import session_scope
from pawpos.models import User


def login(username: str, password: str) -> CurrentUser:
    """Authenticate an active account and remember only its public identity."""
    login_session.logout()
    if not isinstance(username, str) or not username.strip():
        raise AuthError("Enter your username and password.")
    username = username.strip()
    with session_scope() as session:
        user = session.scalar(select(User).where(User.username == username))
        # Database collation may match a different capitalization.
        if (
            user is None
            or user.username != username
            or not verify_password(password, user.password_hash)
        ):
            raise AuthError("Incorrect username or password.")
        if not user.is_active:
            raise AuthError("This account is disabled. Contact the shop owner.")
        identity = CurrentUser(user.id, user.username, user.full_name, user.role)
    login_session.set_current_user(identity)
    return identity


def logout() -> None:
    """Clear the signed-in user before returning to login."""
    login_session.logout()


def change_password(
    current_password: str, new_password: str, confirmation: str
) -> None:
    """Change the active account's password after verifying its current one."""
    with session_scope() as session:
        user = _require_user(session)
        if not verify_password(current_password, user.password_hash):
            raise ValidationError("Current password is incorrect.")
        if new_password != confirmation:
            raise ValidationError("New passwords do not match.")
        user.password_hash = hash_password(new_password)


def _require_user(session: Session) -> User:
    """Recheck persisted access before a catalog read or owner operation."""
    current = login_session.current_user
    user = session.get(User, current.id) if current is not None else None
    if user is None or not user.is_active:
        raise AuthError("An active account is required.")
    return user


def _require_owner(session: Session) -> User:
    """Recheck persisted access so disabling an account takes effect immediately."""
    user = _require_user(session)
    if user.role != "owner":
        raise AuthError("An active owner account is required.")
    return user
