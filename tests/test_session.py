import unittest
from dataclasses import FrozenInstanceError

from pawpos.core import session


class CurrentUserTests(unittest.TestCase):
    def tearDown(self):
        session.logout()

    def test_login_and_logout(self):
        user = session.CurrentUser(1, "owner", "Shop Owner", "owner")
        session.set_current_user(user)
        self.assertEqual(session.current_user, user)
        session.logout()
        self.assertIsNone(session.current_user)

    def test_identity_is_immutable(self):
        user = session.CurrentUser(2, "cashier", "Cashier One", "cashier")
        with self.assertRaises(FrozenInstanceError):
            user.role = "owner"
