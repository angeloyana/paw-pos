"""Expected service errors suitable for presentation to the user."""


class PawPOSError(Exception):
    """Base class for expected application errors."""


class ValidationError(PawPOSError):
    """An input is missing or invalid."""


class BusinessRuleError(PawPOSError):
    """An operation violates a shop rule."""


class NotFoundError(PawPOSError):
    """A requested record does not exist."""


class AuthError(PawPOSError):
    """Authentication or authorization failed."""
