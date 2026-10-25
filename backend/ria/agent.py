"""The conversation: what RIA knows about the call, her tools, and the checks
before anything is saved.

The model decides what to say and which tool to call; the tools do the parts
that must be exact, with words written in prompts.py and data from the call sheet:
    verify_customer     the right person is on the line (only then the invoice is told)
    switch_language     the customer wants or speaks another language
    check_payment_date  reads a payment date back, or says the latest date allowed
    finish_call         saves the outcome; the app says goodbye and hangs up
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import time
from collections import deque
from collections.abc import AsyncIterable
from datetime import date, timedelta
from typing import Annotated, Literal

from livekit import rtc
from livekit.agents import Agent, ModelSettings, RunContext, StopResponse, llm, stt

from db_driver import DatabaseDriver
from ria import dates, script, voice
from ria.languages import NAMES, requested_language, says_name
from ria.outcomes import OUTCOME_CODES, SAVE_UNVERIFIED, OutcomeCode, notes_for
from ria.script import fill, pick

logger = logging.getLogger("ria-agent")
DB = DatabaseDriver()

# A clear "yes" to "am I speaking with Ravi garu?": the app tells the balance at once,
# without waiting for the model. Anything else (questions, "busy", "no") goes to it
YES_WORDS = {
    "హా", "ఆ", "ఆఁ", "అవును", "జీ", "సరే", "ఓకే", "నేనే",
    "हाँ", "हां", "हा", "जी", "हाँजी", "yes", "yeah", "yep", "speaking", "haan", "han", "ji", "ok", "okay",
}
YES_STEMS = ("అవున", "ఆవున", "ఔన", "ఆనండ", "ఆఉండ", "అవుండ", "చెప్ప", "చెపండ", "మాట్లాడుతున్న", "సరేనండ", "బోలియే", "बोलिए", "बोलो", "बोल रह", "मैं ही",
             "tell me")
NOT_YES = (
    "కాదు", "కాద", "వేరే", "రాంగ్", "ఎవరు", "ఏంటి", "ఎందుకు", "బిజీ", "తర్వాత", "లేదు",
    "नहीं", "नही", "गलत", "कौन", "क्या", "क्यों", "बाद में", "व्यस्त", "बिज़ी", "बिजी",
    "no", "not", "wrong", "who", "what", "why", "busy", "later", "?",
)
# Agreeing ("సరేండి. అప్పటికి కడతాను.") or saying no to a date RIA read back
AGREES_RE = re.compile(
    r"సరే|ఓకే|ఒకే|అవున|ఆవున|ఔన|ఆనండ|ఆఉండ|అవుండ|అప్పటికి|అప్పటిలోగా|ఆ లోపు|కడతా|కట్టేస్తా|చేస్తా|కరెక్ట్"
    r"|ठीक|हाँ|हां|हांजी|सही|कर दूँगा|कर दूंगा|कर दूँगी|कर दूंगी|तब तक"
    r"|\b(?:ok|okay|yes|yeah|sure|fine|done|correct|right|will pay|by then)\b",
    re.I,
)
REFUSAL_RE = re.compile(
    r"కుదర|లేదు|లేదండ|కాదు|అవ్వదు|చేయలేను|కట్టలేను|కట్టను|చెల్లించను|ఇవ్వను|ఇయ్యను"
    r"|नहीं|नही|मुश्किल|नहीं दूँ|नहीं दूंग|नहीं भरूँ|नहीं भरूंग|नहीं देंगे"
    r"|can'?t|cannot|not possible|won'?t pay|will not pay|\bno\b", re.I
)
# "No problem" says yes, though it has a "no" in it ("పర్లేదు" ends in "లేదు")
NO_PROBLEM_RE = re.compile(
    r"పర్లేదు|పర్వాలేదు|ఫర్వాలేదు|ఏం పర్లేదు|no problem|no issues?|कोई बात नहीं|कोई दिक्कत नहीं|कोई प्रॉब्लम नहीं", re.I
)
# "I already paid" in the customer's words: RIA says the team will cross-check it and ends
# the call (the user's rule; asking for the amount and reference lost the claim when the
# customer hung up). Past tense only: "కట్టేస్తా" (I'll pay) is a promise, not this
_PAID_WITH = r"(?:పే|పేమెంట్|payment|అమౌంట్|amount|డబ్బులు|UPI|యూపీఐ|ట్రాన్స్ఫర్|transfer|ఫోన్ ?పే|phone ?pe|గూగుల్ ?పే|google ?pay|g ?pay)"
PAID_CLAIM_RE = re.compile(
    r"already paid|paid already|\b(?:i|we) (?:have |had )?(?:already )?paid\b|payment (?:is |was )?(?:made|done|completed)"
    r"|\b(?:i|we) (?:have )?(?:made|done|sent|transferred) (?:the )?payment"
    r"|చెల్లించా(?!లి)|చెల్లించే[శస]ా|కట్టా[ననుంమ]|కట్టే[శస]ా|పేమెంట్\s*అయి"
    r"|" + _PAID_WITH + r"\s*(?:\S+\s*){0,2}?(?:చే[శస]ే[శస]ా|చే[శస]ా[ననుంమ]|చే[శస]ా|పంప|వే[శస]ా|అయి)"
    r"|(?:पेमेंट|भुगतान|पैसे|payment)\s*(?:\S+\s*){0,2}?(?:कर दिया|कर दी|कर चुका|कर चुकी|हो गया|हो गई|भेज दिया"
    r"|भेज दिए|दे दिया|दे दिए|डाल दिया)",
    re.I,
)
# Unambiguous payment claims: mentions method, date, or completion particle.
# When a claim is NOT explicit (just a bare "కట్టానండి" or "కట్టాను" without method/date),
# RIA confirms once ("మీరు payment ఇప్పటికే చేశారా అండీ?") to avoid mishearing refusal ("కట్టనండి").
EXPLICIT_PAID_RE = re.compile(
    r"already paid|paid already|\b(?:i|we) (?:have |had )?(?:already )?paid\b|payment (?:is |was )?(?:made|done|completed)"
    r"|\b(?:i|we) (?:have )?(?:made|done|sent|transferred) (?:the )?payment"
    r"|చెల్లించే[శస]ా|కట్టే[శస]ా|పేమెంట్\s*అయి|ఆల్రెడీ|నిన్న|మొన్న"
    r"|" + _PAID_WITH + r"\s*(?:\S+\s*){0,2}?(?:చే[శస]ే[శస]ా|చే[శస]ా[ననుంమ]|చే[శస]ా|పంప|వే[శస]ా|అయి)"
    r"|(?:पेमेंट|भुगतान|पैसे|payment)\s*(?:\S+\s*){0,2}?(?:कर दिया|कर दी|कर चुका|कर चुकी|हो गया|हो गई|भेज दिया"
    r"|भेज दिए|दे दिया|दे दिए|डाल दिया)",
    re.I,
)
# Answers to a date read-back that say something else than yes, from the review patch:
# "I already paid", "call me" or "I'm busy" contradict it, so nothing is saved
CONTRADICTS_RE = re.compile(
    r"already paid|paid already|payment (?:is )?(?:made|done)|\b(?:i|we) (?:have )?paid\b|\b(?:call|callback|busy)\b"
    r"|చెల్లించా(?!లి)|చెల్లించే[శస]ా|కట్టా[ననుంమ]|కట్టే[శస]ా|పేమెంట్\s*అయి|ఆల్రెడీ|కాల్ చేయ|బిజీ"
    r"|" + _PAID_WITH + r"\s*(?:\S+\s*){0,2}?(?:చే[శస]ే[శస]ా|చే[శస]ా[ననుంమ]|చే[శస]ా|పంప|వే[శస]ా|అయి)"
    r"|(?:पेमेंट|भुगतान|पैसे|payment)\s*(?:\S+\s*){0,2}?(?:कर दिया|कर दी|कर चुका|कर चुकी|हो गया|हो गई|भेज दिया"
    r"|भेज दिए|दे दिया|दे दिए|डाल दिया)"
    r"|पहले ही|कॉल करो|कॉल करना|व्यस्त|बिज़ी|बिजी",
    re.I,
)
# ...and "the invoice is wrong", "later" or a question: not a quick yes, so the model
# hears it (it may still be a yes, which the model then saves)
DOUBT_RE = re.compile(
    r"invoice|delivery|dispute|\blater\b|తర్వాత|ఇన్వాయిస్|డెలివరీ|बाद में|इनवॉइस|डिलीवरी"
    r"|^\W*(?:why|what|who|how|when|where)\b|\b(?:why|what|who|how|when|where)\W*$"
    r"|ఎందుకు|ఏంటి|ఎవరు|क्यों|कौन",
    re.I,
)


def refuses(text: str) -> bool:
    """A no ("కుదరదు", "नहीं", "no"), not counting "no problem"."""
    return bool(REFUSAL_RE.search(NO_PROBLEM_RE.sub(" ", text)))


# Saying who they are: "నేనే", "నేనే చూసుకుంటాను" (I handle it), "accountant speaking"
IDENTITY_RE = re.compile(
    r"నేనే|నేను చూసుకుంటా|చూసుకుంటున్నా|హ్యాండిల్|అకౌంటెంట్|ఎకౌంటెంట్|మాట్లాడుతున్నా(?:ను|ం)?(?![\u0C00-\u0C7F])"
    r"|मैं ही|मैं देख|मैं बोल|बोल रहा हूँ|बोल रहा हूं|बोल रही हूँ|बोल रही हूं|अकाउंटेंट|हैंडल|देखता हूँ|देखता हूं|देखती हूँ|देखती हूं"
    r"|\b(?:speaking|it'?s me|this is (?:he|she|me)|accountant|i handle|in charge)\b",
    re.I,
)
# "Who is speaking?" says nothing about who they are
WHO_QUESTION_RE = re.compile(r"\bwho\b|ఎవరు|ఎవరండి|యవరండి|कौन", re.I)
# Not the customer, or not now: "కాదు", "ఆయన లేరు", "wrong number", "call later" go to the model
NOT_THEM_RE = re.compile(
    r"కాదు|కాద|వేరే|రాంగ్|లేరు|లేడు|లేదు|బయట|బిజీ|తర్వాత|కాల్ చేయ|ఫోన్ చేయ"
    r"|नहीं|नही|गलत|बाहर|व्यस्त|बिज़ी|बिजी|बाद में|कॉल कर"
    r"|\b(?:no|not|wrong|busy|later|out)\b",
    re.I,
)
# RIA asking whether they handle the payments, in the app's line or the model's own words
PAYMENTS_ASKED_RE = re.compile(r"చూసుకుంట|చూస్తారా|హ్యాండిల్|handle|look after|देखते|देखती|संभाल", re.I)
# The customer asking to be called back ("ఐదు గంటలకు కాల్ చేయండి"): a callback time,
# which the model once read back as a payment date and saved as a promise
CALLBACK_REQUEST_RE = re.compile(
    r"కాల్ చేయ|కాల్ చెయ్|ఫోన్ చేయ|call చేయ|call చెయ్|కాల్ బ్యాక్|మళ్ళీ కాల్|మళ్లీ కాల్"
    r"|कॉल कर|फोन कर|फ़ोन कर|call कर|बाद में कॉल|\bcall (?:me|back|later)|\bcallback|ring me",
    re.I,
)
# A transcript that is only a speaker label ("కస్టమర్:") is the transcriber making
# text out of line noise, never something the customer said
LABEL_ONLY_RE = re.compile(
    r"^\W*(?:కస్టమర్|కాలర్|customer|caller|speaker|agent|ग्राहक|कस्टमर)\s*\d*\s*[:：]\W*$", re.I
)
# Asking not to be called again, in so many words: a bare "వద్దు" (no) is not it
DO_NOT_CALL_RE = re.compile(
    r"(?:కాల్|ఫోన్|call)\S*\s*(?:చేయకండి|చెయ్యకండి|చేయొద్దు|చెయ్యొద్దు|చేయవద్దు|వద్దు|cheyakandi|cheyyakandi|vaddu)"
    r"|(?:कॉल|फोन|फ़ोन|call)\s*(?:मत|ना|न)\b|(?:कॉल|फोन|फ़ोन|call)\s*(?:मत|ना|न)\s*कर|call\s*mat"
    r"|don'?t\s+(?:call|ring|phone)|do\s+not\s+(?:call|ring|phone)|stop\s+calling|no\s+more\s+calls|never\s+call"
    # "Please don't trouble me" (the demo script's upset retailer), offered the opt-out
    r"|ఇబ్బంది\s*పెట్టకండి|ఇబ్బంది\s*పెట్టొద్దు|డిస్టర్బ్\s*చేయకండి|disturb\s*చేయకండి"
    r"|परेशान\s*मत|तंग\s*मत|pareshan\s*mat|don'?t\s+(?:trouble|disturb|bother)\s+me",
    re.I,
)
# Upset about the calls: "ఎన్ని సార్లు కాల్ చేస్తారు?", "ఇబ్బంది పెట్టకండి"
UPSET_RE = re.compile(
    r"ఎన్ని\s*సార్లు|ఇబ్బంది\s*పెట్ట|విసిగి|డిస్టర్బ్|कितनी\s*बार|परेशान|तंग|डिस्टर्ब"
    r"|\b(?:kitni\s*baar|pareshan|how\s+many\s+times|stop\s+(?:calling|troubling)|don'?t\s+(?:trouble|disturb|bother))",
    re.I,
)
# Paying in parts: "సగం ఇప్పుడు, మిగతాది వచ్చే వారం" (half now, the rest next week)
REST_RE = re.compile(r"మిగతా|మిగిలిన|మిగిలింది|బ్యాలెన్స్|बाकी|बचा हुआ|\b(?:balance|rest|remaining|baaki|baki)\b", re.I)
NOW_RE = re.compile(r"ఇప్పుడ|ఈరోజు|ఇవాళ|ఈవాళ|अभी|आज|\b(?:now|today|abhi|aaj)\b", re.I)
# Asking for the ledger, a statement or an invoice copy (kept as a ticket even when they promise)
STATEMENT_RE = re.compile(r"స్టేట్\S*మెంట్|లెడ్జర్|స్టేట్మెంట్|स्टेटमेंट|लेजर|लेज़र|\b(?:statement|ledger)\b|invoice\s*copy|ఇన్వాయిస్\s*కాపీ",
                          re.I)
# Only "hello?": the customer checking that someone is there
HELLO_ONLY_RE = re.compile(r"^\W*(?:హలో|హలో అండీ|hello|hallo|helo|हेलो|हैलो|हलो)\W*$", re.I)
# A voicemail or network message instead of a person
VOICEMAIL_RE = re.compile(
    r"person you are (?:trying to reach|calling)|leave (?:a|an|your)(?: additional)? message|after the (?:tone|beep)"
    r"|voice ?mail|(?:this|the) person is not available|reply after the|record your message|you may hang up"
    r"|is (?:currently )?switched off|not reachable|is busy on another call"
    r"|మెసేజ్ పెట్టుకో|సందేశాన్ని|స్విచ్ ఆఫ్|అందుబాటులో లేరు|రీచ్ కావడం లేదు"
    r"|संदेश छोड़|स्विच ऑफ|पहुंच से बाहर|नॉट रीचेबल|उपलब्ध नहीं है",
    re.I,
)
# Text the model must never speak: other alphabets (a Chinese word once slipped
# into a Telugu reply), a tool call written out as text, notes in brackets
UNSPEAKABLE_RE = re.compile(r"[^\x00-ɏऀ-෿​-‍‐-⁯₹\s]")
LEAKED_CODE_RE = re.compile(r"functions?\.|finish_call|check_payment_date|verify_customer|switch_language|```|\{\s*\"",
                            re.I)
BRACKET_NOTE_RE = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
OPEN_BRACKET_RE = re.compile(r"[(\[][^)\]]*$")


def speakable(text: str, language: str = "") -> str:
    """The model's reply as it may be spoken (and recorded)."""
    text = UNSPEAKABLE_RE.sub("", text)
    if (code := LEAKED_CODE_RE.search(text)):
        text = text[: code.start()]
    text = OPEN_BRACKET_RE.sub("", BRACKET_NOTE_RE.sub("", text))
    # Replace all-caps RIA with mixed-case Ria so TTS pronounces it as a name rather than letters R-I-A
    text = re.sub(r"\bRIA\b", "Ria", text)
    # Convert standalone day counts before day words into customer's native words
    if language in ("te", ""):
        text = re.sub(
            r"(?<![\d₹$.,])(\d{1,3})\s*(రోజులు|రోజుల|రోజుల్లో|రోజు)\b",
            lambda m: f"{dates.format_day_count(int(m.group(1)), 'te')} {m.group(2)}",
            text,
        )
    if language in ("hi", ""):
        text = re.sub(
            r"(?<![\d₹$.,])(\d{1,3})\s*(दिनों|दिन)\b",
            lambda m: f"{dates.format_day_count(int(m.group(1)), 'hi')} {m.group(2)}",
            text,
        )
    return text


def is_plain_yes(text: str, customer_name: str) -> bool:
    lowered = text.lower().strip()
    words = re.sub(r"[,.!।\-–—\"']", " ", lowered).split()
    if not words or len(words) > 6 or any(w in lowered for w in NOT_YES if not w.isascii()):
        return False
    if any(w in words for w in NOT_YES if w.isascii()):
        return False
    if "?" not in text and says_name(text, customer_name):  # "వసీమా?" asks, it doesn't answer
        # Only treat as plain yes if it is just their name ("వికాస్"), name with polite particle ("వికాస్ అండీ"), or explicit self-identification
        if (len(words) == 1 or
            (len(words) == 2 and any(w in ("అండీ", "గారు", "సర్", "మేడం", "जी", "sir", "madam") for w in words)) or
            "నేనే" in lowered or "మాట్లాడుతున్న" in lowered or "बोल रहा" in lowered):
            return True
        return False
    return any(w in YES_WORDS for w in words) or any(
        (stem in lowered) if " " in stem else any(w.startswith(stem) for w in words) for stem in YES_STEMS
    )


def instructions(call: dict, language: str) -> str:
    """prompts.COLLECTION_INSTRUCTIONS with this call's sheet data and calendar."""
    today = dates.today()

    # Data availability checks
    has_amount = bool(call.get("amount") is not None and float(call["amount"]) > 0)
    has_invoice = bool(call.get("invoice_no") and str(call["invoice_no"]).strip())
    has_due = bool(call.get("due_date"))
    customer_raw = (call.get("customer_name") or "").strip()
    has_customer = bool(customer_raw and customer_raw.lower() not in ("customer", "unknown", "sir", "madam"))

    due = None
    if has_due:
        try:
            due_val = call["due_date"]
            due = date.fromisoformat(due_val) if isinstance(due_val, str) else due_val
        except Exception:
            due = None

    if due:
        overdue = dates.overdue_phrase(due, language)
        due_date_str = f"{due:%d %B %Y}"
    else:
        overdue = "not specified in follow-up records"
        due_date_str = "not specified in follow-up records"

    business = call.get("business") or ""
    previous = call.get("previous_promised_date")
    broken = False
    if previous:
        try:
            prev_dt = date.fromisoformat(previous) if isinstance(previous, str) else previous
            broken = prev_dt < today
        except Exception:
            broken = False

    # Project tracks payment due date only; invoice billing date is not collected or invented
    inv_date_str = "not specified in follow-up records"

    latest = dates.latest_promise_date(call) or (today + timedelta(days=dates.extension_days(call)))
    latest_date_str = f"{latest:%A, %d %B %Y}"
    cal_days = max(45, min(370, (latest - today).days + 7))

    amount_str = dates.format_inr(float(call["amount"])) if has_amount else "not specified in follow-up records"
    invoice_no_str = call["invoice_no"] if has_invoice else "not specified in follow-up records"
    customer_str = customer_raw if has_customer else "the customer"

    return fill(script.PROMPTS.COLLECTION_INSTRUCTIONS, dict(
        company=call.get("company", ""),
        customer=customer_str,
        customer_id=call.get("customer_code") or call.get("retailer_id") or "unknown",
        business=f" ({business})" if business and business != customer_raw else "",
        business_name=business or "their business",
        invoice_no=invoice_no_str,
        invoice_date=inv_date_str,
        amount=amount_str,
        balance_due=amount_str,
        invoice_amount=amount_str,
        due_date=due_date_str,
        overdue=overdue,
        latest_date=latest_date_str,
        extension_days=dates.extension_days(call),
        previous_promised_date=f"{date.fromisoformat(previous):%d %B %Y}" if broken else "none (don't mention one)",
        today=f"{today:%A, %d %B %Y}",
        calendar=dates.calendar(today, days=cal_days),
        language=NAMES[language],
    ))


class CollectionAgent(Agent):
    """One invoice call. `lines` speaks fixed lines; `stt` is the transcriber, whose
    language follows the conversation's."""

    def __init__(self, call: dict, language: str, lines, stt) -> None:
        super().__init__(instructions=instructions(call, language))
        self._call = call
        self.language = language
        self.lines = lines
        self.stt_engine = stt
        self.has_amount = bool(call.get("amount") is not None and float(call["amount"]) > 0)
        self.has_invoice = bool(call.get("invoice_no") and str(call["invoice_no"]).strip())
        self.has_due = bool(call.get("due_date"))
        self.latest_date = dates.latest_promise_date(call) or (dates.today() + timedelta(days=dates.extension_days(call)))
        self.verified = False       # the right person is on the line
        self.amount_told = False
        self.finished = False
        self.customer_texts: list[str] = []
        # What they said once a callback came up: the callback day and time come only
        # from these, never from an invoice number or an earlier payment date
        self.callback_texts: list[str] = []
        # Dates read back to the customer -> how many customer messages there were
        # then (their answer is the next one). A promise is saved only for one of them
        self.read_backs: dict[date, int] = {}
        # Days the app heard the customer name -> customer messages then
        self.named_days: dict[date, int] = {}
        # Customer messages when the app told them the latest date accounts allow
        self.limit_offered_at: int | None = None
        # Rupees for a part payment being read back (0: the full balance)
        self.part_amount = 0.0
        # When the rest is paid, in the customer's words, for the notes (" Balance: “next week”.")
        self.balance_note = ""
        # The day the customer asked for when it was after the latest allowed one
        self.late_date: date | None = None
        # Times they said no to the latest allowed date: the first gets one more try
        self.limit_refusals = 0
        # Times the app asked who they are, before they said
        self.who_asks = 0
        # Unclear answers to a who question they heard in full (greeting or who line)
        self.unclear_after_heard = 0
        # Someone other than the customer answered (verify_customer said so)
        self.someone_else = False
        # The app asked them whether they handle the customer's payments
        self.payments_asked = False
        # A vague or past callback time was asked about once already
        self.callback_time_asked = False
        # Customer messages when the app asked what time to call (their answer is the next one)
        self.time_asked_at: int | None = None
        # A part payment under the minimum (30% of the balance) was questioned once already
        self.part_minimum_asked = False
        # Proposed 30% partial payment after customer payment refusal (offered once)
        self.refusal_offered_partial = False
        # Whether Ria asked to confirm an ambiguous payment claim (e.g. "కట్టానండి")
        self.paid_confirmation_asked = False
        # Set by the call: RIA's last line was cut off by the customer talking
        self.last_line_interrupted = False
        # Set by the call: say the goodbye for an outcome and hang up; voicemail
        self.on_finished = lambda code: None
        self.on_voicemail = lambda text: None
        # Every customer turn, also those the app answers itself (the log and the transcript)
        self.on_heard = lambda text: None
        # The customer's last ~20 s of audio, for the backup transcript (see call.py)
        self.recent_audio: deque[tuple[float, rtc.AudioFrame]] = deque()
        # RIA_DEBUG_AUDIO=1: the whole call's audio as the transcriber got it, saved at the end
        self.debug_audio: list[rtc.AudioFrame] | None = [] if os.getenv("RIA_DEBUG_AUDIO") == "1" else None

    @property
    def call_id(self) -> str:
        return self._call["call_id"]

    # -- speaking ------------------------------------------------------------------

    def say_line(self, *lines: dict, interruptible: bool = True, cache: bool = True):
        """Fixed lines from prompts.py in the conversation language, said as one."""
        try:
            session = self.session
        except RuntimeError:
            session = None
        if session is None:
            return None
        return asyncio.create_task(self.lines.say(session, self.line_text(*lines), interruptible, cache))

    def line_text(self, *lines: dict) -> str:
        return " ".join(pick(each, self.language) for each in lines)

    def tell_amount(self) -> None:
        self.verified = True
        if self.amount_told:
            return
        self.amount_told = True
        if self.has_due:
            try:
                due_val = self._call["due_date"]
                due_dt = date.fromisoformat(due_val) if isinstance(due_val, str) else due_val
                self.lines.fields["overdue"] = dates.overdue_phrase(due_dt, self.language)
            except Exception:
                self.lines.fields["overdue"] = ""
        else:
            self.lines.fields["overdue"] = ""

        logger.info("Call %s: customer verified; announcing follow-up", self.call_id)

        # Adaptive spoken line matching available data
        if self.has_invoice and self.has_amount:
            chosen = script.PROMPTS.COLLECTION_AMOUNT_LINES
        elif self.has_amount:
            chosen = getattr(script.PROMPTS, "COLLECTION_AMOUNT_NO_INV", script.PROMPTS.COLLECTION_AMOUNT_LINES)
        elif self.has_invoice:
            chosen = getattr(script.PROMPTS, "COLLECTION_INV_NO_AMOUNT", script.PROMPTS.COLLECTION_AMOUNT_LINES)
        else:
            chosen = getattr(script.PROMPTS, "COLLECTION_GENERIC_FOLLOWUP", script.PROMPTS.COLLECTION_AMOUNT_LINES)

        self.say_line(chosen)
        asyncio.create_task(self._remember_verified())

    async def _remember_verified(self) -> None:
        # In the conversation, not only the instructions: the model asked "are you Ravi
        # Kumar garu?" again after he had said yes
        chat_ctx = self.chat_ctx.copy()
        chat_ctx.add_message(role="system", content=f"(Internal) Verified: you are speaking with "
                             f"{self._call['customer_name']}. Never ask who they are again.")
        await self.update_chat_ctx(chat_ctx)

    async def switch_to(self, language: str) -> None:
        if language == self.language or language not in NAMES:
            return
        logger.info("Call %s: language %s -> %s", self.call_id, self.language, language)
        self.language = language
        # Exact transcripts in the new language from the next words on
        self.stt_engine.update_options(language=voice.stt_languages(language))
        await self.update_instructions(instructions(self._call, language))

    async def stt_node(self, audio: AsyncIterable[rtc.AudioFrame], model_settings: ModelSettings):
        async def keep(frames: AsyncIterable[rtc.AudioFrame]):
            async for frame in frames:
                now = time.monotonic()
                if self.debug_audio is not None:
                    self.debug_audio.append(frame)
                self.recent_audio.append((now, frame))
                while self.recent_audio and now - self.recent_audio[0][0] > 20:
                    self.recent_audio.popleft()
                yield frame

        async for event in Agent.default.stt_node(self, keep(audio), model_settings):
            if (isinstance(event, stt.SpeechEvent) and event.alternatives
                    and LABEL_ONLY_RE.match(event.alternatives[0].text)):
                logger.info("Call %s: dropped transcript %r (not speech)", self.call_id, event.alternatives[0].text)
                continue
            yield event

    def audio_between(self, start: float, end: float) -> list[rtc.AudioFrame]:
        return [frame for at, frame in self.recent_audio if start <= at <= end]

    async def tts_node(self, text: AsyncIterable[str], model_settings: ModelSettings):
        async def clean(chunks: AsyncIterable[str]):
            # Passed on a word at a time, so "finish_" + "call(" split across chunks is
            # still caught, and an open bracket is held until it closes (and is dropped)
            pending = ""
            async for chunk in chunks:
                pending += chunk
                if (code := LEAKED_CODE_RE.search(pending)):
                    # A tool call written out as text: say what came before it, nothing after
                    if pending[: code.start()].strip():
                        yield speakable(pending[: code.start()], self.language)
                    async for _ in chunks:
                        pass
                    return
                if OPEN_BRACKET_RE.search(pending):
                    continue
                cut = max(pending.rfind(" "), pending.rfind("\n"))
                if cut > 0:
                    yield speakable(pending[: cut + 1], self.language)
                    pending = pending[cut + 1:]
            if pending:
                yield speakable(pending, self.language)

        async for frame in Agent.default.tts_node(self, clean(text), model_settings):
            yield frame

    # -- each customer turn ----------------------------------------------------------

    async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage) -> None:
        if self.finished:
            raise StopResponse()  # the goodbye is playing
        text = (new_message.text_content or "").strip()
        if not text:
            return
        note = await self.take_turn(text)
        if note is None:
            raise StopResponse()
        if note:
            turn_ctx.add_message(role="system", content=note)

    async def take_turn(self, text: str) -> str | None:
        """What the app does with something the customer said, before the model replies.
        Returns None if the app answered it itself, else a note for the model ("" for none)."""
        self.on_heard(text)
        self.customer_texts.append(text)
        if self.callback_texts or CALLBACK_REQUEST_RE.search(text):
            self.callback_texts.append(text)
        if len(self.customer_texts) <= 3 and VOICEMAIL_RE.search(text):
            self.finished = True
            self.on_voicemail(text)
            return None
        asked = requested_language(text)
        if asked and asked != self.language:
            await self.switch_to(asked)
            return fill(script.PROMPTS.LANGUAGE_SWITCH_NOTE, {"language": NAMES[asked]})
        if self.paid_confirmation_asked:
            self.paid_confirmation_asked = False
            if refuses(text):
                # Customer clarified that they refuse: "No, I said I won't pay!"
                minimum = self._part_minimum()
                min_str = dates.format_inr(minimum)
                balance_str = dates.format_inr(float(self._call["amount"]))
                logger.info("Call %s: customer clarified refusal after payment question", self.call_id)
                return (f"The customer clarified that they refuse to pay. Acknowledge respectfully in one short sentence "
                        f"and ask ONCE if they can pay at least 30% ({min_str} of {balance_str}) for now. "
                        f"Don't call finish_call yet unless they refuse this 30% offer too.")
            elif is_plain_yes(text, "") or AGREES_RE.search(text) or PAID_CLAIM_RE.search(text):
                logger.info("Call %s: customer confirmed they already paid", self.call_id)
                await self._save("PAYMENT_MADE", None, 0,
                                 f"Customer confirmed payment already made; cross-check with the bank. Their words: {text}")
                return None

        if (self.verified or self._said_who_they_are()) and not self.someone_else and PAID_CLAIM_RE.search(text):
            # If explicit (mentions UPI, bank, date, or completed verb), save PAYMENT_MADE at once
            if EXPLICIT_PAID_RE.search(text):
                logger.info("Call %s: customer says they already paid (explicit)", self.call_id)
                await self._save("PAYMENT_MADE", None, 0,
                                 f"Customer says they already paid; cross-check with the bank. Their words: {text}")
                return None
            else:
                # Ambiguous: single bare verb (e.g. 'కట్టానండి' which sounds like refusal 'కట్టనండి')
                # Confirm once before recording PAYMENT_MADE
                logger.info("Call %s: ambiguous payment claim %r; asking confirmation", self.call_id, text)
                self.paid_confirmation_asked = True
                confirm_line = getattr(script.PROMPTS, "COLLECTION_CONFIRM_PAID", script.DEFAULT_LINES["COLLECTION_CONFIRM_PAID"])
                self.say_line(confirm_line)
                return None
        if not self.verified and not self.someone_else and is_plain_yes(text, self._call["customer_name"]):
            # "అవునండి" to the greeting, or to RIA asking again: until they are verified she
            # asks only who they are, so the balance follows at once from the call sheet
            self.tell_amount()
            return None
        if self.verified and self._refused_limit(text):
            self.limit_refusals += 1
            if self.limit_refusals == 1:
                # The first "no, market is bad": one more try within the allowed time, as a
                # person would, before it goes to the team as an extension request
                self.limit_offered_at = len(self.customer_texts)
                return (f"They can't pay by {self.latest_date:%A %d %B}. Acknowledge it in a few words, say the system "
                        f"gives time only until {self.latest_date:%d %B}, and ask for a convenient day before then. "
                        "Don't call any tool now unless they name a day.")
            # "లేదండి, అంతకు ముందు కుదరదు" again: an extension request for the team, saved at once
            await self._save("EXTENSION_REQUESTED", self.late_date, 0,
                             f"Customer can't pay by {self.latest_date}; asked for {self.late_date}.")
            return None
        if self.verified and (when := self._confirmed_read_back(text)):
            # "అవునండి" to the read-back: saved at once, no model turn before the goodbye
            # (that wait made the last reply the slowest of the call)
            code = "PARTIAL_PAYMENT_PROMISE" if self.part_amount else "PROMISE_TO_PAY"
            await self._save(code, when, self.part_amount,
                             f"Customer confirmed payment on {when}.{self._part_note(self.part_amount)}{self.balance_note}")
            return None
        if self.time_asked_at == len(self.customer_texts) - 1:
            # Their answer to "what time should I call?": "రేపు ఉదయం 11 కి" is the callback time,
            # which was taken for a payment day
            return ("They answered what time to call them back: call finish_call with CALLBACK_REQUESTED now (the "
                    "system books that exact time). It is not a payment date.")
        if (len(self.customer_texts) > 1 and CALLBACK_REQUEST_RE.search(self.customer_texts[-2])
                and (dates.said_a_date(text) or dates.said_a_time(text))):
            # "బిజీ, తర్వాత కాల్ చేయండి", the model asks when, "రేపు 11 కి": the callback time too
            return ("They asked to be called back just before: if this is the time to call them, call finish_call "
                    "with CALLBACK_REQUESTED now (the system books that exact time). Only if they now promise a "
                    "payment day, use check_payment_date.")
        if self.verified and UPSET_RE.search(text):
            # The demo script: apologise, and offer one call at their time or no more calls
            return ("They are upset about the calls. Apologise in one short sentence and don't mention the payment "
                    "now. If they clearly said not to call again, call finish_call with DO_NOT_CALL; otherwise offer "
                    "to call only once, at a time that suits them, or to note that they don't want calls about this.")
        if self.verified and not CALLBACK_REQUEST_RE.search(text) and not CONTRADICTS_RE.search(text):
            if (plan := self._paying_in_parts(text)) is not None:
                return plan
            if found := dates.spoken_date(text, refuses):
                when, words = found
                self.named_days[when] = len(self.customer_texts)
                logger.info("Call %s: customer named %s (%r)", self.call_id, when, words)
                return (f"The customer named their payment day: “{words}” = {when:%A %d %B %Y}. Call "
                        f"check_payment_date with {when.isoformat()} now (with part_amount if they will pay only part "
                        "of the balance then); don't ask which day.")
        if self.someone_else and not self.verified:
            # They already said they aren't the customer: "in one hour, he'll be back" was met
            # with "are you Gyan Vardhan?" again. The app has asked when the customer is free
            name = self._call["customer_name"]
            return (f"Someone other than {name} is speaking: share nothing about the invoice and don't ask who they "
                    f"are again. You have asked when {name} can be reached: if they said a time, or that they don't "
                    "know, call finish_call with CALLBACK_REQUESTED now (the app books that exact time, or the next "
                    "calling slot). Otherwise answer them in one short sentence.")
        if not self.verified and self._asked_about_payments():
            # Their answer to "do you handle Gyan's payments?": "తెలియదండి" or "లేదండి" was
            # met with "are you Gyan?" again
            name = self._call["customer_name"]
            return (f"They were asked whether they handle {name}'s payments: yes → verify_customer payments_person; "
                    f"no → verify_customer someone_else; they don't know {name} or the business → verify_customer "
                    "wrong_number. Share nothing about the invoice.")
        if not self.verified and not self._said_who_they_are():
            name = self._call["customer_name"]
            hello = HELLO_ONLY_RE.match(text) and self.who_asks < 3
            if not hello and NOT_THEM_RE.search(text):
                # "కాదు", "he's not here", "call later": the model records it (someone else,
                # wrong number, callback). The payments question it may lead to gets ready now
                self.lines.prepare(self.line_text(script.PROMPTS.COLLECTION_PAYMENTS_ASK))
                return (f"They haven't said they are {name} or handle their payments: share nothing about the "
                        "invoice, and don't ask who they are again. If they said they are not, call verify_customer "
                        f"with someone_else or wrong_number (the system then asks whether they handle {name}'s "
                        "payments). If they are busy, call finish_call with CALLBACK_REQUESTED; the system says "
                        "goodbye.")
            if not hello and not self.last_line_interrupted:
                self.unclear_after_heard += 1
            # A who line they talked over ("హలో?" over the greeting, line noise) wasn't heard, so it
            # doesn't count: calls were given up after ~15 s, the question never heard once
            if not hello and (self.unclear_after_heard >= 3 or self.who_asks >= 5):
                # Still unclear after three who questions they heard (or five asks on a noisy line):
                # a callback, booked by the app. The model once said "I'll call back" without
                # saving it, and the call went on
                logger.info("Call %s: couldn't tell who answered; booking a callback", self.call_id)
                await self._save("CALLBACK_REQUESTED", None, 0, "Couldn't confirm who answered the phone.")
                return None
            # Unclear, "who is this?", "హలో?", a call-screening assistant: the app says who RIA
            # is and asks again. The model never speaks before they say who they are: it asked
            # for a payment date, and once told the due date, to people who never confirmed
            self.who_asks += 1
            logger.info("Call %s: asking who they are (%d; %d unclear after hearing it)",
                        self.call_id, self.who_asks, self.unclear_after_heard)
            self.say_line(script.PROMPTS.COLLECTION_WHO_ASK)
            return None
        if HELLO_ONLY_RE.match(text):
            # Checking the line: answering with the balance again was too much
            return ("They said hello to check the line. Say in a few words that you can hear them, then ask "
                    "your last question again in one short sentence.")
        return ""

    def _paying_in_parts(self, text: str) -> str | None:
        """A note for "half now, the rest next week": the first part's day is the promise
        (the last day said, next week, was taken for it), the rest goes in the notes."""
        rest = REST_RE.search(text)
        if not rest or rest.start() == 0 or "?" in text:
            return None
        before, balance = text[: rest.start()], text[rest.start():].strip(" ,.।")
        found = dates.spoken_date(before, refuses)
        first = found[0] if found else (dates.today() if NOW_RE.search(before) else None)
        if first is None:
            if not dates.spoken_date(text, refuses):
                return None  # no day at all: not a payment plan
            return ("They will pay in parts but didn't say which day they pay the first part. Ask that in one short "
                    "sentence; don't call check_payment_date yet.")
        self.named_days[first] = len(self.customer_texts)
        self.balance_note = f" Balance: “{balance}”."
        half = dates.format_inr(float(self._call["amount"]) / 2)
        logger.info("Call %s: paying in parts, first on %s; balance %r", self.call_id, first, balance)
        return (f"They will pay in parts: the first part on {first:%A %d %B %Y}, the rest later (“{balance}”). Call "
                f"check_payment_date with {first.isoformat()} and part_amount = the first part (half the balance is "
                f"{half}); don't ask which day.")

    async def answer_backup(self, text: str) -> None:
        """A customer turn Pulse missed, transcribed from the saved audio instead."""
        note = await self.take_turn(text)
        if note is not None and not self.finished:
            self.session.generate_reply(user_input=text, instructions=note or None)

    # -- tools -------------------------------------------------------------------------

    @llm.function_tool
    async def verify_customer(
        self,
        context: RunContext,
        who: Annotated[
            Literal["customer", "payments_person", "someone_else", "wrong_number"],
            "customer: they are the customer named in CALL DATA; payments_person: they handle payments for that "
            "business; someone_else: another person; wrong_number: they don't know the customer or business",
        ],
    ):
        """Record who picked up, once they have said it. For customer or payments_person
        the system then tells them the balance from the call sheet; for someone_else or
        wrong_number it asks them the next question itself. Say nothing yourself."""
        if self.verified and who in ("someone_else", "wrong_number"):
            # Already confirmed: a later misheard line ("ఆప్ కాసి భాస్కర్ రేహే", Hindi for
            # "where are you calling from?") isn't a different person
            return "They already confirmed they are the customer. Answer what they just said."
        if who in ("customer", "payments_person"):
            if not self._said_who_they_are():
                logger.info("Call %s: not verified yet: they haven't said who they are", self.call_id)
                return (f"Not verified: they haven't said they are {self._call['customer_name']} or handle payments. "
                        f"Ask once more, simply, whether you are speaking with {self._call['customer_name']}. "
                        "Share nothing about the invoice until they say yes.")
            self.tell_amount()
            return llm.ToolResult("Verified. The system is telling them the balance and asking when they can pay; "
                                  "say nothing now and wait for their answer.", reply_required=False)
        # The user's rule (prompts.py) for someone else on the phone, each step said by the app:
        # the model's second reply after this tool made these the slowest turns (~3.5 s)
        name = self._call["customer_name"]
        if not self._asked_about_payments():
            # First: do they handle the customer's payments?
            self.payments_asked = True
            self.say_line(script.PROMPTS.COLLECTION_PAYMENTS_ASK)
            self.lines.prepare(self.line_text(script.PROMPTS.COLLECTION_MESSAGE, script.PROMPTS.COLLECTION_WHEN_AVAILABLE))
            return llm.ToolResult(f"The system asked whether they handle {name}'s payments; say nothing now and wait "
                                  "for their answer.", reply_required=False)
        if who == "wrong_number":
            await self._save("WRONG_NUMBER", None, 0, f"They don't know {name} or the business.")
            return llm.ToolResult("Saved. The goodbye is being played; say nothing.", reply_required=False)
        if self.someone_else:
            return "Already noted. Answer what they just said; share nothing about the invoice."
        # They don't: they pass on that RIA from accounts called, and the callback is booked
        self.someone_else = True
        said = [t for t in self.customer_texts if dates.callback_time([t])]
        if not said:
            self.callback_time_asked = True  # "I don't know" to it books the next calling slot
            self.say_line(script.PROMPTS.COLLECTION_MESSAGE, script.PROMPTS.COLLECTION_WHEN_AVAILABLE)
            return llm.ToolResult(f"The system asked them to tell {name} that RIA called, and when {name} can be "
                                  "reached; say nothing now and wait for their answer.", reply_required=False)
        # They already gave the time ("ఆయన లేరు, గంట తర్వాత చేయండి"): the message (queued before
        # the goodbye), then the callback for that time
        await self.lines.say(self.session, self.line_text(script.PROMPTS.COLLECTION_MESSAGE))
        self.callback_texts = said
        return await self._finish("CALLBACK_REQUESTED", "", 0, f"{name} wasn't available; someone else answered.")

    def _asked_about_payments(self) -> bool:
        """RIA asked whether they handle the payments: the app's line, or the model in its own words."""
        return self.payments_asked or any(
            getattr(item, "role", None) == "assistant" and PAYMENTS_ASKED_RE.search(item.text_content or "")
            for item in self.chat_ctx.items)

    def _said_who_they_are(self) -> bool:
        """A yes to "am I speaking with Ravi garu?", "నేనే", or "I handle payments"."""
        name = self._call["customer_name"]
        return any(is_plain_yes(t, name)
                   or ((IDENTITY_RE.search(t) or says_name(t, name)) and not WHO_QUESTION_RE.search(t) and "?" not in t)
                   or re.search(r"(?:^|\W)(?:అవున|ఆవున|ఔన|ఆనండ|ఆఉండ|అవుండ|हाँ|हां)|\b(?:yes|yeah|correct)\b", t, re.I)
                   for t in self.customer_texts)

    @llm.function_tool
    async def switch_language(
        self,
        context: RunContext,
        language: Annotated[Literal["te", "hi", "en"], "te Telugu, hi Hindi, en English"],
    ):
        """Change the conversation language: the customer asked for it, or has been
        speaking it (Hindi or English may reach you written in Telugu letters)."""
        await self.switch_to(language)
        follow = "" if self.verified else (" If they have already said who they are (a yes or 'tell me' to the "
                                          "greeting counts), call verify_customer now; don't ask again.")
        return f"Now speak only {NAMES[language]}.{follow}"

    @llm.function_tool
    async def check_payment_date(
        self,
        context: RunContext,
        payment_date: Annotated[str, "YYYY-MM-DD: the day the customer said, looked up in the calendar"],
        part_amount: Annotated[float, "Rupees, if they will pay only part of the balance on that day; else 0"] = 0,
    ):
        """Use as soon as the customer names the day they will PAY (never for a callback
        time). The system reads it back to them (or tells them the latest date accounts
        allow); say nothing yourself."""
        when = dates.parse_iso(payment_date)
        if not when:
            return "Give the date as YYYY-MM-DD, taken from the calendar in your instructions."
        if when < dates.today():
            return f"{when:%d %B} has passed (today is {dates.today():%d %B}). Ask which day from today on."
        # The day must be in what they just said: after "అవునండి కరెక్ట్" the model once
        # read back today, made up, because an earlier line had "రోజు" in it
        heard = any(dates.said_a_date(t) for t in self.customer_texts[-2:]) or any(
            at >= len(self.customer_texts) - 1 for at in getattr(self, "named_days", {}).values())
        if not heard:
            # Asked again and the model lands on the same day from a real answer (not a bare
            # "సరే"): a day said in words this check can't read; the read-back confirms it
            if getattr(self, "unread_day", None) != when or len(self.customer_texts[-1].split()) < 3:
                self.unread_day = when
                return "The customer hasn't named a day just now. Ask them which day; never suggest one."
        if CALLBACK_REQUEST_RE.search(self.customer_texts[-1]):
            return ("They asked to be called back: that is a callback time, not a payment day. Confirm the time "
                    "and call finish_call with CALLBACK_REQUESTED.")
        if note := self._part_below_minimum(part_amount, when):
            return note
        self.part_amount = part_amount or 0
        return self._read_back(when)

    def _part_minimum(self) -> int:
        """Company policy: a part payment is at least 30% of the balance."""
        return math.ceil(float(self._call["amount"]) * 0.30)

    def _part_below_minimum(self, amount: float, when: date) -> str | None:
        """Asked once when a part payment is under the minimum (₹26,000 was taken where
        ₹26,369 was the least allowed); after that it is saved with a note for the team."""
        minimum = self._part_minimum()
        if not 0 < (amount or 0) < minimum or self.part_minimum_asked:
            return None
        self.part_minimum_asked = True
        return (f"Not saved: {dates.format_inr(amount)} is below the minimum part payment of "
                f"{dates.format_inr(minimum)} (30% of the {dates.format_inr(float(self._call['amount']))} balance). "
                f"Tell them the minimum is {dates.format_inr(minimum)} and ask once if they can pay that by "
                f"{when:%d %B}; then use check_payment_date again with the amount they agree to.")

    def _part_note(self, amount: float) -> str:
        minimum = self._part_minimum()
        return f" Below the minimum part payment ({dates.format_inr(minimum)})." if 0 < (amount or 0) < minimum else ""

    def _already_offered_partial(self) -> bool:
        """Check whether Ria has already proposed the 30% partial payment option."""
        if self.refusal_offered_partial:
            return True
        partial_offer_re = re.compile(
            r"30\s*%|30\s*శాతం|30\s*प्रतिशत|\bpartial\b|కనీసం 30|at least 30|30 percent",
            re.I
        )
        for item in getattr(self.chat_ctx, "items", []):
            if getattr(item, "role", None) == "assistant":
                text = getattr(item, "text_content", "") or ""
                if partial_offer_re.search(text):
                    return True
        return False

    def _read_back(self, when: date) -> llm.ToolResult:
        if when > self.latest_date:
            self.limit_offered_at = len(self.customer_texts)
            self.late_date = when
            self.read_backs[self.latest_date] = len(self.customer_texts)
            logger.info("Call %s: %s is after the latest allowed %s; offering it", self.call_id, when, self.latest_date)
            self.say_line({k: dates.date_line(script.PROMPTS.DATE_LIMIT_LINES, self.latest_date, k)
                           for k in script.PROMPTS.DATE_LIMIT_LINES})
            return llm.ToolResult(
                f"The system told them accounts allow time only until {self.latest_date:%A %d %B} and asked if they "
                f"can pay by then. Wait for their answer: yes → finish_call PROMISE_TO_PAY with promised_date "
                f"{self.latest_date.isoformat()}; a clear no → acknowledge it and ask for a day before then; only a second no → EXTENSION_REQUESTED with {when.isoformat()} in the notes.",
                reply_required=False)
        self.read_backs[when] = len(self.customer_texts)
        logger.info("Call %s: reading back %s", self.call_id, when)
        self.say_line({k: dates.date_line(script.PROMPTS.DATE_READBACKS, when, k)
                       for k in script.PROMPTS.DATE_READBACKS})
        return llm.ToolResult(
            f"The system read {when:%A %d %B} back to them and asked if it's right. Wait for their answer: yes → "
            f"finish_call PROMISE_TO_PAY with promised_date {when.isoformat()}; no → ask which day.",
            reply_required=False)

    def _agreed_to(self, when: date) -> bool:
        """The customer answered the read-back of `when`, and the answer doesn't
        contradict it: no "no", no "already paid" / "call later", no other day."""
        asked_at = self.read_backs.get(when)
        if asked_at is None or len(self.customer_texts) <= asked_at:
            return False
        answer = self.customer_texts[-1]
        return not (refuses(answer) or CONTRADICTS_RE.search(answer) or self._names_other_day(answer, when))

    @staticmethod
    def _names_other_day(text: str, when: date) -> bool:
        """ "Yes, tomorrow" after RIA read back Friday: the answer names another day,
        and not Friday too ("not Thursday, Friday" is fine)."""
        lowered = dates.AMOUNT_RE.sub(" ", dates.MONEY_RE.sub(" ", text)).lower()
        same = other = False
        if (relative := dates.relative_day([text])) is not None:
            same, other = relative == when, relative != when
        for i, names in enumerate(dates.WEEKDAY_WORDS):
            if any(n in lowered for n in names):
                same, other = same or i == when.weekday(), other or i != when.weekday()
        for day in re.findall(r"(?<![\d₹$.,])(\d{1,2})(?![\d,.:])", lowered):
            same, other = same or int(day) == when.day, other or int(day) != when.day
        return other and not same

    @llm.function_tool
    async def finish_call(
        self,
        context: RunContext,
        code: Annotated[OutcomeCode, "The one outcome code for this call"],
        promised_date: Annotated[
            str, "YYYY-MM-DD: the payment date the customer agreed to, or the callback day they gave; else empty"
        ] = "",
        promised_amount: Annotated[float, "Rupees promised if less than the full balance (part payment), else 0"] = 0,
        notes: Annotated[str, "One short factual English line, e.g. 'Customer requested callback after 5 PM.'"] = "",
    ):
        """Record the call's outcome and end the call. The system says the closing line;
        say nothing yourself.

        Pick the code from what the customer actually said:
        PROMISE_TO_PAY: agrees to pay the full balance on a day they named.
        PARTIAL_PAYMENT_PROMISE: agrees to pay part of it, with the amount and the day.
        PAYMENT_MADE: says they have already paid.
        PAYMENT_VERIFICATION_REQUIRED: says they paid, but part, a different amount, or they aren't sure.
        PAYMENT_DATE_UNKNOWN: will pay but can't say when.
        INVOICE_DISPUTE: says the invoice, amount or rate is wrong, or they don't owe it.
        DELIVERY_ISSUE: goods not received, short, damaged or returned.
        INVOICE_COPY_REQUESTED: asks for an invoice copy, statement or ledger.
        CALLBACK_REQUESTED: busy now, or the customer isn't there; call another time.
        PAYMENT_REFUSED: clearly won't pay and gives none of the reasons above (only after offering 30% partial payment once).
        CUSTOMER_UPSET: angry, abusive or complaining about the company or the calls.
        WRONG_NUMBER: they don't know the customer or the business.
        DO_NOT_CALL: asks not to be called again.
        EXTENSION_REQUESTED: can pay only after the latest date accounts allow.
        OTHER: none of these.
        When two fit, the reason wins: a dispute, delivery issue or "already paid" over
        PAYMENT_REFUSED. If a customer initially refuses payment (e.g. "I won't pay" / "కట్టను"),
        propose paying 30% once before recording PAYMENT_REFUSED."""
        return await self._finish(code, promised_date, promised_amount, notes)

    async def _finish(self, code: str, promised_date: str, promised_amount: float, notes: str):
        if self.finished:
            return llm.ToolResult("Already saved. Say nothing more.", reply_required=False)
        if not self.customer_texts:
            return "Not saved: the customer hasn't answered yet. Wait for them."
        if code not in SAVE_UNVERIFIED and not self.verified:
            return ("Not saved: you haven't confirmed you're speaking with the customer or their payments person. "
                    "Ask, then call verify_customer.")
        when = dates.parse_iso(promised_date)
        if code == "DO_NOT_CALL" and not any(DO_NOT_CALL_RE.search(t) for t in self.customer_texts[-3:]):
            return ("Not saved: they haven't asked not to be called again. If that is what they mean, ask them "
                    "once whether they want no more calls about this invoice.")

        if code == "PAYMENT_REFUSED" and self.has_amount and not self._already_offered_partial():
            self.refusal_offered_partial = True
            minimum = self._part_minimum()
            min_str = dates.format_inr(minimum)
            balance_str = dates.format_inr(float(self._call["amount"]))
            logger.info("Call %s: customer refused payment; proposing 30%% partial payment (%s)", self.call_id, min_str)
            return llm.ToolResult(
                f"Do not end the call yet. The customer refused payment. Acknowledge respectfully and ask ONCE "
                f"if they can pay at least 30% ({min_str} of {balance_str}) for now. If they agree, get their payment date "
                f"and call check_payment_date. If they refuse this 30% partial payment offer as well, accept their refusal "
                f"politely and call finish_call with PAYMENT_REFUSED.",
                reply_required=True,
            )

        if code == "EXTENSION_REQUESTED":
            if when and when <= self.latest_date:
                code = "PROMISE_TO_PAY"  # in time: no extension needed, it's a promise
            elif self.limit_offered_at is None:
                return self._read_back(when) if when else "Not saved: ask which day they can pay."
            elif self._agreed_to(self.latest_date) and AGREES_RE.search(self.customer_texts[-1]):
                code, when = "PROMISE_TO_PAY", self.latest_date  # they said yes to the latest date
        if code in ("PROMISE_TO_PAY", "PARTIAL_PAYMENT_PROMISE"):
            if not when:
                return "Not saved: a promise needs the date. Ask which day, then use check_payment_date."
            if not self._agreed_to(when):
                if when in self.read_backs:
                    return "Not saved: they haven't agreed to that date. Ask which day suits them."
                if not any(dates.said_a_date(t) for t in self.customer_texts):
                    return "Not saved: the customer hasn't named a day. Ask them which day; never suggest one."
                return self._read_back(when)  # they must hear the date before it is saved
            if code == "PARTIAL_PAYMENT_PROMISE":
                amount = promised_amount or self.part_amount
                if note := self._part_below_minimum(amount, when):
                    return note
                # The part read back, also when the model leaves the amount out (the full
                # balance was shown as promised)
                promised_amount = amount
                notes = f"{notes}{self._part_note(amount)}".strip()
            notes = f"{notes}{self.balance_note}".strip()
        elif code == "CALLBACK_REQUESTED":
            # Only the day and time the customer gave, in the callback part of the call:
            # callbacks were saved for days nobody said
            said = self.callback_texts or self.customer_texts[-2:]
            said_day = any(dates.said_a_date(t) for t in said)
            said_time = any(dates.said_a_time(t) for t in said)
            if said_day and (relative := dates.relative_day(said)):
                # "రేపు 5 గంటలకు": the customer's own word decides the day (the model left it
                # out once, and once saved today)
                when = relative
            # The exact moment from their own words, also when someone else answered: "ఒక గంట
            # తర్వాత" was booked 5 minutes later, as the model's notes had no clock time
            at = dates.callback_time(said, when if said_day else None)
            if not at and not self.callback_time_asked:
                # Vague ("ఎల్లుండి సాయంత్రం"), already past ("ఉదయం 9" at 4 PM) or none ("busy, call
                # later"): asked once (the user's rule: no callback without a clear time; the demo
                # script: "what time suits you? I'll call exactly then"). The app asks: the model's
                # second reply here took ~4 s. A second time without one: the next calling slot
                self.callback_time_asked = True
                self.time_asked_at = len(self.customer_texts)
                self.say_line(script.PROMPTS.CALLBACK_TIME_ASK)
                return llm.ToolResult("Not saved: no exact time yet, so the system asked them what time to call. Say "
                                      "nothing now; when they answer, call finish_call with CALLBACK_REQUESTED again.",
                                      reply_required=False)
            rest = dates.CLOCK_RE.sub("", notes).strip(" ,.;")  # the model's own clock times aren't used
            if at:
                when, notes = at.date(), f"Callback at {at:%I:%M %p}. {rest}".strip()
            elif said_day:
                # Still no exact time: the first calling hour of the day they named
                notes = rest or "Customer asked for a callback on that day but gave no exact time."
            else:
                when, notes = None, "Customer asked for a callback but gave no day or time."
        elif code != "EXTENSION_REQUESTED":
            when = None  # "date unknown", disputes...: no date was promised

        await self._save(code, when, promised_amount, notes)
        return llm.ToolResult("Saved. The goodbye is being played; say nothing.", reply_required=False)

    async def _save(self, code: str, when: date | None, amount: float, notes: str) -> None:
        self.finished = True
        saved_notes = notes_for(code, notes, when)
        if not OUTCOME_CODES[code][1] and any(STATEMENT_RE.search(t) for t in self.customer_texts):
            # "Send me the ledger first", then a date: the promise, and the statement ticket too
            saved_notes = f"{saved_notes} Statement requested. | ticket: account_statement_or_ledger".strip()[:300]
        await asyncio.to_thread(
            DB.save_collection_call,
            self.call_id,
            outcome=OUTCOME_CODES[code][0],
            promised_date=when.isoformat() if when else None,
            promised_amount=amount or None,
            notes=saved_notes or None,
            language=self.language,
        )
        logger.info("Call %s: %s %s", self.call_id, code, when or "")
        self.on_finished(code)

    def _refused_limit(self, text: str) -> bool:
        """A clear no, just now, to "accounts allow time only until ..."."""
        return (self.late_date is not None and self.limit_offered_at == len(self.customer_texts) - 1
                and refuses(text) and not AGREES_RE.search(text) and "?" not in text)

    def _confirmed_read_back(self, text: str) -> date | None:
        """The date RIA read back in her last line, if this reply is a short yes to it."""
        asked = [when for when, at in self.read_backs.items() if at == len(self.customer_texts) - 1]
        if (not asked or len(text.split()) > 6 or refuses(text) or CONTRADICTS_RE.search(text)
                or DOUBT_RE.search(text) or "?" in text or self._names_other_day(text, asked[0])):
            return None
        return asked[0] if (AGREES_RE.search(text) or is_plain_yes(text, "")) else None
