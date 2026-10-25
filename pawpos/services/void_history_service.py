"""Read-only, account-scoped access to saved void item snapshots."""

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pawpos.core.errors import AuthError, ValidationError
from pawpos.db.base import session_scope
from pawpos.models import VoidLog
from pawpos.services.auth_service import _require_user


def _access(session):
    user = _require_user(session)
    if user.role not in ("owner", "cashier"):
        raise AuthError("An active cashier or owner account is required.")
    return user


def get_access() -> tuple[int, str]:
    """Recheck access before displaying cached history details."""
    with session_scope() as session:
        user = _access(session)
        return user.id, user.role


@dataclass(frozen=True)
class VoidRecord:
    id: int
    user_id: int
    actor_name: str
    created_at: datetime
    product_name: str
    quantity: Decimal
    amount: Decimal
    scope: str
    reason: str


def list_voids(
    *, date_from: date | None = None, date_to: date | None = None
) -> tuple[VoidRecord, ...]:
    """Return saved item rows, restricted by persisted role and inclusive dates."""
    with session_scope() as session:
        user = _access(session)
        for bound in (date_from, date_to):
            if bound is not None and type(bound) is not date:
                raise ValidationError("Dates must be calendar dates.")
        if date_from and date_to and date_from > date_to:
            raise ValidationError("From date must not be after To date.")
        query = select(VoidLog).options(joinedload(VoidLog.user))
        if user.role == "cashier":
            query = query.where(VoidLog.user_id == user.id)
        if date_from:
            query = query.where(
                VoidLog.created_at >= datetime.combine(date_from, time.min)
            )
        if date_to:
            query = query.where(
                VoidLog.created_at <= datetime.combine(date_to, time.max)
            )
        query = query.order_by(VoidLog.created_at.desc(), VoidLog.id.desc())
        return tuple(
            VoidRecord(
                row.id,
                row.user_id,
                row.user.full_name,
                row.created_at,
                row.product_name,
                row.quantity,
                row.amount,
                row.void_scope,
                row.reason,
            )
            for row in session.scalars(query)
        )
