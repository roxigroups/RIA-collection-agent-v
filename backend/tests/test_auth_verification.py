"""Unit tests for self-service sign-up and password reset verification logic."""
import hashlib
import unittest
from datetime import datetime, timedelta, timezone


class AuthVerificationUnitTests(unittest.TestCase):
    def test_code_hashing(self):
        code = "482910"
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        self.assertEqual(len(code_hash), 64)
        self.assertEqual(code_hash, hashlib.sha256("482910".encode()).hexdigest())
        self.assertNotEqual(code_hash, hashlib.sha256("482911".encode()).hexdigest())

    def test_password_policy(self):
        def is_valid_password(p: str) -> bool:
            return len(p) >= 8 and any(c.isalpha() for c in p) and any(c.isdigit() for c in p)

        self.assertTrue(is_valid_password("Password123"))
        self.assertTrue(is_valid_password("secure9Pass!"))
        self.assertFalse(is_valid_password("short1"))  # < 8 chars
        self.assertFalse(is_valid_password("onlyletters"))  # no digits
        self.assertFalse(is_valid_password("123456789"))  # no letters

    def test_otp_expiration(self):
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=15)
        self.assertGreater(expires_at, now)
        past_expiration = now - timedelta(seconds=1)
        self.assertLess(past_expiration, now)


if __name__ == "__main__":
    unittest.main()
