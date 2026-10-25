import os
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

import importlib
os.environ.setdefault("DATABASE_URL", "postgresql://mock:mock@localhost:5432/mockdb")
import ria.script as script
importlib.reload(script)

from ria.agent import CollectionAgent, PAID_CLAIM_RE, CONTRADICTS_RE, EXPLICIT_PAID_RE
from ria.outcomes import OUTCOME_CODES
from ria.voice import STT_KEYWORDS
from ria import dates


class TestPaidClaimsAndPTP(unittest.IsolatedAsyncioTestCase):
    def test_stt_keywords_contain_negations(self):
        """Fix 2: Ensure STT_KEYWORDS contains negative and refusal keywords to steer recognition."""
        expected_negatives = ["కట్టను", "కట్టనండి", "కట్టేది లేదు", "కట్టలేను", "కాదు", "లేదు", "नहीं दूँगा", "won't pay"]
        for word in expected_negatives:
            self.assertIn(word, STT_KEYWORDS, f"Expected '{word}' to be present in STT_KEYWORDS")

    def test_explicit_paid_regex(self):
        """Fix 3: Test that EXPLICIT_PAID_RE identifies claims with methods/dates, and separates bare ambiguous verbs."""
        explicit_samples = [
            "నేను PhonePe చేసానండి",
            "Google Pay చేశానండి",
            "యూపీఐ చేసేశాను",
            "డబ్బులు పంపించానండి",
            "నిన్ననే కట్టాను",
            "మొన్ననే కట్టేశాను",
            "కట్టేశానండి",
            "కట్టేసానండి",
            "Already paid",
            "payment is done",
            "पेमेंट कर दिया जी",
        ]
        for phrase in explicit_samples:
            self.assertTrue(bool(EXPLICIT_PAID_RE.search(phrase)), f"Expected '{phrase}' to match EXPLICIT_PAID_RE")

        ambiguous_samples = [
            "నేను కట్టానండి.",
            "కట్టాను",
            "కట్టామండి",
            "కట్టాం",
            "చెల్లించాను",
        ]
        for phrase in ambiguous_samples:
            self.assertFalse(bool(EXPLICIT_PAID_RE.search(phrase)), f"Expected '{phrase}' NOT to match EXPLICIT_PAID_RE")
            self.assertTrue(bool(PAID_CLAIM_RE.search(phrase)), f"Expected '{phrase}' to match general PAID_CLAIM_RE")

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

    async def test_explicit_paid_saves_immediately(self):
        """Fix 3: An explicit payment claim (e.g. PhonePe) saves PAYMENT_MADE immediately without extra question."""
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
            res = await agent.take_turn("నేను PhonePe చేసానండి.")
            self.assertIsNone(res)
            mock_save.assert_called_once()
            self.assertEqual(mock_save.call_args[0][0], "PAYMENT_MADE")

    async def test_ambiguous_paid_confirms_first_then_saves(self):
        """Fix 3: Ambiguous claim ('నేను కట్టానండి.') triggers confirmation question, then saves on 'అవునండి'."""
        call = {
            "call_id": "test-202",
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
            # Turn 1: Ambiguous claim -> Ria should ask confirmation line, NOT save yet
            res1 = await agent.take_turn("నేను కట్టానండి.")
            self.assertIsNone(res1)
            mock_save.assert_not_called()
            self.assertTrue(agent.paid_confirmation_asked)

            # Turn 2: Customer confirms ("అవునండి") -> Saves PAYMENT_MADE
            res2 = await agent.take_turn("అవునండి.")
            self.assertIsNone(res2)
            mock_save.assert_called_once()
            self.assertEqual(mock_save.call_args[0][0], "PAYMENT_MADE")

    async def test_ambiguous_paid_refusal_clarification_prompts_partial_30(self):
        """Fix 3: Ambiguous claim followed by refusal clarification triggers 30% partial payment offer."""
        call = {
            "call_id": "test-203",
            "customer_name": "Vikas",
            "amount": "10000",
            "invoice_no": "123456",
            "company": "roxygroups",
        }
        mock_lines = MagicMock()
        mock_stt = MagicMock()
        agent = CollectionAgent(call, "te", mock_lines, mock_stt)
        agent.verified = True
        agent.someone_else = False

        with patch.object(agent, "_save", new_callable=AsyncMock) as mock_save:
            # Turn 1: Ambiguous claim
            await agent.take_turn("నేను కట్టానండి.")
            self.assertTrue(agent.paid_confirmation_asked)

            # Turn 2: Customer clarifies refusal ("లేదండి, కట్టను అంటున్నాను")
            res = await agent.take_turn("లేదండి, కట్టను అంటున్నాను.")
            mock_save.assert_not_called()
            self.assertIsNotNone(res)
            self.assertIn("30%", res)
            self.assertIn("refuse to pay", res)

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

    def test_is_plain_yes_avoids_false_verification(self):
        """Ensure sentences containing the name but meaning someone else (e.g. 'నేను వికాస్ మీరా.') do not verify."""
        from ria.agent import is_plain_yes
        self.assertTrue(is_plain_yes("వికాస్", "vikas"))
        self.assertTrue(is_plain_yes("వికాస్ అండీ", "vikas"))
        self.assertTrue(is_plain_yes("నేనే వికాస్", "vikas"))
        self.assertTrue(is_plain_yes("వికాస్ మాట్లాడుతున్నాను", "vikas"))

        # Phrases with name that are NOT confirmation:
        self.assertFalse(is_plain_yes("నేను వికాస్ మీరా.", "vikas"))
        self.assertFalse(is_plain_yes("వికాస్ బయటికి వెళ్ళాడు", "vikas"))
        self.assertFalse(is_plain_yes("వికాస్ కాదు", "vikas"))
        self.assertFalse(is_plain_yes("వికాస్ లేడు", "vikas"))
