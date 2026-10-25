import os
import unittest
from datetime import date, timedelta

os.environ.setdefault("DATABASE_URL", "postgresql://mock:mock@localhost:5432/mockdb")
from ria import dates
from ria.agent import speakable


class TestDayPronunciation(unittest.TestCase):
    def test_format_day_count_telugu(self):
        """Test Telugu day count conversion across units, teens, tens, and compounds."""
        cases = {
            1: "ఒక",
            2: "రెండు",
            3: "మూడు",
            5: "ఐదు",
            7: "ఏడు",
            10: "పది",
            11: "పదకొండు",
            12: "పన్నెండు",
            15: "పదిహేను",
            20: "ఇరవై",
            25: "ఇరవై ఐదు",
            30: "ముప్పై",
            45: "నలభై ఐదు",
            60: "అరవై",
            90: "తొంబై",
            100: "వంద",
        }
        for num, expected in cases.items():
            self.assertEqual(dates.format_day_count(num, "te"), expected, f"Failed for {num}")

    def test_format_day_count_hindi(self):
        """Test Hindi day count conversion."""
        cases = {
            1: "एक",
            2: "दो",
            5: "पांच",
            11: "ग्यारह",
            15: "पंद्रह",
            20: "बीस",
            25: "पच्चीस",
            30: "तीस",
        }
        for num, expected in cases.items():
            self.assertEqual(dates.format_day_count(num, "hi"), expected, f"Failed for {num}")

    def test_format_day_count_english(self):
        """English day counts stay as standard digits."""
        self.assertEqual(dates.format_day_count(11, "en"), "11")
        self.assertEqual(dates.format_day_count(25, "en"), "25")

    def test_overdue_phrase_uses_words(self):
        """Verify overdue_phrase produces localized words for days."""
        today = dates.today()
        due_11_days_ago = today - timedelta(days=11)

        te_phrase = dates.overdue_phrase(due_11_days_ago, "te")
        self.assertIn("పదకొండు రోజుల", te_phrase)
        self.assertNotIn("11", te_phrase)

        hi_phrase = dates.overdue_phrase(due_11_days_ago, "hi")
        self.assertIn("ग्यारह दिन", hi_phrase)
        self.assertNotIn("11", hi_phrase)

        en_phrase = dates.overdue_phrase(due_11_days_ago, "en")
        self.assertIn("11 days overdue", en_phrase)

    def test_speakable_leaves_amounts_intact_and_converts_days(self):
        """Ensure currency amounts remain intact in English while day counts convert to Telugu/Hindi words."""
        # 1. Day count converted in Telugu
        text1 = "మీ due 11 రోజుల ముందే ముగిసింది"
        out1 = speakable(text1, "te")
        self.assertIn("పదకొండు రోజుల", out1)
        self.assertNotIn("11", out1)

        # 2. Amount and invoice left completely intact in English format
        text2 = "మీ invoice INV-104 లో ₹25,000 balance due ఉంది అండీ."
        out2 = speakable(text2, "te")
        self.assertIn("₹25,000", out2)
        self.assertIn("INV-104", out2)

        # 3. Sentence with BOTH amount and days
        text3 = "₹10,000 balance ఉంది, ఇది 15 రోజులు overdue అయింది."
        out3 = speakable(text3, "te")
        self.assertIn("₹10,000", out3)
        self.assertIn("పదిహేను రోజులు", out3)
        self.assertNotIn("15", out3)

        # 4. Hindi day count conversion
        text4 = "आपका payment 11 दिन पहले due हुआ था, balance ₹5,000 है।"
        out4 = speakable(text4, "hi")
        self.assertIn("ग्यारह दिन", out4)
        self.assertIn("₹5,000", out4)
        self.assertNotIn("11", out4)


if __name__ == "__main__":
    unittest.main()
