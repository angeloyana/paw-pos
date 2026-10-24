"""Customer lookup and quick creation for signed-in checkout users."""

from dataclasses import dataclass

from sqlalchemy import or_, select

from pawpos.db.base import session_scope
from pawpos.models import Customer
from pawpos.services.auth_service import _require_user
from pawpos.services.catalog_validation import text


@dataclass(frozen=True)
class CustomerDetails:
    id: int
    name: str
    contact: str


def list_customers(search: str = "") -> list[CustomerDetails]:
    """Search names and contacts using literal case-insensitive text."""
    with session_scope() as session:
        _require_user(session)
        search = text(search, "Search", 120, required=False)
        query = select(Customer).order_by(Customer.name, Customer.id)
        if search:
            query = query.where(
                or_(
                    Customer.name.icontains(search, autoescape=True),
                    Customer.contact.icontains(search, autoescape=True),
                )
            )
        return [
            CustomerDetails(row.id, row.name, row.contact or "")
            for row in session.scalars(query)
        ]


def create_customer(name: str, contact: str = "") -> CustomerDetails:
    """Quick-add a customer; contact is optional and names need not be unique."""
    with session_scope() as session:
        _require_user(session)
        name = text(name, "Name", 120)
        contact = text(contact, "Contact", 120, required=False)
        customer = Customer(name=name, contact=contact or None)
        session.add(customer)
        session.flush()
        return CustomerDetails(customer.id, customer.name, customer.contact or "")
