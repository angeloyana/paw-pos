"""First-run demo catalog; never change an existing installation."""

from sqlalchemy import select

from pawpos.core.money import D
from pawpos.core.security import hash_password
from pawpos.db.base import session_scope
from pawpos.models import Category, Product, StockMovement, User

CATEGORIES = (
    ("Dog Food", True),
    ("Cat Food", True),
    ("Fish and Bird Food", True),
    ("Treats", True),
    ("Toys", False),
    ("Accessories", False),
    ("Grooming", False),
    ("Health and Care", False),
)

PRODUCTS = (
    ("Dog Food Loose (Adult)", "Dog Food", "kg", "95.00", "50.000", "10"),
    ("Cat Food Loose (Tuna)", "Cat Food", "kg", "120.00", "40.000", "10"),
    ("Pedigree Adult 1.5kg Pack", "Dog Food", "piece", "285.00", "20", "5"),
    ("Whiskas Pouch 85g", "Cat Food", "piece", "28.00", "60", "15"),
    ("Fish Flakes 50g", "Fish and Bird Food", "piece", "45.00", "25", "5"),
    ("Bird Seed Mix", "Fish and Bird Food", "kg", "80.00", "15.000", "5"),
    ("Dog Biscuit Treats", "Treats", "piece", "65.00", "30", "8"),
    ("Rubber Chew Toy", "Toys", "piece", "150.00", "12", "3"),
    ("Cat Feather Wand", "Toys", "piece", "85.00", "3", "5"),
    ("Nylon Dog Collar (M)", "Accessories", "piece", "120.00", "18", "5"),
    ("Dog Leash 1.2m", "Accessories", "piece", "180.00", "10", "3"),
    ("Pet Shampoo 250ml", "Grooming", "piece", "210.00", "14", "4"),
    ("Flea and Tick Spray", "Health and Care", "piece", "260.00", "0", "3"),
    ("Stainless Food Bowl", "Accessories", "piece", "95.00", "22", "5"),
)


def seed_database() -> bool:
    """Create demo users and inventory atomically only when no users exist."""
    with session_scope() as session:
        if session.scalar(select(User.id).limit(1)) is not None:
            return False
        owner = User(
            username="owner",
            full_name="Shop Owner",
            role="owner",
            password_hash=hash_password("owner123"),
        )
        cashier = User(
            username="cashier",
            full_name="Cashier One",
            role="cashier",
            password_hash=hash_password("cashier123"),
        )
        session.add_all([owner, cashier])
        categories = {
            name: Category(name=name, is_food=food) for name, food in CATEGORIES
        }
        session.add_all(categories.values())
        session.flush()
        for name, category, unit, price, stock, threshold in PRODUCTS:
            product = Product(
                name=name,
                category=categories[category],
                unit_type=unit,
                unit_price=D(price),
                stock_quantity=D(stock),
                low_stock_threshold=D(threshold),
            )
            session.add(product)
            if D(stock) > 0:
                session.add(
                    StockMovement(
                        product=product,
                        user_id=owner.id,
                        movement_type="stock_received",
                        quantity_change=D(stock),
                        stock_after=D(stock),
                        note="Initial stock",
                    )
                )
    return True
