import os
import unittest

os.environ["DATABASE_URL"] = "postgresql://dummy:dummy@localhost:5432/dummy"

from dialer import parse_invoice
import ria.script as script
script.load()
from ria.agent import instructions

class TestFlexibleCSV(unittest.TestCase):
    def test_complete_row(self):
        row = {
            "name": "Ravi Kumar",
            "phone": "9876543210",
            "business": "Sri Laxmi Enterprises",
            "invoice_no": "INV-2026-001",
            "amount": "15000",
            "due_date": "15-10-2026",
            "language": "te",
        }
        inv, err = parse_invoice(row)
        self.assertEqual(err, "")
        self.assertIsNotNone(inv)
        self.assertEqual(inv["customer_name"], "Ravi Kumar")
        self.assertEqual(inv["phone"], "+919876543210")
        self.assertEqual(inv["invoice_no"], "INV-2026-001")
        self.assertEqual(inv["amount"], 15000.0)
        self.assertTrue(inv["has_amount"])
        self.assertTrue(inv["has_invoice_no"])
        self.assertTrue(inv["has_due_date"])
        self.assertTrue(inv["has_customer_name"])

    def test_phone_only_row(self):
        row = {"phone": "9876543210"}
        inv, err = parse_invoice(row)
        self.assertEqual(err, "")
        self.assertIsNotNone(inv)
        self.assertEqual(inv["customer_name"], "Customer")
        self.assertEqual(inv["phone"], "+919876543210")
        self.assertEqual(inv["invoice_no"], "")
        self.assertIsNone(inv["amount"])
        self.assertIsNone(inv["due_date"])
        self.assertFalse(inv["has_amount"])
        self.assertFalse(inv["has_invoice_no"])
        self.assertFalse(inv["has_due_date"])

    def test_partial_row_phone_and_amount(self):
        row = {
            "phone": "9876543210",
            "amount": "25,000",
        }
        inv, err = parse_invoice(row)
        self.assertEqual(err, "")
        self.assertIsNotNone(inv)
        self.assertEqual(inv["amount"], 25000.0)
        self.assertTrue(inv["has_amount"])
        self.assertFalse(inv["has_invoice_no"])
        self.assertFalse(inv["has_due_date"])

    def test_invalid_phone_rejected(self):
        row = {"phone": "12345"}
        inv, err = parse_invoice(row)
        self.assertIsNone(inv)
        self.assertIn("not an Indian mobile number", err)

    def test_instructions_with_missing_fields(self):
        call = {
            "call_id": "call-123",
            "company": "Roxy Distributors",
            "customer_name": "Customer",
            "phone": "+919876543210",
            "invoice_no": "",
            "amount": 0.0,
            "due_date": None,
        }
        prompt = instructions(call, "te")
        self.assertIn("not specified in follow-up records", prompt)
        self.assertIn("Roxy Distributors", prompt)

    def test_camel_case_due_date(self):
        row = {
            "phone": "9876543210",
            "dueDate": "20-10-2026",
        }
        inv, err = parse_invoice(row)
        self.assertEqual(err, "")
        self.assertIsNotNone(inv)
        self.assertEqual(inv["due_date"], "2026-10-20")
        self.assertTrue(inv["has_due_date"])

    def test_instructions_with_due_date(self):
        call = {
            "call_id": "call-123",
            "company": "Roxy Distributors",
            "customer_name": "Ravi",
            "phone": "+919876543210",
            "invoice_no": "INV-100",
            "amount": 5000.0,
            "due_date": "2026-10-25",
        }
        prompt = instructions(call, "te")
        self.assertIn("25 October 2026", prompt)

    def test_max_import_rows_limit(self):
        from server import MAX_IMPORT_ROWS
        self.assertEqual(MAX_IMPORT_ROWS, 100)

if __name__ == "__main__":
    unittest.main()
