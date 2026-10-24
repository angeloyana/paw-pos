import pytest

from pawpos.core import session as login_session
from pawpos.core.errors import AuthError, ValidationError
from pawpos.core.session import CurrentUser
from pawpos.models import User
from pawpos.services import customer_service


@pytest.fixture
def customer_user(session_factory):
    with session_factory.begin() as session:
        user = User(
            username="cashier",
            full_name="Cashier",
            role="cashier",
            password_hash="unused",
        )
        session.add(user)
        session.flush()
        login_session.set_current_user(
            CurrentUser(user.id, user.username, user.full_name, user.role)
        )
    return session_factory


def test_quick_add_search_and_optional_contact(customer_user):
    first = customer_service.create_customer(" Ana Cruz ", " 0917 ")
    second = customer_service.create_customer("Ana Cruz")
    assert (first.name, first.contact) == ("Ana Cruz", "0917")
    assert second.contact == "" and second.id != first.id
    assert customer_service.list_customers("CRUZ") == [first, second]
    assert customer_service.list_customers("917") == [first]
    assert customer_service.list_customers("absent") == []


def test_search_treats_wildcards_literally(customer_user):
    special = customer_service.create_customer("A_100%")
    customer_service.create_customer("Another")
    assert customer_service.list_customers("%") == [special]
    assert customer_service.list_customers("_") == [special]


@pytest.mark.parametrize(
    "name,contact",
    [("", ""), (" ", ""), (None, ""), ("x" * 121, ""), ("Ana", "x" * 121)],
)
def test_invalid_customer_does_not_create_rows(customer_user, name, contact):
    with pytest.raises(ValidationError):
        customer_service.create_customer(name, contact)
    assert customer_service.list_customers() == []


def test_requires_active_login(customer_user):
    with customer_user.begin() as session:
        session.get(User, login_session.current_user.id).is_active = False
    with pytest.raises(AuthError):
        customer_service.create_customer("Ana")
    with pytest.raises(AuthError):
        customer_service.list_customers()
    login_session.logout()
    with pytest.raises(AuthError):
        customer_service.list_customers()
