"""Import every table before schema initialization."""

from pawpos.models.category import Category
from pawpos.models.customer import Customer
from pawpos.models.product import Product
from pawpos.models.refund import RefundItem, RefundRequest
from pawpos.models.refund_tracking import (
    RefundDecisionNotice,
    RefundPayout,
    RefundPayoutCorrection,
    RefundTrackingState,
)
from pawpos.models.sale import Sale, SaleItem, VoidLog
from pawpos.models.stock_movement import StockMovement
from pawpos.models.user import User

__all__ = [
    "Category",
    "Customer",
    "Product",
    "RefundDecisionNotice",
    "RefundPayout",
    "RefundPayoutCorrection",
    "RefundTrackingState",
    "RefundItem",
    "RefundRequest",
    "Sale",
    "SaleItem",
    "StockMovement",
    "User",
    "VoidLog",
]
