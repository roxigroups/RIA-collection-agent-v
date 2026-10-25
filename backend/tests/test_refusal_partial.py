import os
import unittest
from unittest.mock import MagicMock, AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://mock:mock@localhost:5432/mockdb")
from livekit.agents import llm
from ria.agent import CollectionAgent, refuses, REFUSAL_RE


class TestRefusalPartialPayment(unittest.IsolatedAsyncioTestCase):
    def test_refusal_regex(self):
        """Test that refuses() and REFUSAL_RE identify Telugu, Hindi, and English refusal phrases."""
        refusal_phrases = [
            "నేను కట్టను",
            "కట్టేది లేదు",
            "నేను కట్టలేను",
            "పైసలు చెల్లించను",
            "డబ్బులు ఇవ్వను",
            "I won't pay",
            "I will not pay",
            "I cannot pay",
            "नहीं दूँगा",
            "नहीं देंगे",
            "नहीं भरूँगा",
        ]
        for phrase in refusal_phrases:
            self.assertTrue(refuses(phrase), f"Expected '{phrase}' to be recognized as refusal")

        acceptance_phrases = [
            "సరే కడతాను",
            "I will pay tomorrow",
            "హా చేస్తాను",
            "हाँ दे दूँगा",
        ]
        for phrase in acceptance_phrases:
            self.assertFalse(refuses(phrase), f"Expected '{phrase}' not to be recognized as refusal")

    async def test_first_refusal_prompts_partial_and_second_refusal_saves(self):
        """First refusal triggers a 30% partial payment offer; second refusal saves PAYMENT_REFUSED."""
        call = {
            "call_id": "test-101",
            "customer_name": "Karna",
            "amount": "10000",
            "invoice_no": "INV-001",
            "company": "TestCo",
        }
        mock_lines = MagicMock()
        mock_stt = MagicMock()
        agent = CollectionAgent(call, "te", mock_lines, mock_stt)
        agent.verified = True
        agent.customer_texts = ["నేను కట్టను"]

        with patch("ria.agent.DB.save_collection_call") as mock_save:
            # First refusal: should NOT save, must prompt for 30% (₹3,000)
            res1 = await agent._finish("PAYMENT_REFUSED", "", 0, "Customer said won't pay")
            self.assertIsInstance(res1, llm.ToolResult)
            self.assertIn("Do not end the call yet", res1.output)
            self.assertIn("30%", res1.output)
            self.assertIn("3,000", res1.output)
            self.assertTrue(res1.reply_required)
            self.assertTrue(agent.refusal_offered_partial)
            self.assertFalse(agent.finished)
            mock_save.assert_not_called()

            # Customer refuses again
            agent.customer_texts.append("అది కూడా కట్టను")

            # Second refusal: must save and end call
            res2 = await agent._finish("PAYMENT_REFUSED", "", 0, "Second refusal")
            self.assertIsInstance(res2, llm.ToolResult)
            self.assertIn("Saved", res2.output)
            self.assertTrue(agent.finished)
            mock_save.assert_called_once()
            args, kwargs = mock_save.call_args
            self.assertEqual(kwargs.get("outcome"), "REFUSED")

    async def test_refusal_when_partial_already_offered_in_chat(self):
        """If 30% partial payment was already offered in conversation, first tool refusal saves immediately."""
        call = {
            "call_id": "test-102",
            "customer_name": "Karna",
            "amount": "20000",
            "invoice_no": "INV-002",
            "company": "TestCo",
        }
        mock_lines = MagicMock()
        mock_stt = MagicMock()
        agent = CollectionAgent(call, "te", mock_lines, mock_stt)
        agent.verified = True
        agent.customer_texts = ["కట్టలేను", "కట్టను"]

        # Add assistant message into chat context
        ctx = agent.chat_ctx.copy()
        ctx.add_message(role="assistant", content="అర్థమైందండీ, కనీసం 30% భాగం చెల్లించడం వీలవుతుందా?")
        await agent.update_chat_ctx(ctx)

        self.assertTrue(agent._already_offered_partial())

        with patch("ria.agent.DB.save_collection_call") as mock_save:
            res = await agent._finish("PAYMENT_REFUSED", "", 0, "Customer refused after 30% offer")
            self.assertIsInstance(res, llm.ToolResult)
            self.assertIn("Saved", res.output)
            self.assertTrue(agent.finished)
            mock_save.assert_called_once()

    async def test_refusal_without_amount(self):
        """If the call record has no amount, PAYMENT_REFUSED is saved immediately without proposing 30%."""
        call = {
            "call_id": "test-103",
            "customer_name": "Karna",
            "amount": 0,
            "invoice_no": "INV-003",
            "company": "TestCo",
        }
        mock_lines = MagicMock()
        mock_stt = MagicMock()
        agent = CollectionAgent(call, "te", mock_lines, mock_stt)
        agent.verified = True
        agent.customer_texts = ["కట్టను"]

        self.assertFalse(agent.has_amount)

        with patch("ria.agent.DB.save_collection_call") as mock_save:
            res = await agent._finish("PAYMENT_REFUSED", "", 0, "Customer won't pay")
            self.assertIsInstance(res, llm.ToolResult)
            self.assertIn("Saved", res.output)
            self.assertTrue(agent.finished)
            mock_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
