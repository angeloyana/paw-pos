"""Completed-sale receipts, 80 mm PDFs, and the system PDF viewer handoff."""

import os
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from pawpos.config import ASSETS_DIR, RECEIPTS_DIR, SHOP_NAME
from pawpos.core.errors import BusinessRuleError, NotFoundError, ValidationError
from pawpos.core.money import format_peso, format_qty
from pawpos.db.base import session_scope
from pawpos.models import Sale
from pawpos.services.auth_service import _require_user


@dataclass(frozen=True)
class ReceiptLine:
    product_name: str
    quantity: Decimal
    unit_type: str
    unit_price: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class Receipt:
    sale_id: int
    receipt_number: str
    completed_at: datetime
    cashier_name: str
    customer_name: str | None
    lines: tuple[ReceiptLine, ...]
    total: Decimal
    payment_method: str
    amount_received: Decimal | None
    change_amount: Decimal | None
    gcash_reference: str | None


def build_receipt(sale_id: int) -> Receipt:
    """Load immutable receipt data from a committed sale's saved item snapshots."""
    if type(sale_id) is not int or sale_id <= 0:
        raise ValidationError("Choose a valid sale.")
    with session_scope() as session:
        _require_user(session)
        sale = session.scalar(
            select(Sale)
            .where(Sale.id == sale_id)
            .options(
                joinedload(Sale.cashier),
                joinedload(Sale.customer),
                selectinload(Sale.items),
            )
        )
        if sale is None:
            raise NotFoundError("Sale not found.")
        if (
            sale.status != "completed"
            or not sale.receipt_number
            or sale.completed_at is None
        ):
            raise BusinessRuleError("Receipts are available only for completed sales.")
        return Receipt(
            sale.id,
            sale.receipt_number,
            sale.completed_at,
            sale.cashier.full_name,
            sale.customer.name if sale.customer else None,
            tuple(
                ReceiptLine(
                    item.product_name,
                    item.quantity,
                    item.unit_type,
                    item.unit_price,
                    item.line_total,
                )
                for item in sorted(sale.items, key=lambda row: row.id)
            ),
            sale.total,
            sale.payment_method,
            sale.amount_received,
            sale.change_amount,
            sale.gcash_reference,
        )


def receipt_text(receipt: Receipt) -> str:
    """Format the same wrapped content for preview and a narrow printed receipt."""
    width = 38
    lines = [
        SHOP_NAME.center(width),
        receipt.receipt_number,
        receipt.completed_at.strftime("%Y-%m-%d %H:%M:%S"),
    ]

    def append(value: str) -> None:
        lines.extend(textwrap.wrap(" ".join(value.split()), width=width))

    append(f"Cashier: {receipt.cashier_name}")
    if receipt.customer_name:
        append(f"Customer: {receipt.customer_name}")
    lines.append("-" * width)
    for item in receipt.lines:
        append(item.product_name)
        append(
            f"{format_qty(item.quantity, item.unit_type)} x "
            + format_peso(item.unit_price)
            + ("/kg" if item.unit_type == "kg" else " each")
        )
        lines.append(format_peso(item.line_total).rjust(width))
    lines.append("-" * width)
    append(f"TOTAL: {format_peso(receipt.total)}")
    append("Payment: Cash" if receipt.payment_method == "cash" else "Payment: GCash")
    if receipt.payment_method == "cash":
        append(f"Received: {format_peso(receipt.amount_received)}")
        append(f"Change: {format_peso(receipt.change_amount)}")
    else:
        append(f"Reference: {receipt.gcash_reference}")
    lines.extend(["", "Thank you for shopping at PawPOS!".center(width)])
    return "\n".join(lines)


def make_pdf(receipt: Receipt, output_dir: str | Path | None = None) -> Path:
    """Write an 80 mm PDF atomically, embedding a font that contains the peso sign."""
    if not re.fullmatch(r"PAW-[0-9]{8}-[0-9]{4}", receipt.receipt_number):
        raise ValidationError("Invalid receipt number.")
    directory = Path(output_dir) if output_dir is not None else RECEIPTS_DIR
    path = directory / f"{receipt.receipt_number}.pdf"
    temporary = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=directory, suffix=".pdf", delete=False) as file:
            temporary = Path(file.name)
        font_name = "PawPOSReceipt"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(
                TTFont(font_name, str(ASSETS_DIR / "fonts" / "DejaVuSansMono.ttf"))
            )
        lines = receipt_text(receipt).split("\n")
        margin, leading = 4 * mm, 11
        height = max(80 * mm, 2 * margin + len(lines) * leading)
        document = canvas.Canvas(str(temporary), pagesize=(80 * mm, height))
        document.setTitle(receipt.receipt_number)
        document.setAuthor(SHOP_NAME)
        document.setFont(font_name, 8)
        y = height - margin - 8
        for line in lines:
            document.drawString(margin, y, line)
            y -= leading
        document.save()
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def print_receipt(receipt: Receipt, output_dir: str | Path | None = None) -> Path:
    """Generate a PDF and open its default viewer; printing stays in the OS UI."""
    path = make_pdf(receipt, output_dir).resolve()
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        else:
            command = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen(
                [command, str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except OSError:
        raise BusinessRuleError(
            f"Cannot open the PDF viewer. Open this receipt manually: {path}"
        ) from None
    return path
