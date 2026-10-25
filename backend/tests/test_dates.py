"""Regression tests for ria/dates.py (the user's suite, written against ria_dates_production.py).

The production module imports RIA application helpers. Lightweight stubs are used here
so the date logic can be tested independently of the telephony application.
Run from backend/: python -m unittest -v tests/test_dates.py
"""
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))

# Import dialer or stub if running in isolation
try:
    import dialer
    if not hasattr(dialer, "IST"):
        dialer.IST = IST
except ImportError:
    dialer = types.ModuleType("dialer")
    dialer.IST = IST
    sys.modules["dialer"] = dialer
ria = types.ModuleType("ria")
ria.__path__ = [str(Path(__file__).resolve().parents[1] / "ria")]
script = types.ModuleType("ria.script")
script.base_language = lambda lines: "en"
script.fill = lambda template, values: template.format(**values)
script.pick = lambda value, language: value.get(language, value.get("en", value)) if isinstance(value, dict) else value
script.PROMPTS = types.SimpleNamespace(
    DUE_PHRASES={
        "te": {
            "overdue": "{days} రోజుల క్రితమే due అయింది", "overdue_one": "నిన్ననే due అయింది",
            "today": "ఈరోజే due date", "upcoming": "ఇంకా {days} రోజుల్లో due ఉంది",
        },
        "hi": {
            "overdue": "{days} दिन पहले due हो चुका है", "overdue_one": "कल ही due हुआ था",
            "today": "आज ही due date है", "upcoming": "अगले {days} दिनों में due है",
        },
        "en": {
            "overdue": "{days} days overdue", "overdue_one": "1 day overdue",
            "today": "due today", "upcoming": "due in {days} days",
        },
    },
    COLLECTION_INSTRUCTIONS="{company} {customer} {amount} {balance_due} {invoice_no} {due_date} {overdue}",
)
script.load = lambda: script.PROMPTS
ria.script = script
sys.modules.setdefault("ria", ria)
sys.modules.setdefault("ria.script", script)

MODULE_PATH = Path(__file__).resolve().parents[1] / "ria" / "dates.py"
spec = importlib.util.spec_from_file_location("ria_dates_fixed_under_test", MODULE_PATH)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class DateParsingTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 10, 11)  # Sunday; deterministic boundary date
        mod.today = lambda: self.today

    def assert_spoken_date(self, text, expected):
        result = mod.spoken_date(text)
        self.assertEqual(result[0] if result else None, expected, text)

    def test_relative_dates_and_durations(self):
        cases = {
            "today": date(2026, 10, 11),
            "tomorrow": date(2026, 10, 12),
            "day after tomorrow": date(2026, 10, 13),
            "in 4 days": date(2026, 10, 15),
            "in fourteen days": date(2026, 10, 25),
            "in 40 days": date(2026, 11, 20),
            "ఎల్లుండి": date(2026, 10, 13),
            "ఫోర్ డేస్": date(2026, 10, 15),
            "పద్నాలుగు రోజుల్లో": date(2026, 10, 25),
            "நாளை": date(2026, 10, 12),
            "நாளை மறுநாள்": date(2026, 10, 13),
            "பதினான்கு நாட்கள்": date(2026, 10, 25),
            "ನಾಳೆ": date(2026, 10, 12),
            "ನಾಡಿದ್ದು": date(2026, 10, 13),
            "ಹದಿನಾಲ್ಕು ದಿನಗಳು": date(2026, 10, 25),
            "चौदह दिन": date(2026, 10, 25),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assert_spoken_date(text, expected)

    def test_weekdays_and_last_correction_wins(self):
        self.assert_spoken_date("Friday", date(2026, 10, 16))
        self.assert_spoken_date("next Friday", date(2026, 10, 23))
        self.assert_spoken_date("not Friday, Monday", date(2026, 10, 12))
        self.assert_spoken_date("Friday but Monday", date(2026, 10, 12))
        self.assert_spoken_date("Friday or Monday", None)
        self.assert_spoken_date("Sunday", None)  # today is Sunday; don't guess today vs next week
        self.assert_spoken_date("today Sunday", date(2026, 10, 11))

    def test_month_end_and_explicit_dates(self):
        self.assert_spoken_date("end of month", date(2026, 10, 31))
        self.assert_spoken_date("October 31", date(2026, 10, 31))
        self.assert_spoken_date("2028-02-29", date(2028, 2, 29))
        self.assert_spoken_date("29 February 2028", date(2028, 2, 29))
        self.assert_spoken_date("February 29, 2028", date(2028, 2, 29))
        self.assert_spoken_date("29 February 2027", None)  # invalid leap day

    def test_non_dates_and_past_statements(self):
        self.assert_spoken_date("₹50", None)
        self.assert_spoken_date("I paid 4 days ago", None)
        self.assertFalse(mod.said_a_date(["Friday", "Okay"]))  # stale earlier turn ignored
        self.assertFalse(mod.said_a_date("15:00"))
        self.assertFalse(mod.said_a_date("₹50"))

    def test_callback_datetime(self):
        now = datetime(2026, 10, 11, 16, 0, tzinfo=IST)
        self.assertEqual(mod.callback_time("Friday at 5 PM", now=now), datetime(2026, 10, 16, 17, 0, tzinfo=IST))
        self.assertEqual(mod.callback_time("tomorrow at 4 PM", now=now), datetime(2026, 10, 12, 16, 0, tzinfo=IST))
        self.assertEqual(mod.callback_time("in 30 minutes", now=now), datetime(2026, 10, 11, 16, 30, tzinfo=IST))
        self.assertEqual(mod.callback_time("after one hour", now=now), datetime(2026, 10, 11, 17, 0, tzinfo=IST))
        self.assertIsNone(mod.callback_time("today at 4 PM", now=now))  # already passed
        self.assertIsNone(mod.callback_time("at 3 PM", now=now))  # don't silently roll to tomorrow
        self.assertIsNone(mod.callback_time("tomorrow evening", now=now))  # ask for exact time
        self.assertIsNone(mod.callback_time("later", now=now))

    def test_ptp_window_validation(self):
        call = {"due_date": "2026-10-01", "tenant_config": {"rules": {"ptpwindow_days": 7}}}
        self.assertEqual(mod.latest_promise_date(call), date(2026, 10, 18))
        self.assertEqual(mod.validate_promise_date(call, "2026-10-18"), date(2026, 10, 18))
        self.assertIsNone(mod.validate_promise_date(call, "2026-10-19"))
        self.assertIsNone(mod.validate_promise_date(call, "2026-10-10"))
        self.assertIsNone(mod.latest_promise_date({}))
        self.assertIsNone(mod.latest_promise_date({"due_date": "not-a-date"}))
        self.assertEqual(mod.extension_days({"tenant_config": {"rules": {"ptpwindow_days": 0}}}), 1)

    def test_ptp_save_adapter_guards_and_success(self):
        call = {"call_id": "call-123", "customer_id": "cust-9", "invoice_no": "INV-4",
                "due_date": "2026-10-01", "balance_due": "500.00",
                "tenant_config": {"rules": {"ptpwindow_days": 7}}}
        saved = []
        api = lambda payload: saved.append(payload) or {"success": True}
        common = dict(
            call=call,
            payment_date_expression="I will pay on October 15",
            confirmation_utterance="yes",
            readback_date="2026-10-15",
            readback_confirmed=True,
            explicit_payment_commitment=True,
            payment_amount="500.00",
            save_ptp_api=api,
            as_of=date(2026, 10, 11),
        )
        no_commitment = mod.save_validated_ptp(**{**common, "explicit_payment_commitment": False})
        self.assertFalse(no_commitment["ok"])
        self.assertEqual(saved, [])
        no_readback = mod.save_validated_ptp(**{**common, "readback_confirmed": False})
        self.assertFalse(no_readback["ok"])
        self.assertEqual(saved, [])
        vague_ack = mod.save_validated_ptp(**{**common, "confirmation_utterance": "okay"})
        self.assertFalse(vague_ack["ok"])
        self.assertEqual(saved, [])
        mismatch = mod.save_validated_ptp(**{**common, "readback_date": "2026-10-16"})
        self.assertFalse(mismatch["ok"])
        self.assertEqual(saved, [])
        good = mod.save_validated_ptp(**common)
        self.assertTrue(good["ok"], good)
        self.assertEqual(saved[0]["payment_date"], "2026-10-15")
        self.assertEqual(saved[0]["payment_amount"], "500.00")
        outside = mod.save_validated_ptp(**{**common, "payment_date_expression": "I will pay on October 25", "readback_date": "2026-10-25"})
        self.assertFalse(outside["ok"])
        self.assertEqual(len(saved), 1)
        too_much = mod.save_validated_ptp(**{**common, "payment_amount": "501.00"})
        self.assertFalse(too_much["ok"])
        bad_precision = mod.save_validated_ptp(**{**common, "payment_amount": "100.001"})
        self.assertFalse(bad_precision["ok"])
        refused = mod.save_validated_ptp(**{**common, "payment_date_expression": "I won't pay Friday"})
        self.assertFalse(refused["ok"])
        partial = mod.save_validated_ptp(**{**common, "payment_amount": "100.00"})
        self.assertFalse(partial["ok"])
        authorized_partial = mod.save_validated_ptp(**{**common, "payment_amount": "100.00", "allow_partial_payment": True})
        self.assertTrue(authorized_partial["ok"], authorized_partial)
        self.assertEqual(len(saved), 2)

    def test_callback_reschedule_adapter_uses_same_call_id(self):
        now = datetime(2026, 10, 11, 16, 0, tzinfo=IST)
        sent = []
        api = lambda payload: sent.append(payload) or {"success": True}
        result = mod.reschedule_existing_callback(
            call_id="call-123", latest_customer_utterance="Friday at 5 PM", reschedule_api=api, now=now)
        self.assertTrue(result["ok"], result)
        self.assertEqual(sent[0]["call_id"], "call-123")
        self.assertEqual(sent[0]["scheduled_at"], "2026-10-16T17:00:00+05:30")
        unclear = mod.reschedule_existing_callback(
            call_id="call-123", latest_customer_utterance="later", reschedule_api=api, now=now)
        self.assertFalse(unclear["ok"])
        self.assertEqual(len(sent), 1)
        too_far = mod.reschedule_existing_callback(
            call_id="call-123", latest_customer_utterance="December 1 at 5 PM", reschedule_api=api, now=now)
        self.assertFalse(too_far["ok"])
        self.assertEqual(len(sent), 1)
        failed = mod.reschedule_existing_callback(
            call_id="call-123", latest_customer_utterance="Friday at 5 PM", reschedule_api=lambda payload: {"success": False}, now=now)
        self.assertFalse(failed["ok"])


def tearDownModule():
    # Clean up mock ria namespace so other tests can import actual ria modules
    sys.modules.pop("ria.script", None)
    sys.modules.pop("ria", None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
