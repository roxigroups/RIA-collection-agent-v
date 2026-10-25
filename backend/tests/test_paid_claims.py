import os
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

import importlib
os.environ.setdefault("DATABASE_URL", "postgresql://mock:mock@localhost:5432/mockdb")
import ria.script as script
importlib.reload(script)

from ria.agent import CollectionAgent, PAID_CLAIM_RE, CONTRADICTS_RE
from ria.outcomes import OUTCOME_CODES
from ria import dates


class TestPaidClaimsAndPTP(unittest.IsolatedAsyncioTestCase):
    def test_paid_claim_regex_matches(self):
        """Test that PAID_CLAIM_RE detects past-tense payment claims across Telugu, Hindi, and English."""
        positives = [
            "నేను కట్టానండి.",
            "కట్టేశానండి",
            "కట్టేశాను",
            "కట్టేసానండి",
            "కట్టేసాను",
            "కట్టామండి",
            "కట్టాం",
            "చెల్లించానండి",
            "చెల్లించాను",
            "చెల్లించేశానండి",
            "పేమెంట్ అయిందండి",
            "పేమెంట్ అయిపోయింది",
            "పేమెంట్ చేశానండి",
            "పేమెంట్ చేసానండి",
            "పేమెంట్ చేసేశానండి",
            "డబ్బులు పంపించానండి",
            "యూపీఐ చేసేశాను",
            "google pay చేశానండి",
            "i already paid",
            "we have already paid",
            "payment is done",
            "पेमेंट कर दिया",
            "पैसे भेज दिए जी",
        ]
        for phrase in positives:
            self.assertTrue(bool(PAID_CLAIM_RE.search(phrase)), f"Expected '{phrase}' to match PAID_CLAIM_RE")
            self.assertTrue(bool(CONTRADICTS_RE.search(phrase)), f"Expected '{phrase}' to match CONTRADICTS_RE")

    def test_paid_claim_regex_rejects_future_or_questions(self):
        """Test that PAID_CLAIM_RE does NOT falsely match future promises, questions, or refusals."""
        negatives = [
            "ఎంత కట్టాలి?",
            "ఎప్పుడు కట్టాలి?",
            "నేను కట్టను",
            "కట్టలేను",
            "రేపు కడతాను",
            "కట్టేస్తాను",
            "కట్టేస్తా",
            "చెల్లించాలి",
            "చెల్లించేస్తాను",
        ]
        for phrase in negatives:
            self.assertFalse(bool(PAID_CLAIM_RE.search(phrase)), f"Expected '{phrase}' NOT to match PAID_CLAIM_RE")

    async def test_already_paid_saves_payment_made_interceptor(self):
        """When a verified customer says 'నేను కట్టానండి.', it should save PAYMENT_MADE without LLM hallucination."""
        call = {
            "call_id": "test-201",
            "customer_name": "Vikas",
            "amount": "2026",
            "invoice_no": "123456",
            "company": "roxygroups",
        }
        mock_lines = MagicMock()
        mock_stt = MagicMock()
        agent = CollectionAgent(call, "te", mock_lines, mock_stt)
        agent.verified = True
        agent.someone_else = False

        with patch.object(agent, "_save", new_callable=AsyncMock) as mock_save:
            res = await agent.take_turn("నేను కట్టానండి.")
            self.assertIsNone(res, "Expected interceptor to handle turn directly without prompting LLM")
            mock_save.assert_called_once()
            args = mock_save.call_args[0]
            self.assertEqual(args[0], "PAYMENT_MADE")
            self.assertIn("Customer says they already paid", args[3])

    def test_no_double_rupee_symbol(self):
        """Ensure formatting amount with format_inr in script templates does not produce ₹₹."""
        formatted_amount = dates.format_inr(2026)  # '₹2,026'
        fields = {
            "company": "roxygroups",
            "invoice_no": "123456",
            "amount": formatted_amount,
            "overdue": "పద్నాలుగు రోజుల క్రితమే due అయింది",
        }
        lines_dict = getattr(script.PROMPTS, "COLLECTION_AMOUNT_LINES", script.DEFAULT_LINES["COLLECTION_AMOUNT_LINES"])
        for template in lines_dict.values():
            rendered = script.fill(template, fields)
            self.assertNotIn("₹₹", rendered, f"Found double rupee symbol in: {rendered}")
            self.assertIn("₹2,026", rendered, f"Expected valid ₹2,026 in: {rendered}")

        no_inv_dict = getattr(script.PROMPTS, "COLLECTION_AMOUNT_NO_INV", script.DEFAULT_LINES["COLLECTION_AMOUNT_NO_INV"])
        for template in no_inv_dict.values():
            rendered = script.fill(template, fields)
            self.assertNotIn("₹₹", rendered, f"Found double rupee symbol in: {rendered}")
            self.assertIn("₹2,026", rendered, f"Expected valid ₹2,026 in: {rendered}")

    def test_partial_payment_is_ptp(self):
        """Verify that PARTIAL_PAYMENT_PROMISE outcome maps to PROMISE-TO-PAY."""
        outcome_tuple = OUTCOME_CODES.get("PARTIAL_PAYMENT_PROMISE")
        self.assertIsNotNone(outcome_tuple)
        dashboard_outcome, ticket, label = outcome_tuple
        self.assertEqual(dashboard_outcome, "PROMISE-TO-PAY")
        self.assertEqual(label, "Part payment")
