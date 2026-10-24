"""Shared refund reads, personal decision notices, and audited payout recording."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from pawpos.core.errors import BusinessRuleError, NotFoundError, ValidationError
from pawpos.db.base import session_scope
from pawpos.models import (
    RefundDecisionNotice,
    RefundItem,
    RefundPayout,
    RefundPayoutCorrection,
    RefundRequest,
    Sale,
    User,
)
from pawpos.services.auth_service import _require_owner, _require_user
from pawpos.services.catalog_validation import text
from pawpos.services.refund_service import RefundDetails, _details, _id

STATUSES = ("all", "pending", "rejected", "awaiting_payout", "paid", "legacy_paid")


@dataclass(frozen=True)
class PayoutDetails:
    method: str | None
    reference: str | None
    paid_by: str | None
    paid_at: datetime | None
    legacy_assumed_paid: bool


@dataclass(frozen=True)
class CorrectionDetails:
    old_method: str
    old_reference: str | None
    new_method: str
    new_reference: str | None
    reason: str
    corrected_by: str
    corrected_at: datetime


@dataclass(frozen=True)
class TrackedRefund:
    request: RefundDetails
    payout: PayoutDetails | None
    corrections: tuple[CorrectionDetails, ...] = ()

    @property
    def status(self) -> str:
        if self.request.status != "approved":
            return self.request.status
        if self.payout is None:
            return "awaiting_payout"
        return "legacy_paid" if self.payout.legacy_assumed_paid else "paid"


@dataclass(frozen=True)
class DecisionNotice:
    request_id: int
    receipt_number: str
    status: str
    created_at: datetime


def _query():
    return select(RefundRequest).options(
        joinedload(RefundRequest.sale),
        joinedload(RefundRequest.requester),
        joinedload(RefundRequest.reviewer),
        selectinload(RefundRequest.items).joinedload(RefundItem.sale_item),
    )


def _tracked(session, request, *, history=False):
    payout = session.scalar(
        select(RefundPayout).where(RefundPayout.refund_request_id == request.id)
    )
    details = None
    corrections = ()
    if payout is not None:
        actor = session.get(User, payout.paid_by) if payout.paid_by else None
        details = PayoutDetails(
            payout.method,
            payout.reference,
            actor.full_name if actor else None,
            payout.paid_at,
            payout.legacy_assumed_paid,
        )
        if history:
            rows = session.execute(
                select(RefundPayoutCorrection, User.full_name)
                .join(User, RefundPayoutCorrection.corrected_by == User.id)
                .where(RefundPayoutCorrection.payout_id == payout.id)
                .order_by(RefundPayoutCorrection.id)
            )
            corrections = tuple(
                CorrectionDetails(
                    row.old_method,
                    row.old_reference,
                    row.new_method,
                    row.new_reference,
                    row.reason,
                    actor_name,
                    row.corrected_at,
                )
                for row, actor_name in rows
            )
    return TrackedRefund(_details(request), details, corrections)


def list_refunds(receipt="", status="all") -> list[TrackedRefund]:
    """List all shop requests; payout filters do not change approval status."""
    with session_scope() as session:
        _require_user(session)
        receipt = text(receipt, "Receipt", 30, required=False)
        if status not in STATUSES:
            raise ValidationError("Choose a valid refund status.")
        query = _query().join(RefundRequest.sale)
        if receipt:
            query = query.where(Sale.receipt_number.contains(receipt, autoescape=True))
        if status in ("pending", "rejected"):
            query = query.where(RefundRequest.status == status)
        elif status != "all":
            query = query.outerjoin(
                RefundPayout, RefundPayout.refund_request_id == RefundRequest.id
            ).where(RefundRequest.status == "approved")
            if status == "awaiting_payout":
                query = query.where(RefundPayout.id.is_(None))
            else:
                query = query.where(
                    RefundPayout.legacy_assumed_paid == (status == "legacy_paid")
                )
        return [
            _tracked(session, row)
            for row in session.scalars(
                query.order_by(
                    RefundRequest.requested_at.desc(), RefundRequest.id.desc()
                )
            )
        ]


def get_refund(request_id: int) -> TrackedRefund:
    with session_scope() as session:
        _require_user(session)
        request = session.scalar(_query().where(RefundRequest.id == _id(request_id)))
        if request is None:
            raise NotFoundError("Refund request not found.")
        return _tracked(session, request, history=True)


def _payment(method, reference):
    if method not in ("cash", "gcash"):
        raise ValidationError("Choose cash or GCash.")
    reference = text(reference, "GCash reference", 50, required=method == "gcash")
    return method, reference if method == "gcash" else None


def record_payout(request_id: int, method: str, reference="") -> TrackedRefund:
    """Record the full amount already returned; unique request prevents duplicates."""
    try:
        with session_scope() as session:
            actor = _require_user(session)
            method, reference = _payment(method, reference)
            request = session.scalar(
                _query().where(RefundRequest.id == _id(request_id)).with_for_update()
            )
            if request is None:
                raise NotFoundError("Refund request not found.")
            if request.status != "approved":
                raise BusinessRuleError("Only approved refunds can be paid.")
            if (
                session.scalar(
                    select(RefundPayout.id).where(
                        RefundPayout.refund_request_id == request.id
                    )
                )
                is not None
            ):
                raise BusinessRuleError("This refund is already recorded as paid.")
            payout = RefundPayout(
                refund_request_id=request.id,
                method=method,
                reference=reference,
                paid_by=actor.id,
                paid_at=datetime.now(),
            )
            session.add(payout)
            session.flush()
            return _tracked(session, request, history=True)
    except IntegrityError:
        # Inspect after rollback so unrelated constraint errors are not hidden.
        with session_scope() as session:
            duplicate = session.scalar(
                select(RefundPayout.id).where(
                    RefundPayout.refund_request_id == request_id
                )
            )
        if duplicate is not None:
            raise BusinessRuleError(
                "This refund is already recorded as paid."
            ) from None
        raise


def correct_payout(
    request_id: int, method: str, reference: str, reason: str
) -> TrackedRefund:
    """Correct payment details with append-only audit, without reopening payment."""
    with session_scope() as session:
        owner = _require_owner(session)
        method, reference = _payment(method, reference)
        reason = text(reason, "Correction reason", 255)
        payout = session.scalar(
            select(RefundPayout)
            .where(RefundPayout.refund_request_id == _id(request_id))
            .with_for_update()
        )
        if payout is None or payout.legacy_assumed_paid:
            raise BusinessRuleError(
                "Select a recorded payout; legacy assumed payments cannot be corrected."
            )
        if (payout.method, payout.reference) == (method, reference):
            raise ValidationError(
                "Change the method or reference before saving a correction."
            )
        session.add(
            RefundPayoutCorrection(
                payout_id=payout.id,
                old_method=payout.method,
                old_reference=payout.reference,
                new_method=method,
                new_reference=reference,
                reason=reason,
                corrected_by=owner.id,
            )
        )
        payout.method, payout.reference = method, reference
        session.flush()
        request = session.scalar(_query().where(RefundRequest.id == request_id))
        return _tracked(session, request, history=True)


def unread_notices() -> list[DecisionNotice]:
    with session_scope() as session:
        user = _require_user(session)
        rows = session.execute(
            select(RefundDecisionNotice, RefundRequest)
            .join(
                RefundRequest,
                RefundDecisionNotice.refund_request_id == RefundRequest.id,
            )
            .options(joinedload(RefundRequest.sale))
            .where(
                RefundDecisionNotice.user_id == user.id,
                RefundDecisionNotice.read_at.is_(None),
            )
            .order_by(
                RefundDecisionNotice.created_at.desc(), RefundDecisionNotice.id.desc()
            )
        )
        return [
            DecisionNotice(r.id, r.sale.receipt_number, r.status, n.created_at)
            for n, r in rows
        ]


def acknowledge_decision(request_id: int) -> None:
    """Acknowledge only the current user's notice, never another requester's."""
    with session_scope() as session:
        user = _require_user(session)
        notice = session.scalar(
            select(RefundDecisionNotice).where(
                RefundDecisionNotice.refund_request_id == _id(request_id),
                RefundDecisionNotice.user_id == user.id,
            )
        )
        if notice is not None and notice.read_at is None:
            notice.read_at = datetime.now()
