"""bcrypt password hashing without silently truncating long passwords."""

import bcrypt

from pawpos.core.errors import ValidationError


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password.strip():
        raise ValidationError("Password is required.")
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise ValidationError("Password must be at most 72 UTF-8 bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Treat invalid passwords or stored hashes as failed verification."""
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False
    encoded = password.encode("utf-8")
    if not encoded or len(encoded) > 72:
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode("ascii"))
    except (ValueError, UnicodeError):
        return False
