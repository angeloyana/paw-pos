from decimal import Decimal

import pytest
from PIL import Image
from sqlalchemy import event, func, select

from pawpos.core.errors import (
    AuthError,
    BusinessRuleError,
    NotFoundError,
    ValidationError,
)
from pawpos.core.security import hash_password
from pawpos.models import Category, Product, StockMovement, User
from pawpos.services import auth_service, category_service, product_service


@pytest.fixture(scope="module")
def password_hash():
    return hash_password("test-password")


@pytest.fixture
def catalog(session_factory, password_hash):
    with session_factory.begin() as session:
        session.add_all(
            [
                User(
                    username="owner",
                    full_name="Owner",
                    role="owner",
                    password_hash=password_hash,
                ),
                User(
                    username="cashier",
                    full_name="Cashier",
                    role="cashier",
                    password_hash=password_hash,
                ),
            ]
        )
    auth_service.login("owner", "test-password")
    category = category_service.save_category("Food", is_food=True)
    return session_factory, category


def create(category, **overrides):
    arguments = dict(
        name="Dog Food",
        category_id=category.id,
        unit_price="95.00",
        unit_type="kg",
        initial_stock="1.375",
        low_stock_threshold="0.5",
    )
    arguments.update(overrides)
    return product_service.save_product(**arguments)


def test_category_create_edit_soft_delete_and_reactivate(catalog):
    factory, category = catalog
    changed = category_service.save_category(
        " Dry food ", description=" Food bags ", is_food=True, category_id=category.id
    )
    assert changed.name == "Dry food" and changed.description == "Food bags"
    category_service.deactivate_category(category.id)
    assert category_service.list_categories() == []
    assert category_service.list_categories(include_inactive=True)[0].is_active is False
    with factory() as session:
        assert session.get(Category, category.id) is not None
    category_service.save_category("Dry food", category_id=category.id)
    assert len(category_service.list_categories()) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " food "},
        {"name": ""},
        {"name": "n" * 81},
        {"name": "Other", "description": "d" * 256},
        {"name": "Other", "is_food": "false"},
    ],
)
def test_invalid_or_duplicate_category_is_rejected(catalog, changes):
    with pytest.raises(ValidationError):
        category_service.save_category(**changes)
    assert len(category_service.list_categories()) == 1


def test_category_with_inactive_products_cannot_be_deactivated(catalog):
    _, category = catalog
    product = create(category)
    product_service.deactivate_product(product.id)
    with pytest.raises(BusinessRuleError):
        category_service.deactivate_category(category.id)
    with pytest.raises(BusinessRuleError):
        category_service.save_category("Food", is_active=False, category_id=category.id)
    assert category_service.list_categories()[0].is_active


def test_initial_stock_movement_and_decimal_values(catalog):
    factory, category = catalog
    product = create(category)
    assert product.stock_quantity == Decimal("1.375")
    assert product.unit_price == Decimal("95.00")
    with factory() as session:
        movement = session.scalar(select(StockMovement))
        assert movement.product_id == product.id
        assert movement.quantity_change == movement.stock_after == Decimal("1.375")
        assert movement.note == "Initial stock"
        assert movement.user_id == 1 and movement.movement_type == "stock_received"


def test_zero_stock_has_no_movement(catalog):
    factory, category = catalog
    create(category, initial_stock="0")
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(StockMovement)) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"name": "n" * 121},
        {"unit_price": "-1"},
        {"unit_price": "1.001"},
        {"unit_price": 1.5},
        {"unit_price": "NaN"},
        {"unit_price": "100000000"},
        {"unit_type": "bag"},
        {"initial_stock": "-1"},
        {"initial_stock": "0.0001"},
        {"initial_stock": "10000000"},
        {"unit_type": "piece", "initial_stock": "1.5"},
        {"unit_type": "piece", "initial_stock": "1", "low_stock_threshold": "0.5"},
        {"low_stock_threshold": "-1"},
        {"supplier": "s" * 121},
        {"is_active": "false"},
        {"category_id": 999},
    ],
)
def test_invalid_product_is_not_saved(catalog, changes):
    factory, category = catalog
    with pytest.raises(ValidationError):
        create(category, **changes)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Product)) == 0
        assert session.scalar(select(func.count()).select_from(StockMovement)) == 0


def test_edit_preserves_stock_and_history_and_disallows_stock_entry(catalog):
    factory, category = catalog
    product = create(category)
    updated = product_service.save_product(
        "Renamed",
        category.id,
        "99.50",
        "kg",
        product_id=product.id,
        low_stock_threshold="0.25",
        supplier="Supplier",
    )
    assert updated.stock_quantity == Decimal("1.375")
    assert updated.name == "Renamed" and updated.supplier == "Supplier"
    with pytest.raises(BusinessRuleError, match="Inventory"):
        product_service.save_product(
            "Changed", category.id, "1", "kg", product_id=product.id, initial_stock="0"
        )
    with factory() as session:
        assert session.get(Product, product.id).name == "Renamed"
        assert session.scalar(select(func.count()).select_from(StockMovement)) == 1


def test_unit_change_requires_no_stock_or_history(catalog):
    _, category = catalog
    stocked = create(category)
    with pytest.raises(BusinessRuleError, match="Unit type"):
        product_service.save_product(
            "Changed", category.id, "1", "piece", product_id=stocked.id
        )
    empty = create(category, initial_stock="0")
    changed = product_service.save_product(
        "Empty toy", category.id, "1", "piece", product_id=empty.id
    )
    assert changed.unit_type == "piece"


def test_search_category_filter_and_inactive_visibility(catalog):
    _, category = catalog
    product = create(category, name="Dog Food 100%")
    toys = category_service.save_category("Toys")
    create(
        toys, name="Ball", unit_type="piece", initial_stock="2", low_stock_threshold="1"
    )
    assert [p.id for p in product_service.list_products("DOG", category.id)] == [
        product.id
    ]
    assert product_service.list_products("_") == []
    assert [p.id for p in product_service.list_products("%", category.id)] == [
        product.id
    ]
    product_service.deactivate_product(product.id)
    assert product_service.list_products(category_id=category.id) == []
    assert len(product_service.list_products(include_inactive=True)) == 2


def test_inactive_category_cannot_receive_products(catalog):
    _, category = catalog
    category_service.deactivate_category(category.id)
    with pytest.raises(ValidationError, match="active category"):
        create(category)


@pytest.fixture
def image_store(tmp_path, monkeypatch):
    monkeypatch.setattr(product_service, "PROJECT_ROOT", tmp_path)
    destination = tmp_path / "assets" / "products"
    monkeypatch.setattr(product_service, "PRODUCT_IMAGES_DIR", destination)
    source = tmp_path / "source.png"
    Image.new("RGB", (10, 10), "blue").save(source)
    return source, destination


def test_image_copy_survives_original_deletion_and_edit(catalog, image_store):
    _, category = catalog
    source, destination = image_store
    product = create(category, image_source=source)
    assert product.image_path.startswith("assets/products/")
    copied = destination / product.image_path.split("/")[-1]
    assert copied.read_bytes() == source.read_bytes()
    source.unlink()
    updated = product_service.save_product(
        "Renamed", category.id, "95", "kg", product_id=product.id
    )
    assert updated.image_path == product.image_path and copied.exists()


def test_invalid_image_leaves_no_product_or_copy(catalog, image_store):
    factory, category = catalog
    source, destination = image_store
    source.write_text("not an image")
    with pytest.raises(ValidationError, match="valid image"):
        create(category, image_source=source)
    assert not destination.exists()
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Product)) == 0


def test_failed_commit_removes_copied_image_and_rolls_back_stock(catalog, image_store):
    factory, category = catalog
    source, destination = image_store

    def fail_commit(session):
        raise RuntimeError("Simulated database failure")

    event.listen(factory, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError):
            create(category, image_source=source)
    finally:
        event.remove(factory, "before_commit", fail_commit)
    assert list(destination.iterdir()) == []
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Product)) == 0
        assert session.scalar(select(func.count()).select_from(StockMovement)) == 0


def test_cashier_reads_only_active_catalog_and_cannot_write(catalog):
    _, category = catalog
    create(category)
    auth_service.login("cashier", "test-password")
    assert len(category_service.list_categories()) == 1
    assert len(product_service.list_products()) == 1
    for operation in (
        lambda: create(category),
        lambda: category_service.save_category("Forbidden"),
        lambda: category_service.deactivate_category(category.id),
        lambda: product_service.deactivate_product(1),
        lambda: product_service.list_products(include_inactive=True),
        lambda: category_service.list_categories(include_inactive=True),
    ):
        with pytest.raises(AuthError):
            operation()
    auth_service.logout()
    with pytest.raises(AuthError):
        product_service.list_products()


def test_missing_catalog_rows_report_not_found(catalog):
    _, category = catalog
    for operation in (
        lambda: category_service.deactivate_category(999),
        lambda: category_service.save_category("Missing", category_id=999),
        lambda: product_service.deactivate_product(999),
        lambda: product_service.save_product(
            "Missing", category.id, "1", "kg", product_id=999
        ),
    ):
        with pytest.raises(NotFoundError):
            operation()
