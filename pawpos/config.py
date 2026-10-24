"""Project paths and local database configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

SHOP_NAME = "PawPOS"
REFUND_WINDOW_DAYS = 7
THEME = "cosmo"
ASSETS_DIR = PROJECT_ROOT / "assets"
PRODUCT_IMAGES_DIR = ASSETS_DIR / "products"
RECEIPTS_DIR = PROJECT_ROOT / "receipts"
LOG_PATH = PROJECT_ROOT / "pawpos.log"


def database_url() -> URL:
    """Build a URL without interpreting special characters in credentials."""
    return URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "pawpos"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "pawpos"),
        query={"charset": "utf8mb4"},
    )
