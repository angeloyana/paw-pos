import unittest

from pawpos.core.errors import ValidationError
from pawpos.core.security import hash_password, verify_password


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password("owner123")

    def test_hash_verifies_only_the_correct_password(self):
        self.assertNotEqual(self.password_hash, "owner123")
        self.assertTrue(verify_password("owner123", self.password_hash))
        self.assertFalse(verify_password("wrong", self.password_hash))

    def test_hashes_use_random_salts(self):
        self.assertNotEqual(hash_password("owner123"), self.password_hash)

    def test_invalid_passwords_are_rejected(self):
        for value in ("", "   ", "a" * 73, "🐾" * 19, None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                hash_password(value)

    def test_long_password_is_not_truncated(self):
        password = "a" * 72
        hashed = hash_password(password)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password(password + "b", hashed))

    def test_malformed_hashes_and_inputs_fail_verification(self):
        for password, hashed in (
            ("owner123", "invalid"),
            ("owner123", "🐾"),
            (None, self.password_hash),
            ("owner123", None),
            ("", self.password_hash),
        ):
            with self.subTest(password=password):
                self.assertFalse(verify_password(password, hashed))
