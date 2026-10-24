"""Catalog operations; stock can only be entered at product creation."""

import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pawpos.config import PRODUCT_IMAGES_DIR, PROJECT_ROOT
from pawpos.core.errors import BusinessRuleError, NotFoundError, ValidationError
from pawpos.core.money import DecimalInput
from pawpos.db.base import session_scope
from pawpos.models import Category, Product, SaleItem, StockMovement
from pawpos.services.auth_service import _require_owner, _require_user
from pawpos.services.catalog_validation import flag, number, quantity, text


@dataclass(frozen=True)
class ProductDetails:
    id: int
    name: str
    category_id: int
    category_name: str
    unit_price: Decimal
    unit_type: str
    stock_quantity: Decimal
    low_stock_threshold: Decimal
    supplier: str
    image_path: str | None
    is_active: bool


def _details(product: Product) -> ProductDetails:
    return ProductDetails(
        product.id,
        product.name,
        product.category_id,
        product.category.name,
        product.unit_price,
        product.unit_type,
        product.stock_quantity,
        product.low_stock_threshold,
        product.supplier or "",
        product.image_path,
        product.is_active,
    )


def list_products(
    search: str = "", category_id: int | None = None, *, include_inactive: bool = False
) -> list[ProductDetails]:
    """Search by literal case-insensitive name and optionally category."""
    with session_scope() as session:
        (_require_owner if include_inactive else _require_user)(session)
        search = text(search, "Search", 120, required=False)
        query = (
            select(Product)
            .join(Product.category)
            .options(joinedload(Product.category))
            .order_by(Product.name, Product.id)
        )
        if not include_inactive:
            query = query.where(
                Product.is_active.is_(True), Category.is_active.is_(True)
            )
        if search:
            query = query.where(Product.name.icontains(search, autoescape=True))
        if category_id is not None:
            query = query.where(Product.category_id == category_id)
        return [_details(product) for product in session.scalars(query)]


def _copy_image(source: str | Path) -> Path:
    try:
        path = Path(source)
        with Image.open(path) as image:
            extension = {
                "PNG": ".png",
                "JPEG": ".jpg",
                "WEBP": ".webp",
                "GIF": ".gif",
                "BMP": ".bmp",
            }.get(image.format)
            if extension is None:
                raise ValidationError("Choose a PNG, JPEG, WebP, GIF, or BMP image.")
            image.verify()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        raise ValidationError(
            "Cannot read the selected image. Choose a valid image file."
        ) from None
    PRODUCT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    destination = PRODUCT_IMAGES_DIR / f"{uuid4().hex}{extension}"
    try:
        shutil.copyfile(path, destination)
    except OSError:
        destination.unlink(missing_ok=True)
        raise ValidationError("Cannot save the image to assets/products.") from None
    return destination


def save_product(
    name: str,
    category_id: int,
    unit_price: DecimalInput,
    unit_type: str,
    *,
    low_stock_threshold: DecimalInput = "0",
    supplier: str = "",
    is_active: bool = True,
    product_id: int | None = None,
    initial_stock: DecimalInput | None = None,
    image_source: str | Path | None = None,
) -> ProductDetails:
    """Save a product and its initial movement atomically; clean up failed image copies."""
    copied_image = None
    try:
        with session_scope() as session:
            owner = _require_owner(session)
            name = text(name, "Name", 120)
            price = number(unit_price, "Price", 2, "99999999.99")
            threshold = quantity(low_stock_threshold, "Low-stock threshold", unit_type)
            supplier = text(supplier, "Supplier", 120, required=False)
            flag(is_active, "Active")
            category = session.get(Category, category_id)
            if category is None or not category.is_active:
                raise ValidationError("Choose an active category.")
            creating = product_id is None
            product = Product() if creating else session.get(Product, product_id)
            if product is None:
                raise NotFoundError("Product not found.")
            if not creating:
                if initial_stock is not None:
                    raise BusinessRuleError(
                        "Change existing stock through Inventory, not the product form."
                    )
                if product.unit_type != unit_type:
                    has_history = session.scalar(
                        select(StockMovement.id)
                        .where(StockMovement.product_id == product.id)
                        .limit(1)
                    )
                    has_sale = session.scalar(
                        select(SaleItem.id)
                        .where(SaleItem.product_id == product.id)
                        .limit(1)
                    )
                    if (
                        product.stock_quantity != 0
                        or has_history is not None
                        or has_sale is not None
                    ):
                        raise BusinessRuleError(
                            "Unit type cannot change once a product has stock or transaction history."
                        )
            stock = (
                quantity(
                    "0" if initial_stock is None else initial_stock,
                    "Initial stock",
                    unit_type,
                )
                if creating
                else product.stock_quantity
            )
            product.name, product.category = name, category
            product.unit_price, product.unit_type = price, unit_type
            product.low_stock_threshold, product.supplier = threshold, supplier or None
            product.is_active = is_active
            if creating:
                product.stock_quantity = stock
            if image_source is not None:
                copied_image = _copy_image(image_source)
                product.image_path = copied_image.relative_to(PROJECT_ROOT).as_posix()
            session.add(product)
            session.flush()
            if creating and stock > 0:
                session.add(
                    StockMovement(
                        product_id=product.id,
                        user_id=owner.id,
                        movement_type="stock_received",
                        quantity_change=stock,
                        stock_after=stock,
                        note="Initial stock",
                    )
                )
            result = _details(product)
    except Exception:
        if copied_image is not None:
            copied_image.unlink(missing_ok=True)
        raise
    return result


def deactivate_product(product_id: int) -> None:
    """Hide a product from selling while preserving sales and stock history."""
    with session_scope() as session:
        _require_owner(session)
        product = session.get(Product, product_id)
        if product is None:
            raise NotFoundError("Product not found.")
        product.is_active = False
