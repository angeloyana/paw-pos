"""Preferences for the active account, without exposing credentials."""

from dataclasses import dataclass

from ttkbootstrap.themes.standard import STANDARD_THEMES

from pawpos.config import THEME
from pawpos.core.errors import ValidationError
from pawpos.db.base import session_scope
from pawpos.models import UserSettings
from pawpos.services.auth_service import _require_user


def theme_names() -> tuple[str, ...]:
    """List built-in themes without creating a Tk window."""
    return tuple(sorted(STANDARD_THEMES))


@dataclass(frozen=True)
class Settings:
    theme: str


def get_settings() -> Settings:
    """Read the active user's theme, defaulting for missing/retired themes."""
    with session_scope() as session:
        user = _require_user(session)
        settings = session.get(UserSettings, user.id)
        theme = settings.theme if settings is not None else THEME
        return Settings(theme if theme in theme_names() else THEME)


def set_theme(theme: str) -> Settings:
    """Save only the signed-in active user's supported theme."""
    with session_scope() as session:
        user = _require_user(session)
        if not isinstance(theme, str) or theme not in theme_names():
            raise ValidationError("Choose a built-in theme.")
        settings = session.get(UserSettings, user.id)
        if settings is None:
            session.add(UserSettings(user_id=user.id, theme=theme))
        else:
            settings.theme = theme
    return Settings(theme)
