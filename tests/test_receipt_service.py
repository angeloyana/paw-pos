import re
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from pawpos.core import session as login_session
from pawpos.core.errors import (
    AuthError,
    BusinessRuleError,
    NotFoundError,
    ValidationError,
)
from pawpos.core.session import CurrentUser
from pawpos.models import Category, Customer, Product, Sale, User
from pawpos.services import receipt_service, sale_service
from pawpos.services.cart import Cart
from pawpos.services.receipt_service import Receipt, ReceiptLine
from pawpos.services.sale_service import Payment


@pytest.fixture
def receipt():
    return Receipt(
        1,
        "PAW-20261024-0001",
        datetime(2026, 10, 24, 12, 30),
        "Cashier One",
        "Ana",
        (
            ReceiptLine(
                "Dog Food Loose",
                Decimal("1.375"),
                "kg",
                Decimal("95"),
                Decimal("130.63"),
            ),
            ReceiptLine("Pouch", Decimal("2"), "piece", Decimal("28"), Decimal("56")),
        ),
        Decimal("186.63"),
        "cash",
        Decimal("200"),
        Decimal("13.37"),
        None,
    )


def test_receipt_loads_saved_snapshots_and_checks_auth(session_factory):
    with session_factory.begin() as session:
        user = User(
            username="cashier",
            full_name="Cashier One",
            role="cashier",
            password_hash="unused",
        )
        category = Category(name="Food")
        customer = Customer(name="Ana")
        session.add_all([user, category, customer])
        session.flush()
        session.add(
            Product(
                name="Pouch",
                category_id=category.id,
                unit_type="piece",
                unit_price=28,
                stock_quantity=3,
            )
        )
        login_session.set_current_user(
            CurrentUser(user.id, user.username, user.full_name, user.role)
        )
    cart = Cart()
    cart.add_piece(1, "Pouch", 28, stock_quantity=3)
    sale = sale_service.complete_sale(cart, Payment("cash", 100), customer_id=1)
    with session_factory.begin() as session:
        session.get(Product, 1).name = "Renamed"
        session.get(Product, 1).unit_price = 30
        held = Sale(status="held", cashier_id=1, total=0)
        session.add(held)
        session.flush()
        held_id = held.id
    receipt = receipt_service.build_receipt(sale.id)
    assert receipt.lines[0].product_name == "Pouch"
    assert receipt.lines[0].unit_price == 28
    assert receipt.customer_name == "Ana" and receipt.cashier_name == "Cashier One"
    assert receipt.change_amount == 72
    with pytest.raises(BusinessRuleError):
        receipt_service.build_receipt(held_id)
    with pytest.raises(NotFoundError):
        receipt_service.build_receipt(999)
    with pytest.raises(ValidationError):
        receipt_service.build_receipt(True)
    login_session.logout()
    with pytest.raises(AuthError):
        receipt_service.build_receipt(sale.id)


def test_preview_has_all_cash_fields_and_gcash_fields(receipt):
    text = receipt_service.receipt_text(receipt)
    for value in (
        "PawPOS",
        "PAW-20261024-0001",
        "2026-10-24 12:30:00",
        "Cashier One",
        "Customer: Ana",
        "1.375 kg x ₱95.00/kg",
        "₱130.63",
        "2 x ₱28.00 each",
        "₱56.00",
        "TOTAL: ₱186.63",
        "Received: ₱200.00",
        "Change: ₱13.37",
    ):
        assert value in text
    gcash = replace(
        receipt,
        payment_method="gcash",
        customer_name=None,
        amount_received=None,
        change_amount=None,
        gcash_reference="REF-123",
    )
    text = receipt_service.receipt_text(gcash)
    assert "Payment: GCash" in text and "Reference: REF-123" in text
    assert "Received" not in text and "Change" not in text and "Customer:" not in text


def test_pdf_is_80mm_embeds_peso_font_wraps_and_grows(receipt, tmp_path):
    receipt = replace(
        receipt,
        cashier_name="Long cashier name " * 5,
        customer_name="Long customer name " * 5,
        lines=(replace(receipt.lines[0], product_name="Long product " * 20),) * 20,
    )
    lines = receipt_service.receipt_text(receipt).split("\n")
    assert all(len(line) <= 38 for line in lines)
    drawn = []
    original = Canvas.drawString

    def record(canvas, x, y, text, *args, **kwargs):
        drawn.append((x, y, text))
        return original(canvas, x, y, text, *args, **kwargs)

    with patch.object(Canvas, "drawString", record):
        path = receipt_service.make_pdf(receipt, tmp_path)
    data = path.read_bytes()
    assert data.startswith(b"%PDF-")
    box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", data)
    width, height = (float(value) for value in box.groups())
    assert width == pytest.approx(80 * mm, abs=0.001)
    assert height > 80 * mm
    assert b"/FontFile2" in data and b"/ToUnicode" in data
    font = pdfmetrics.getFont("PawPOSReceipt")
    assert 0x20B1 in font.face.charToGlyph
    assert all(
        x + pdfmetrics.stringWidth(text, "PawPOSReceipt", 8) <= width - 4 * mm
        for x, _y, text in drawn
    )
    assert min(y for _x, y, _text in drawn) > 0
    assert len(list(tmp_path.iterdir())) == 1


def test_pdf_failure_preserves_existing_file_and_cleans_temporary(receipt, tmp_path):
    path = receipt_service.make_pdf(receipt, tmp_path)
    before = path.read_bytes()
    with (
        patch.object(Canvas, "save", side_effect=OSError("disk full")),
        pytest.raises(OSError),
    ):
        receipt_service.make_pdf(receipt, tmp_path)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    with pytest.raises(ValidationError):
        receipt_service.make_pdf(replace(receipt, receipt_number="../escape"), tmp_path)


@pytest.mark.parametrize(
    "platform,opener", [("linux", "xdg-open"), ("darwin", "open"), ("win32", None)]
)
def test_print_handoff_uses_default_viewer(receipt, tmp_path, platform, opener):
    with (
        patch.object(receipt_service.sys, "platform", platform),
        patch.object(receipt_service.os, "startfile", create=True) as startfile,
        patch.object(receipt_service.subprocess, "Popen") as popen,
    ):
        path = receipt_service.print_receipt(receipt, tmp_path)
    assert path.is_file()
    if opener:
        assert popen.call_args.args[0] == [opener, str(path)]
        startfile.assert_not_called()
    else:
        startfile.assert_called_once_with(str(path))
        popen.assert_not_called()


def test_viewer_launch_error_keeps_pdf_available(receipt, tmp_path):
    with (
        patch.object(receipt_service.sys, "platform", "linux"),
        patch.object(
            receipt_service.subprocess, "Popen", side_effect=OSError("no viewer")
        ),
        pytest.raises(BusinessRuleError, match="manually"),
    ):
        receipt_service.print_receipt(receipt, tmp_path)
    assert (tmp_path / f"{receipt.receipt_number}.pdf").is_file()
