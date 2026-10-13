"""prompts.py: RIA's instructions and fixed lines.

The file is read again at the start of every call, so an edit applies from the
next call without a restart. An entry left out of the file keeps its last working
version, so prompts.py can hold only what is being edited. A broken edit (a syntax
error, an empty or malformed entry) keeps the whole last working version and logs why.
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import re
from types import SimpleNamespace

import prompts as prompts_file
from ria.settings import BACKEND_DIR

logger = logging.getLogger("ria-agent")

TEXTS = ("COLLECTION_INSTRUCTIONS", "LANGUAGE_SWITCH_NOTE")
# Other names prompts.py may give an entry: the instructions written as RIA_SYSTEM_PROMPT
# were left unused, and calls ran on the last working version
ALIASES = {"COLLECTION_INSTRUCTIONS": "RIA_SYSTEM_PROMPT"}
LINES = (
    "COLLECTION_OPENINGS", "COLLECTION_WHO_ASK", "COLLECTION_AMOUNT_LINES", "DUE_PHRASES", "DATE_READBACKS", "DATE_LIMIT_LINES",
    "COLLECTION_GOODBYES", "COLLECTION_ARE_YOU_THERE", "COLLECTION_REPEAT", "UNKNOWN_CALLER",
    "COLLECTION_PAYMENTS_ASK", "COLLECTION_MESSAGE", "COLLECTION_WHEN_AVAILABLE", "CALLBACK_TIME_ASK",
)
# Lines the app speaks after a tool instead of a second model reply (that took ~2.5 s),
# which prompts.py has never had: these words until prompts.py gives its own
DEFAULT_LINES = {
    # Someone else answered: do they handle the payments? (the user's rule in prompts.py)
    "COLLECTION_PAYMENTS_ASK": {
        "te": "{customer} గారి payments, accounts మీరు చూసుకుంటారా అండీ?",
        "hi": "क्या {customer} जी के payments और accounts आप देखते हैं?",
        "en": "Do you handle the payments or accounts for {customer}?",
    },
    # ...they don't: the message for the customer, then when to call back
    "COLLECTION_MESSAGE": {
        "te": "దయచేసి {customer} గారికి {company} accounts team నుంచి RIA call చేశారని చెప్పండి.",
        "hi": "कृपया {customer} जी को बता दीजिए कि {company} accounts team से RIA का call आया था।",
        "en": "Please tell {customer} that RIA from the {company} accounts team called.",
    },
    "COLLECTION_WHEN_AVAILABLE": {
        "te": "{customer} గారు ఎప్పుడు అందుబాటులో ఉంటారు?",
        "hi": "{customer} जी से कब बात हो पाएगी?",
        "en": "When can we reach {customer}?",
    },
    # A callback with no exact time: none ("busy, call later"), vague ("రేపు సాయంత్రం") or past
    "CALLBACK_TIME_ASK": {
        "te": "తప్పకుండా అండీ. ఏ time కి call చేయమంటారు? సరిగ్గా ఆ time కే call చేస్తాను.",
        "hi": "ज़रूर जी। किस time पर call करूँ? ठीक उसी time पर call करूँगी।",
        "en": "Of course. What time should I call? I'll call you exactly then.",
    },
}
# Goodbyes for outcomes prompts.py has none for (it uses the general one otherwise)
DEFAULT_CLOSINGS = {
    # Won't commit to anything now (the demo script): the team follows up in person
    "PAYMENT_REFUSED": {
        "te": "పర్లేదండీ, అర్థం చేసుకున్నాను. మీ response note చేసుకున్నాను, మా team నుంచి ఎవరైనా మీతో personal గా మాట్లాడతారు. Thank you.",
        "hi": "कोई बात नहीं जी, मैं समझती हूँ। मैंने आपका response note कर लिया है, हमारी team से कोई आपसे personally बात करेगा। धन्यवाद।",
        "en": "That's alright, I understand. I've noted your response, and someone from our team will speak with you personally. Thank you.",
    },
}
# Placeholders prompts.py may use; any other {word} is spoken as written
FIELDS = frozenset((
    "company", "customer", "business", "business_name", "invoice_no", "invoice_date", "amount", "balance_due", "invoice_amount",
    "due_date", "overdue", "today", "calendar", "language", "days", "day", "month", "weekday", "latest_date",
    "extension_days", "previous_promised_date", "customer_id",
))
PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")
DUE_KINDS = {"overdue", "overdue_one", "today", "upcoming"}

PROMPTS = SimpleNamespace()
# The last prompts.py that loaded, kept on disk: an edit that deleted the fixed lines
# once stopped the agent from starting at all, and every call went out silent
LAST_GOOD = os.path.join(BACKEND_DIR, "tts_cache", "prompts_last_good.json")


def base_language(lines: dict) -> str:
    """The language a set of lines falls back to: English if written, else the first."""
    return "en" if "en" in lines else next(iter(lines))


def pick(lines: dict, language: str):
    """The line for this language, else the fallback language's line."""
    return lines[language] if language in lines else lines[base_language(lines)]


def fill(template: str, values: dict) -> str:
    """{name} -> its value. Unknown names and stray braces stay as written."""
    return PLACEHOLDER_RE.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), template)


def last_good() -> dict:
    """The last prompts.py that loaded, as saved on disk, or {}."""
    try:
        with open(LAST_GOOD, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def load() -> SimpleNamespace:
    """prompts.py as it is now, or the last working version if it is broken."""
    global PROMPTS
    try:
        module = importlib.reload(prompts_file)

        def given(name, default=None):
            alias = ALIASES.get(name, "")
            return getattr(module, name, getattr(module, alias, default) if alias else default)

        # Entries the file leaves out: the last working version's
        saved = vars(PROMPTS) or last_good()
        kept = [name for name in (*TEXTS, *LINES, "CLOSING_LINES") if given(name) is None and name in saved]
        if kept:
            logger.info("prompts.py has no %s; using the last working version of those", ", ".join(kept))

        def entry(name, default=None):
            return saved[name] if name in kept else given(name, default)

        loaded = {}
        for name in TEXTS:
            value = entry(name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is missing or empty")
            loaded[name] = value
        for name in LINES:
            value = entry(name, DEFAULT_LINES.get(name))
            if not isinstance(value, dict) or not value or not all(value.values()):
                raise ValueError(f"{name} must give at least one language's line, none empty")
            loaded[name] = value
        for language, phrases in loaded["DUE_PHRASES"].items():
            if not isinstance(phrases, dict) or DUE_KINDS - set(phrases):
                raise ValueError(f"DUE_PHRASES[{language!r}] needs {', '.join(sorted(DUE_KINDS))}")
        closings = entry("CLOSING_LINES", {})
        if not isinstance(closings, dict) or not all(isinstance(v, dict) and v for v in closings.values()):
            raise ValueError("CLOSING_LINES must map each outcome code to at least one language's line")
        loaded["CLOSING_LINES"] = {**DEFAULT_CLOSINGS, **closings}
    except Exception as e:
        if not vars(PROMPTS):
            if not (saved := last_good()):
                raise e from None  # nothing to fall back on: the agent can't start without its prompts
            PROMPTS = SimpleNamespace(**{**DEFAULT_LINES, **saved})
        logger.error("prompts.py not used (%s); using the last working version", e)
        return PROMPTS
    unknown = {m for v in loaded.values() for m in PLACEHOLDER_RE.findall(json.dumps(v, ensure_ascii=False))}
    if unknown - FIELDS:
        logger.warning("prompts.py uses unknown placeholders %s; they are spoken as written",
                       ", ".join(f"{{{u}}}" for u in sorted(unknown - FIELDS)))
    PROMPTS = SimpleNamespace(**loaded)
    try:
        os.makedirs(os.path.dirname(LAST_GOOD), exist_ok=True)
        # One temp file per process: two calls starting together raced on a shared one
        tmp = f"{LAST_GOOD}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(loaded, f, ensure_ascii=False)
        os.replace(tmp, LAST_GOOD)
    except OSError:
        logger.warning("Couldn't save the last working prompts.py")
    return PROMPTS


load()
