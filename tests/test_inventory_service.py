from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select

from pawpos.core.errors import (
    AuthError,
    BusinessRuleError,
    NotFoundError,
    ValidationError,
)
from pawpos.db.seed import seed_database
from pawpos.models import Product, Sale, StockMovement, User
from pawpos.services import auth_service
from pawpos.services import inventory_service as inventory


@pytest.fixture
def stock(session_factory):
    seed_database()
    auth_service.login("owner", "owner123")
    products = inventory.stock_overview()
    piece = next(p for p in products if p.unit_type == "piece" and p.stock_quantity > 0)
    kg = next(p for p in products if p.unit_type == "kg")
    return session_factory, piece, kg


def test_receive_and_adjust_record_actor_sign_balance_and_delivery_details(stock):
    factory, piece, kg = stock
    assert (
        inventory.receive_stock(piece.id, "3", supplier="Supplier", note="Delivery")
        == piece.stock_quantity + 3
    )
    assert (
        inventory.adjust_stock(piece.id, "-2", reason="Damage", note="Broken")
        == piece.stock_quantity + 1
    )
    assert inventory.adjust_stock(
        kg.id, "0.125", reason="Correction", note="Recount"
    ) == kg.stock_quantity + Decimal("0.125")
    rows = inventory.list_movements(product_id=piece.id)
    assert (
        rows[0].quantity_change == -2
        and rows[0].stock_after == piece.stock_quantity + 1
    )
    assert rows[0].note == "Damage: Broken" and rows[0].user_name == "Shop Owner"
    assert (
        rows[1].quantity_change == 3 and rows[1].stock_after == piece.stock_quantity + 3
    )
    assert rows[1].note == "Supplier: Supplier; Delivery"
    with factory() as session:
        assert session.get(Product, piece.id).supplier == (piece.supplier or None)


@pytest.mark.parametrize("amount", ["0", "-1", "1.5", "NaN", 1.5, "10000000", "1e999"])
def test_invalid_piece_receipt_preserves_stock_history(stock, amount):
    _, piece, _ = stock
    before = inventory.list_movements()
    with pytest.raises(ValidationError):
        inventory.receive_stock(piece.id, amount)
    assert inventory.list_movements() == before
    assert (
        next(p for p in inventory.stock_overview() if p.id == piece.id).stock_quantity
        == piece.stock_quantity
    )


@pytest.mark.parametrize(
    "change,reason,note",
    [
        ("0", "Loss", "Missing"),
        ("-9999999", "Loss", "Missing"),
        ("1.001", "Correction", "Recount"),
        ("1", "Unknown", "Test"),
        ("1", "Other", " "),
        ("1", "Other", "x" * 255),
    ],
)
def test_invalid_adjustment_preserves_stock_history(stock, change, reason, note):
    _, piece, _ = stock
    before = inventory.list_movements()
    with pytest.raises((ValidationError, BusinessRuleError)):
        inventory.adjust_stock(piece.id, change, reason=reason, note=note)
    assert inventory.list_movements() == before


def test_kg_precision_result_limit_and_zero_balance(stock):
    _, piece, kg = stock
    with pytest.raises(ValidationError):
        inventory.receive_stock(kg.id, "0.0001")
    with pytest.raises(ValidationError):
        inventory.receive_stock(kg.id, "9999999.999")
    inventory.adjust_stock(
        piece.id, -piece.stock_quantity, reason="Correction", note="Empty"
    )
    assert inventory.list_movements(product_id=piece.id)[0].stock_after == 0


def test_commit_failure_rolls_back_product_and_movement(stock):
    factory, piece, _ = stock
    before = inventory.list_movements()

    def fail(_session):
        raise RuntimeError("Failed commit")

    event.listen(factory, "before_commit", fail)
    try:
        with pytest.raises(RuntimeError):
            inventory.receive_stock(piece.id, "2")
    finally:
        event.remove(factory, "before_commit", fail)
    assert inventory.list_movements() == before
    with factory() as session:
        assert session.get(Product, piece.id).stock_quantity == piece.stock_quantity


def test_owner_only_and_disabled_account(stock):
    factory, piece, _ = stock
    for identity in ("cashier", None, "owner"):
        if identity:
            auth_service.login(identity, f"{identity}123")
            if identity == "owner":
                with factory.begin() as session:
                    session.scalar(
                        select(User).where(User.username == "owner")
                    ).is_active = False
        else:
            auth_service.logout()
        for operation in (
            inventory.stock_overview,
            inventory.list_movements,
            lambda: inventory.receive_stock(piece.id, "1"),
            lambda: inventory.adjust_stock(
                piece.id, "1", reason="Correction", note="Count"
            ),
        ):
            with pytest.raises(AuthError):
                operation()


def test_filters_references_and_inactive_products(stock):
    factory, piece, _ = stock
    yesterday = date.today() - timedelta(days=1)
    inventory.receive_stock(piece.id, "2", received_date=yesterday)
    with factory.begin() as session:
        product = session.get(Product, piece.id)
        product.is_active = False
        owner_id = session.scalar(select(User.id).where(User.role == "owner"))
        sale = Sale(
            status="completed",
            cashier_id=owner_id,
            total=10,
            receipt_number="PAW-TEST-0001",
        )
        session.add(sale)
        session.flush()
        session.add_all(
            [
                StockMovement(
                    product_id=piece.id,
                    user_id=owner_id,
                    movement_type="sale",
                    quantity_change=-1,
                    stock_after=product.stock_quantity - 1,
                    reference_type="sale",
                    reference_id=sale.id,
                    created_at=datetime.combine(yesterday, datetime.max.time()),
                ),
                StockMovement(
                    product_id=piece.id,
                    user_id=owner_id,
                    movement_type="refund",
                    quantity_change=1,
                    stock_after=product.stock_quantity,
                    reference_type="refund",
                    reference_id=42,
                    created_at=datetime.combine(yesterday, datetime.min.time()),
                ),
            ]
        )
    rows = inventory.list_movements(
        product_id=piece.id, date_from=yesterday, date_to=yesterday
    )
    assert len(rows) == 3
    assert rows[0].reference == "PAW-TEST-0001" and rows[0].quantity_change == -1
    refund = inventory.list_movements(product_id=piece.id, movement_type="refund")
    assert refund[0].reference == "refund #42" and refund[0].quantity_change == 1
    assert inventory.stock_overview(piece.name)[0].is_active is False
    assert inventory.list_movements(product_id=999999) == []


@pytest.mark.parametrize(
    "filters",
    [
        {"movement_type": "invalid"},
        {"date_from": "2026-01-01"},
        {"date_from": date(2026, 2, 1), "date_to": date(2026, 1, 1)},
    ],
)
def test_invalid_history_filters(stock, filters):
    with pytest.raises(ValidationError):
        inventory.list_movements(**filters)


def test_missing_product_and_invalid_delivery_metadata(stock):
    for operation in (
        lambda: inventory.receive_stock(999999, "1"),
        lambda: inventory.adjust_stock(999999, "1", reason="Other", note="Count"),
    ):
        with pytest.raises(NotFoundError):
            operation()
    _, piece, _ = stock
    for kwargs in (
        {"received_date": "bad"},
        {"received_date": date.today() + timedelta(days=1)},
        {"supplier": "s" * 121},
        {"supplier": "s" * 120, "note": "n" * 140},
    ):
        with pytest.raises(ValidationError):
            inventory.receive_stock(piece.id, "1", **kwargs)
