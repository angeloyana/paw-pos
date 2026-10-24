from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError, BusinessRuleError, ValidationError
from pawpos.core.session import CurrentUser
from pawpos.db import base
from pawpos.db.seed import initialize_refund_tracking, seed_database
from pawpos.models import (
    Product,
    RefundDecisionNotice,
    RefundPayout,
    RefundPayoutCorrection,
    RefundRequest,
    RefundTrackingState,
    StockMovement,
    User,
)
from pawpos.services import refund_service as refunds
from pawpos.services import refund_tracking_service as tracking
from tests.test_refund_rules import request, sign_in
from tests.test_refund_rules import sold as sold_fixture


@pytest.fixture
def sold(session_factory):
    yield from sold_fixture.__wrapped__(session_factory)


def approved(sold):
    result = request(sold)
    sign_in("owner")
    refunds.approve(result.id, {item.id: False for item in result.items})
    return result


def test_shared_visibility_filters_details_and_personal_notices(sold):
    result = approved(sold)
    assert tracking.unread_notices() == []  # Reviewer is not the requester.
    sign_in()
    notices = tracking.unread_notices()
    assert [(n.request_id, n.status) for n in notices] == [(result.id, "approved")]
    assert tracking.get_refund(result.id).request.reviewer == "Owner"
    assert [r.request.id for r in tracking.list_refunds(status="awaiting_payout")] == [
        result.id
    ]
    assert tracking.list_refunds(receipt="%") == []
    assert len(tracking.list_refunds(receipt=result.receipt_number)) == 1
    factory = sold[0]
    with factory.begin() as session:
        session.add(
            User(
                id=3,
                username="other",
                full_name="Other",
                role="cashier",
                password_hash="unused",
            )
        )
    login_session.set_current_user(CurrentUser(3, "other", "Other", "cashier"))
    assert len(tracking.list_refunds()) == 1
    assert tracking.unread_notices() == []
    tracking.acknowledge_decision(result.id)
    sign_in()
    assert len(tracking.unread_notices()) == 1
    login_session.logout()
    sign_in()
    assert len(tracking.unread_notices()) == 1
    tracking.acknowledge_decision(result.id)
    tracking.acknowledge_decision(result.id)
    assert tracking.unread_notices() == []


def test_rejection_has_note_and_notice_and_cannot_be_paid(sold):
    result = request(sold)
    with pytest.raises(BusinessRuleError):
        tracking.record_payout(result.id, "cash")
    sign_in("owner")
    refunds.reject(result.id, "Does not match receipt")
    sign_in()
    row = tracking.list_refunds(status="rejected")[0]
    assert row.request.review_note == "Does not match receipt"
    assert tracking.unread_notices()[0].status == "rejected"
    with pytest.raises(BusinessRuleError):
        tracking.record_payout(result.id, "cash")


@pytest.mark.parametrize("method,reference", [("cash", ""), ("gcash", " TX-123 ")])
def test_full_payout_preserves_reports_stock_and_quantity(sold, method, reference):
    result = approved(sold)
    factory = sold[0]
    with factory() as session:
        before_stock = session.get(Product, 1).stock_quantity
        before_movements = session.scalar(
            select(func.count()).select_from(StockMovement)
        )
    remaining = refunds.remaining_refundable(result.items[0].sale_item_id)
    sign_in()
    paid = tracking.record_payout(result.id, method, reference)
    assert paid.status == "paid" and paid.request.status == "approved"
    assert paid.request.total_amount == result.total_amount
    assert paid.payout.paid_by == "Cashier" and paid.payout.paid_at is not None
    assert paid.payout.reference == ("TX-123" if method == "gcash" else None)
    assert tracking.list_refunds(status="awaiting_payout") == []
    assert len(tracking.list_refunds(status="paid")) == 1
    with pytest.raises(BusinessRuleError, match="already"):
        tracking.record_payout(result.id, method, reference)
    with factory() as session:
        assert session.get(Product, 1).stock_quantity == before_stock
        assert (
            session.scalar(select(func.count()).select_from(StockMovement))
            == before_movements
        )
        assert (
            session.get(RefundRequest, result.id).reviewed_at
            == paid.request.reviewed_at
        )
    assert refunds.remaining_refundable(result.items[0].sale_item_id) == remaining


@pytest.mark.parametrize(
    "method,reference",
    [("gcash", ""), ("gcash", " " * 5), ("gcash", "x" * 51), ("bank", "")],
)
def test_invalid_payout_keeps_refund_unpaid(sold, method, reference):
    result = approved(sold)
    with pytest.raises(ValidationError):
        tracking.record_payout(result.id, method, reference)
    assert tracking.get_refund(result.id).status == "awaiting_payout"


def test_corrections_are_owner_only_audited_and_do_not_change_actor_or_time(sold):
    result = approved(sold)
    sign_in()
    original = tracking.record_payout(result.id, "cash")
    with pytest.raises(AuthError):
        tracking.correct_payout(result.id, "gcash", "REF", "Wrong method")
    sign_in("owner")
    with pytest.raises(ValidationError):
        tracking.correct_payout(result.id, "gcash", "REF", "")
    with pytest.raises(ValidationError):
        tracking.correct_payout(result.id, "cash", "", "No change")
    updated = tracking.correct_payout(result.id, "gcash", "REF", "Wrong method")
    assert updated.payout.paid_by == original.payout.paid_by
    assert updated.payout.paid_at == original.payout.paid_at
    correction = updated.corrections[0]
    assert (correction.old_method, correction.new_method, correction.new_reference) == (
        "cash",
        "gcash",
        "REF",
    )
    assert correction.reason == "Wrong method" and correction.corrected_by == "Owner"
    updated = tracking.correct_payout(result.id, "gcash", "REF2", "Typo")
    assert len(updated.corrections) == 2 and updated.status == "paid"


def test_legacy_initialization_only_once_and_without_fabricated_details(sold):
    result = approved(sold)
    factory = sold[0]
    # Simulate a decision made by the old application, which did not create notices.
    with factory.begin() as session:
        session.query(RefundDecisionNotice).delete()
        initialize_refund_tracking(session)
    legacy = tracking.get_refund(result.id)
    assert legacy.status == "legacy_paid"
    assert (
        legacy.payout.method is legacy.payout.paid_by is legacy.payout.paid_at is None
    )
    assert len(tracking.list_refunds(status="legacy_paid")) == 1
    assert tracking.unread_notices() == []
    with pytest.raises(BusinessRuleError):
        tracking.record_payout(result.id, "cash")
    with pytest.raises(BusinessRuleError):
        tracking.correct_payout(result.id, "cash", "", "Invented")
    later = approved(sold)
    assert seed_database() is False
    assert tracking.get_refund(later.id).status == "awaiting_payout"
    with factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(RefundTrackingState)) == 1
        )
        assert session.scalar(select(func.count()).select_from(RefundPayout)) == 1


def fail_commit(_session):
    raise RuntimeError("Commit failed")


def test_notice_review_and_payout_correction_failures_rollback(sold):
    factory = sold[0]
    result = request(sold)
    sign_in("owner")
    event.listen(factory, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError):
            refunds.reject(result.id, "Rejected")
    finally:
        event.remove(factory, "before_commit", fail_commit)
    assert tracking.get_refund(result.id).status == "pending"
    sign_in()
    assert tracking.unread_notices() == []
    sign_in("owner")
    refunds.approve(result.id, {item.id: False for item in result.items})

    event.listen(factory, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError):
            tracking.record_payout(result.id, "cash")
    finally:
        event.remove(factory, "before_commit", fail_commit)
    assert tracking.get_refund(result.id).status == "awaiting_payout"
    tracking.record_payout(result.id, "cash")
    event.listen(factory, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError):
            tracking.correct_payout(result.id, "gcash", "REF", "Typo")
    finally:
        event.remove(factory, "before_commit", fail_commit)
    assert tracking.get_refund(result.id).payout.method == "cash"
    with factory() as session:
        assert (
            session.scalar(select(func.count()).select_from(RefundPayoutCorrection))
            == 0
        )


def test_disabled_and_logged_out_accounts_cannot_use_tracking(sold):
    result = approved(sold)
    sign_in()
    with sold[0].begin() as session:
        session.get(User, 1).is_active = False
    for operation in (
        tracking.list_refunds,
        lambda: tracking.get_refund(result.id),
        tracking.unread_notices,
        lambda: tracking.acknowledge_decision(result.id),
        lambda: tracking.record_payout(result.id, "cash"),
    ):
        with pytest.raises(AuthError):
            operation()
    login_session.logout()
    with pytest.raises(AuthError):
        tracking.list_refunds()


def test_concurrent_payouts_create_one_record(sold, tmp_path, monkeypatch):
    factory = sold[0]
    result = approved(sold)
    # Separate connections model competing saves against the same durable DB.
    with factory() as session:
        source = session.connection().connection.driver_connection
        import sqlite3

        destination = sqlite3.connect(tmp_path / "payout.sqlite")
        source.backup(destination)
        destination.close()
    engine = create_engine(
        f"sqlite:///{tmp_path / 'payout.sqlite'}", connect_args={"timeout": 10}
    )
    shared_factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(base, "SessionLocal", shared_factory)
    sign_in()

    def pay():
        try:
            tracking.record_payout(result.id, "cash")
            return "saved"
        except BusinessRuleError:
            return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: pay(), range(2)))
    assert sorted(results) == ["duplicate", "saved"]
    with shared_factory() as session:
        assert session.scalar(select(func.count()).select_from(RefundPayout)) == 1
    engine.dispose()


def test_database_rejects_duplicate_and_incomplete_payouts(sold):
    result = approved(sold)
    tracking.record_payout(result.id, "cash")
    with pytest.raises(IntegrityError), sold[0].begin() as session:
        session.add(RefundPayout(refund_request_id=result.id, legacy_assumed_paid=True))
    with pytest.raises(IntegrityError), sold[0].begin() as session:
        session.add(RefundPayout(refund_request_id=result.id, method="gcash"))
