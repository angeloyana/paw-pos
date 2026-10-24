"""Category maintenance with soft deletion and product-reference protection."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from pawpos.core.errors import BusinessRuleError, NotFoundError, ValidationError
from pawpos.db.base import session_scope
from pawpos.models import Category, Product
from pawpos.services.auth_service import _require_owner, _require_user
from pawpos.services.catalog_validation import flag, text


@dataclass(frozen=True)
class CategoryDetails:
    id: int
    name: str
    description: str
    is_food: bool
    is_active: bool


def _details(category: Category) -> CategoryDetails:
    return CategoryDetails(
        category.id,
        category.name,
        category.description or "",
        category.is_food,
        category.is_active,
    )


def list_categories(*, include_inactive: bool = False) -> list[CategoryDetails]:
    """Return active categories; only an owner may include inactive rows."""
    with session_scope() as session:
        (_require_owner if include_inactive else _require_user)(session)
        query = select(Category).order_by(Category.name)
        if not include_inactive:
            query = query.where(Category.is_active.is_(True))
        return [_details(category) for category in session.scalars(query)]


def save_category(
    name: str,
    *,
    description: str = "",
    is_food: bool = False,
    is_active: bool = True,
    category_id: int | None = None,
) -> CategoryDetails:
    """Create or edit a category, retaining its identity for historical products."""
    try:
        with session_scope() as session:
            _require_owner(session)
            name = text(name, "Name", 80)
            description = text(description, "Description", 255, required=False)
            flag(is_food, "Food category")
            flag(is_active, "Active")
            category = (
                session.get(Category, category_id)
                if category_id is not None
                else Category()
            )
            if category is None:
                raise NotFoundError("Category not found.")
            duplicate = session.scalar(
                select(Category.id).where(func.lower(Category.name) == name.lower())
            )
            if duplicate is not None and duplicate != category_id:
                raise ValidationError("A category with this name already exists.")
            if not is_active and category_id is not None:
                _check_unused(session, category_id)
            category.name, category.description = name, description or None
            category.is_food, category.is_active = is_food, is_active
            session.add(category)
            session.flush()
            result = _details(category)
    except IntegrityError:
        raise ValidationError("A category with this name already exists.") from None
    return result


def _check_unused(session, category_id: int) -> None:
    if (
        session.scalar(
            select(Product.id).where(Product.category_id == category_id).limit(1)
        )
        is not None
    ):
        raise BusinessRuleError(
            "Cannot deactivate a category that has products, including inactive products."
        )


def deactivate_category(category_id: int) -> None:
    """Retire an unused category without deleting its row."""
    with session_scope() as session:
        _require_owner(session)
        category = session.get(Category, category_id)
        if category is None:
            raise NotFoundError("Category not found.")
        _check_unused(session, category_id)
        category.is_active = False
