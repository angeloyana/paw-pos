"""Authentication and service-side owner authorization."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError
from pawpos.core.security import verify_password
from pawpos.core.session import CurrentUser
from pawpos.db.base import session_scope
from pawpos.models import User


def login(username: str, password: str) -> CurrentUser:
    """Authenticate an active account and remember only its public identity."""
    login_session.logout()
    if not isinstance(username, str) or not username.strip():
        raise AuthError("Enter your username and password.")
    with session_scope() as session:
        user = session.scalar(
            select(User).where(User.username == username.strip().casefold())
        )
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("Incorrect username or password.")
        if not user.is_active:
            raise AuthError("This account is disabled. Contact the shop owner.")
        identity = CurrentUser(user.id, user.username, user.full_name, user.role)
    login_session.set_current_user(identity)
    return identity


def logout() -> None:
    """Clear the signed-in user before returning to login."""
    login_session.logout()


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
