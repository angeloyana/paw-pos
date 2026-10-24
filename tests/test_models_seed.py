from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_mock_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from pawpos.core.security import verify_password
from pawpos.db.base import Base
from pawpos.db.seed import seed_database
from pawpos.models import Category, Product, Sale, SaleItem, StockMovement, User


def test_all_tables_exist_and_compile_for_mysql(session_factory):
    with session_factory() as session:
        assert set(inspect(session.bind).get_table_names()) == {
            "users",
            "categories",
            "products",
            "customers",
            "sales",
            "sale_items",
            "void_logs",
            "stock_movements",
            "refund_requests",
            "refund_items",
            "refund_payouts",
            "refund_payout_corrections",
            "refund_decision_notices",
            "refund_tracking_state",
        }
    statements = []
    engine = create_mock_engine(
        "mysql+pymysql://",
        lambda sql, *args, **kwargs: statements.append(
            str(sql.compile(dialect=engine.dialect))
        ),
    )
    Base.metadata.create_all(engine)
    tables = [sql for sql in statements if "CREATE TABLE" in sql]
    assert len(tables) == 14
    assert all("InnoDB" in sql and "utf8mb4" in sql for sql in tables)


def test_seed_users_catalog_and_every_positive_stock_has_history(session_factory):
    assert seed_database() is True
    with session_factory() as session:
        users = session.scalars(select(User).order_by(User.id)).all()
        assert [(u.username, u.role, u.is_active) for u in users] == [
            ("owner", "owner", True),
            ("cashier", "cashier", True),
        ]
        assert verify_password("owner123", users[0].password_hash)
        assert verify_password("cashier123", users[1].password_hash)
        assert session.scalar(select(func.count()).select_from(Category)) == 8
        products = session.scalars(select(Product)).all()
        assert len(products) == 14
        for product in products:
            assert isinstance(product.unit_price, Decimal)
            assert isinstance(product.stock_quantity, Decimal)
            assert product.category.is_active
            movements = product.stock_movements
            if product.stock_quantity == 0:
                assert movements == []
            else:
                assert len(movements) == 1
                assert movements[0].quantity_change == product.stock_quantity
                assert movements[0].stock_after == product.stock_quantity
                assert movements[0].movement_type == "stock_received"
                assert movements[0].user_id == users[0].id
                assert movements[0].note == "Initial stock"


def test_repeated_seed_preserves_existing_inventory_and_passwords(session_factory):
    seed_database()
    with session_factory.begin() as session:
        owner = session.scalar(select(User).where(User.username == "owner"))
        owner.password_hash = "existing hash"
        owner.is_active = False
    assert seed_database() is False
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 2
        assert session.scalar(select(func.count()).select_from(Product)) == 14
        assert session.scalar(select(func.count()).select_from(StockMovement)) == 13
        owner = session.scalar(select(User).where(User.username == "owner"))
        assert owner.password_hash == "existing hash"
        assert owner.is_active is False


def test_seed_rolls_back_users_and_inventory_on_failure(session_factory):
    with patch(
        "pawpos.db.seed.PRODUCTS", (("Invalid", "Toys", "piece", "-1", "2", "0"),)
    ):
        with pytest.raises(IntegrityError):
            seed_database()
    with session_factory() as session:
        for model in (User, Category, Product, StockMovement):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_database_rejects_negative_stock_and_invalid_foreign_keys(session_factory):
    seed_database()
    with pytest.raises(IntegrityError), session_factory.begin() as session:
        session.execute(text("UPDATE products SET stock_quantity = -1 WHERE id = 1"))
    with pytest.raises(IntegrityError), session_factory.begin() as session:
        session.execute(text("UPDATE products SET category_id = 999 WHERE id = 1"))


def test_held_sale_deletion_cascades_items_without_changing_stock(session_factory):
    seed_database()
    with session_factory.begin() as session:
        product = session.scalar(select(Product))
        product_id, stock = product.id, product.stock_quantity
        sale = Sale(status="held", cashier_id=1, total=product.unit_price)
        sale.items.append(
            SaleItem(
                product=product,
                product_name=product.name,
                unit_type=product.unit_type,
                quantity=Decimal("1"),
                unit_price=product.unit_price,
                line_total=product.unit_price,
            )
        )
        session.add(sale)
        session.flush()
        sale_id = sale.id
    with session_factory.begin() as session:
        session.delete(session.get(Sale, sale_id))
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SaleItem)) == 0
        assert session.get(Product, product_id).stock_quantity == stock
