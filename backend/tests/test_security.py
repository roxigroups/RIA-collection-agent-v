"""Unit tests for security validations and access control."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dashboard_db import Dashboard


class SecurityValidationTests(unittest.TestCase):
    def test_update_user_invalid_role(self):
        db = Dashboard.__new__(Dashboard)
        with self.assertRaises(ValueError) as ctx:
            db.update_user("TENANT-001", "U-123", {"role": "HACKER_ADMIN"})
        self.assertIn("Invalid user role", str(ctx.exception))

    def test_update_user_invalid_status(self):
        db = Dashboard.__new__(Dashboard)
        with self.assertRaises(ValueError) as ctx:
            db.update_user("TENANT-001", "U-123", {"st": "COMPROMISED"})
        self.assertIn("Invalid user status", str(ctx.exception))

    def test_update_user_valid_enums(self):
        db = Dashboard.__new__(Dashboard)
        db.connection = MagicMock()
        mock_conn = MagicMock()
        db.connection.return_value.__enter__.return_value = mock_conn

        # Valid role & status should not raise ValueError
        db.update_user("TENANT-001", "U-123", {"role": "CM", "st": "Active"})
        self.assertTrue(mock_conn.execute.called)


if __name__ == "__main__":
    unittest.main()
