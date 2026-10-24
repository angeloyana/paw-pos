"""Refund payout records, correction audit, personal notices, and cutover marker."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from pawpos.db.base import Base


class RefundPayout(Base):
    __tablename__ = "refund_payouts"
    __table_args__ = (
        CheckConstraint(
            "(legacy_assumed_paid = 1 AND method IS NULL AND reference IS NULL "
            "AND paid_by IS NULL AND paid_at IS NULL) OR "
            "(legacy_assumed_paid = 0 AND paid_by IS NOT NULL AND paid_at IS NOT NULL "
            "AND method IS NOT NULL "
            "AND ((method = 'cash' AND reference IS NULL) OR "
            "(method = 'gcash' AND reference IS NOT NULL AND length(trim(reference)) > 0)))",
            name="refund_payout_details",
        ),
        Base.__table_args__,
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    refund_request_id: Mapped[int] = mapped_column(
        ForeignKey("refund_requests.id"), unique=True
    )
    legacy_assumed_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    method: Mapped[str | None] = mapped_column(String(10))
    reference: Mapped[str | None] = mapped_column(String(50))
    paid_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime)


class RefundPayoutCorrection(Base):
    __tablename__ = "refund_payout_corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    payout_id: Mapped[int] = mapped_column(ForeignKey("refund_payouts.id"), index=True)
    old_method: Mapped[str] = mapped_column(String(10))
    old_reference: Mapped[str | None] = mapped_column(String(50))
    new_method: Mapped[str] = mapped_column(String(10))
    new_reference: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(String(255))
    corrected_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    corrected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class RefundDecisionNotice(Base):
    __tablename__ = "refund_decision_notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    refund_request_id: Mapped[int] = mapped_column(
        ForeignKey("refund_requests.id"), unique=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    read_at: Mapped[datetime | None] = mapped_column(DateTime)


class RefundTrackingState(Base):
    __tablename__ = "refund_tracking_state"
    __table_args__ = (
        CheckConstraint("id = 1", name="refund_tracking_singleton"),
        Base.__table_args__,
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    initialized_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
