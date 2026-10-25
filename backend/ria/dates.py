"""Dates: the calendar the model reads, the payment-date limit, and how dates are said.



The model turns what the customer said ("ఈ నెల 31", "in ten days", "Friday")

into a date by looking it up in the calendar in its instructions, which labels

every day with how far off it is, so it never does date arithmetic itself.

"""

from __future__ import annotations



import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable



from dialer import IST

from ria import script

from ria.script import base_language, fill, pick

logger = logging.getLogger(__name__)



# Monday first, as date.weekday() counts

WEEKDAY_NAMES = {

    "te": ["సోమవారం", "మంగళవారం", "బుధవారం", "గురువారం", "శుక్రవారం", "శనివారం", "ఆదివారం"],

    "hi": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],

    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "ta": ["திங்கள்", "செவ்வாய்", "புதன்", "வியாழன்", "வெள்ளி", "சனி", "ஞாயிறு"],
    "kn": ["ಸೋಮವಾರ", "ಮಂಗಳವಾರ", "ಬುಧವಾರ", "ಗುರುವಾರ", "ಶುಕ್ರವಾರ", "ಶನಿವಾರ", "ಭಾನುವಾರ"],

}

MONTH_NAMES = {

    "te": ["జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్", "జూలై", "ఆగస్టు",

           "సెప్టెంబర్", "అక్టోబర్", "నవంబర్", "డిసెంబర్"],

    "hi": ["जनवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",

           "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
    "ta": ["ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்"],
    "kn": ["ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್", "ಮೇ", "ಜೂನ್", "ಜುಲೈ", "ಆಗಸ್ಟ್", "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್", "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್"],

}





def today() -> date:
    """Return the current calendar date in the application's configured IST timezone."""
    return datetime.now(IST).date()





def calendar(start: date, days: int = 45) -> str:

    """The next weeks, one line per day: "Mon 19 Oct 2026 = 2026-10-19 (in 10 days)"."""

    lines = []

    for i in range(0, days + 1):

        day = start + timedelta(days=i)

        ahead = "today" if i == 0 else "tomorrow" if i == 1 else "day after tomorrow" if i == 2 else f"in {i} days"

        lines.append(f"{day:%a %d %b %Y} = {day.isoformat()} ({ahead})")

    return "\n".join(lines)





def extension_days(call: dict) -> int:
    """Return the configured calendar-day PTP window, defaulting safely to 7 days.

    Invalid, boolean, zero, negative, or unreasonable configuration values fall back
    to the documented default rather than silently weakening policy.
    """
    rules = (call.get("tenant_config") or {}).get("rules") or {}
    raw = rules.get("ptpwindow_days", 7)
    if isinstance(raw, bool):
        return 7
    try:
        days = int(raw)
    except (TypeError, ValueError, OverflowError):
        return 7
    # Invalid low values fail closed at one day rather than widening the payment window.
    # Cap excessive configuration values; tenant policy should validate these on write.
    if days < 1:
        return 1
    return min(days, 365)


def _as_date(value: Any) -> date | None:
    """Strictly normalize an ISO date or date object; datetimes are not accepted."""
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_iso(value)
    return None


def latest_promise_date(call: dict, *, as_of: date | None = None) -> date | None:
    """Return the latest PTP date allowed by policy, or None for invalid due-date data.

    For an invoice whose due-date window has already expired, preserve the existing
    application rule: allow the configured window from today. This must match tenant policy.
    """
    due = _as_date(call.get("due_date"))
    if due is None:
        return None
    current = as_of if isinstance(as_of, date) and not isinstance(as_of, datetime) else today()
    latest = due + timedelta(days=extension_days(call))
    return latest if latest >= current else current + timedelta(days=extension_days(call))


def validate_promise_date(
    call: dict, value: str | date, *, as_of: date | None = None
) -> date | None:
    """Normalize a proposed PTP date only if it is valid, non-past and policy-compliant."""
    proposed = _as_date(value)
    current = as_of if isinstance(as_of, date) and not isinstance(as_of, datetime) else today()
    if proposed is None or proposed < current:
        return None
    latest = latest_promise_date(call, as_of=current)
    if latest is None or proposed > latest:
        return None
    return proposed



def format_inr(amount: float) -> str:

    """₹ with Indian digit grouping: 1234567.5 -> ₹12,34,567.50"""

    rupees, paise = divmod(round(amount * 100), 100)

    digits = str(rupees)

    head, tail = digits[:-3], digits[-3:]

    while len(head) > 2:

        tail = f"{head[-2:]},{tail}"

        head = head[:-2]

    text = f"{head},{tail}" if head else tail

    return f"₹{text}.{paise:02d}" if paise else f"₹{text}"





TE_COUNT_WORDS = {
    1: "ఒక", 2: "రెండు", 3: "మూడు", 4: "నాలుగు", 5: "ఐదు",
    6: "ఆరు", 7: "ఏడు", 8: "ఎనిమిది", 9: "తొమ్మిది", 10: "పది",
    11: "పదకొండు", 12: "పన్నెండు", 13: "పదమూడు", 14: "పద్నాలుగు", 15: "పదిహేను",
    16: "పదహారు", 17: "పదిహేడు", 18: "పద్దెనిమిది", 19: "పంతొమ్మిది", 20: "ఇరవై",
    21: "ఇరవై ఒకటి", 22: "ఇరవై రెండు", 23: "ఇరవై మూడు", 24: "ఇరవై నాలుగు", 25: "ఇరవై ఐదు",
    26: "ఇరవై ఆరు", 27: "ఇరవై ఏడు", 28: "ఇరవై ఎనిమిది", 29: "ఇరవై తొమ్మిది", 30: "ముప్పై",
    31: "ముప్పై ఒకటి", 32: "ముప్పై రెండు", 33: "ముప్పై మూడు", 34: "ముప్పై నాలుగు", 35: "ముప్పై ఐదు",
    36: "ముప్పై ఆరు", 37: "ముప్పై ఏడు", 38: "ముప్పై ఎనిమిది", 39: "ముప్పై తొమ్మిది", 40: "నలభై",
    41: "నలభై ఒకటి", 42: "నలభై రెండు", 43: "నలభై మూడు", 44: "నలభై నాలుగు", 45: "నలభై ఐదు",
    46: "నలభై ఆరు", 47: "నలభై ఏడు", 48: "నలభై ఎనిమిది", 49: "నలభై తొమ్మిది", 50: "యాభై",
    51: "యాభై ఒకటి", 52: "యాభై రెండు", 53: "యాభై మూడు", 54: "యాభై నాలుగు", 55: "యాభై ఐదు",
    56: "యాభై ఆరు", 57: "యాభై ఏడు", 58: "యాభై ఎనిమిది", 59: "యాభై తొమ్మిది", 60: "అరవై",
    65: "అరవై ఐదు", 70: "డెబ్బై", 75: "డెబ్బై ఐదు", 80: "ఎనభై", 85: "ఎనభై ఐదు",
    90: "తొంబై", 95: "తొంబై ఐదు", 100: "వంద",
}

HI_COUNT_WORDS = {
    1: "एक", 2: "दो", 3: "तीन", 4: "चार", 5: "पांच",
    6: "छह", 7: "सात", 8: "आठ", 9: "नौ", 10: "दस",
    11: "ग्यारह", 12: "बारह", 13: "तेरह", 14: "चौदह", 15: "पंद्रह",
    16: "सोलह", 17: "सत्रह", 18: "अठारह", 19: "उन्नीस", 20: "बीस",
    21: "इक्कीस", 22: "बाईस", 23: "तेईस", 24: "चौबीस", 25: "पच्चीस",
    26: "छब्बीस", 27: "सत्ताईस", 28: "अट्ठाईस", 29: "उनतीस", 30: "तीस",
    31: "इकतीस", 32: "बत्तीस", 33: "तैंतीस", 34: "चौंतीस", 35: "पैंतीस",
    36: "छत्तीस", 37: "सैंतीस", 38: "अड़तीस", 39: "उनतालीस", 40: "चालीस",
    45: "पैंतालीस", 50: "पचास", 55: "पचपन", 60: "साठ", 65: "पैंसठ",
    70: "सत्तर", 75: "पचहत्तर", 80: "अस्सी", 85: "पचासी", 90: "नब्बे",
    95: "पंचानवे", 100: "सौ",
}


def te_number_word(n: int) -> str:
    if n in TE_COUNT_WORDS:
        return TE_COUNT_WORDS[n]
    if 20 < n < 100:
        tens = (n // 10) * 10
        units = n % 10
        t_str = TE_COUNT_WORDS.get(tens, "")
        u_str = TE_COUNT_WORDS.get(units, "")
        if t_str and u_str:
            return f"{t_str} {u_str}"
    if 100 <= n < 1000:
        hundreds = n // 100
        rem = n % 100
        h_prefix = "నూట" if hundreds == 1 else f"{TE_COUNT_WORDS.get(hundreds, str(hundreds))} వందల"
        if rem == 0:
            return "వంద" if hundreds == 1 else f"{TE_COUNT_WORDS.get(hundreds, str(hundreds))} వందలు"
        return f"{h_prefix} {te_number_word(rem)}"
    return str(n)


def hi_number_word(n: int) -> str:
    if n in HI_COUNT_WORDS:
        return HI_COUNT_WORDS[n].strip()
    if 20 < n < 100:
        tens = (n // 10) * 10
        units = n % 10
        t_str = HI_COUNT_WORDS.get(tens, "")
        u_str = HI_COUNT_WORDS.get(units, "")
        if t_str and u_str:
            return f"{t_str} {u_str}"
    if 100 <= n < 1000:
        hundreds = n // 100
        rem = n % 100
        h_prefix = "एक सौ" if hundreds == 1 else f"{HI_COUNT_WORDS.get(hundreds, str(hundreds))} सौ"
        if rem == 0:
            return h_prefix
        return f"{h_prefix} {hi_number_word(rem)}"
    return str(n)


def format_day_count(days: int, language: str) -> str:
    """Format a count of days into words for the customer's language.
    Amounts stay in digits/English, while day counts are spoken in the customer's language."""
    if language == "te":
        return te_number_word(days)
    if language == "hi":
        return hi_number_word(days)
    return str(days)


def overdue_phrase(due: date, language: str) -> str:
    """The {overdue} part of the amount line (prompts.DUE_PHRASES)."""
    days = (today() - due).days
    phrases = pick(script.PROMPTS.DUE_PHRASES, language)
    kind = "overdue" if days > 1 else "overdue_one" if days == 1 else "today" if days == 0 else "upcoming"
    day_str = format_day_count(abs(days), language)
    return fill(phrases[kind], {"days": day_str})





def date_line(lines: dict, when: date, language: str) -> str:

    """A fixed line about a date, with the day, month and weekday filled in by code."""

    if language not in lines:

        language = base_language(lines)

    weekday = WEEKDAY_NAMES.get(language, WEEKDAY_NAMES["en"])[when.weekday()]

    month = MONTH_NAMES[language][when.month - 1] if language in MONTH_NAMES else f"{when:%B}"

    return fill(lines[language], {"day": when.day, "month": month, "weekday": weekday})





def parse_iso(value: str) -> date | None:

    """A complete YYYY-MM-DD date from the model, or None."""

    m = re.fullmatch(r"\s*(\d{4})-(\d{2})-(\d{2})\s*", value) if isinstance(value, str) else None

    if not m:

        return None

    try:

        return date(*(int(g) for g in m.groups()))

    except ValueError:

        return None





# Telugu and Devanagari letters: a word in these scripts starts where none of them

# comes before it, so "రోజు" is found in "ఐదు రోజుల్లో" but "డే" is not in "ఉండే"

TE, HI = r"(?<![ఀ-౿])", r"(?<![ऀ-ॿ])"

HI_END = r"(?![ऀ-ॿ])"



# Signs that the customer named a day themselves. A model once offered the due date

# and saved it after a bare "సరే", so a promise needs one of these

DATE_WORDS_RE = re.compile(

    # A day number is 1-2 digits on its own ("25కి" counts); "12345" or "₹50" doesn't

    r"(?<![\d₹$.,:])\d{1,2}(?![\d,.:])"

    # Telugu. "మే" (May) only as a whole word: "మేము" is "we". "వారం" also ends every weekday

    # "డేస్" (days) and "డేట్" (date) anywhere: "ten days" came out as "టండేస్లో"

    # "్రోజు": a number run into "రోజు" ("రెండ్రోజుల్లో", "నాల్రోజులు"), as Telangana speech has it

    r"|(?<!\S)మే(?!\S)|వారం|వారము|డేస|డేశ|డేట|్రోజు|యెల్లుండ|" + TE + r"(?:తేదీ|తారీఖ|రోజు|రేపు|ఎల్లుండి|ఈరోజు|ఇవాళ|ఈవాళ|నెల"

    r"|ఒకటి|రెండు|మూడు|నాలుగు|ఐదు|అయిదు|ఆరు|ఏడు|ఎనిమిది|తొమ్మిది|పది|పదకొండు|పన్నెండు|పదిహేను|ఇరవై|ముప్పై"

    r"|జనవరి|ఫిబ్రవరి|మార్చి|ఏప్రిల్|జూన్|జూలై|ఆగస్టు|సెప్టెంబర్|అక్టోబర్|నవంబర్|డిసెంబర్"

    # English said in Telugu mode comes out in Telugu letters ("ఐ విల్ పే ఇన్ ఫైవ్ డేస్")

    r"|వన్|టూ|త్రీ|ఫోర్|ఫైవ్|సిక్స్|సెవెన్|ఎయిట్|నైన్|టెన్|ట్వెంటీ|థర్టీ|డే|డేట్|వీక్|మంత్|టుమారో|టుడే"

    r"|మండే|ట్యూస్డే|వెడ్నెస్డే|థర్స్డే|ఫ్రైడే|సాటర్డే|సండే|ఫస్ట్|సెకండ్|థర్డ్)"

    # Hindi. Full weekday names: "शुक्र" alone is in "शुक्रिया" (thanks). No "एक"/"दो":

    # "दो" is also "give" ("कॉल कर दो"). Short words must stand alone ("नौकरी", "निकल")

    r"|" + HI + r"(?:तारीख|तारीक|दिन|परसों|हफ्त|हफ़्त|महीन|सोमवार|मंगलवार|बुधवार|गुरुवार|बृहस्पतिवार"

    r"|शुक्रवार|शनिवार|रविवार|इतवार|जनवरी|फरवरी|मार्च|अप्रैल|मई|जून|जुलाई|अगस्त|सितंबर|अक्टूबर|अक्टोबर"

    r"|नवंबर|दिसंबर|पांच|पाँच|ग्यारह|बारह|पंद्रह|बीस|पच्चीस|तीस|इकतीस|फाइव|टेन|डेज़|डेज|वीक|टुमॉरो|टुडे"

    r"|मंडे|फ्राइडे|संडे)"

    r"|" + HI + r"(?:कल|आज|तीन|चार|छह|सात|आठ|नौ|दस|डे)" + HI_END

    + r"|(?:இன்று|நாளை|நாளை மறுநாள்|நாள்|நாட்கள்|வாரம்|மாதம்|திங்கள்|செவ்வாய்|புதன்|வியாழன்|வெள்ளி|சனி|ஞாயிறு|"
    r"ಇಂದು|ನಾಳೆ|ನಾಡಿದ್ದು|ದಿನ|ದಿನಗಳು|ವಾರ|ವಾರಗಳು|ತಿಂಗಳು|ಸೋಮವಾರ|ಮಂಗಳವಾರ|ಬುಧವಾರ|ಗುರುವಾರ|ಶುಕ್ರವಾರ|ಶನಿವಾರ|ಭಾನುವಾರ)"

    # English, as whole words: "one" is not in "done" or "phone"

    + r"|\b(?:today|tomorrow|days?|weeks?|weekend|months?|dates?|monday|tuesday|wednesday|thursday|friday"

    r"|saturday|sunday|january|february|march|april|june|july|august|september|october|november|december"

    r"|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty"

    r"|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|fifteenth|twentieth|thirtieth)\b"

    r"|\b(?:in|on|by|of|till|until|before|after)\s+may\b|\bmay\s+\d",

    re.I,

)

# A number with a unit is a time or an amount, not a day: "ఐదు గంటలకు", "10 minutes",

# "5 PM", "ఐదు వేలు", "50 rupees". Removed before looking for a day

NUMBER = (

    r"(?:(?<![\d.,])\d[\d,]*(?:\.\d+)?"

    r"|\b(?:a|an|half an?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty)"

    r"|" + TE + r"(?:ఒక|ఒకటి|రెండు|మూడు|నాలుగు|ఐదు|అయిదు|ఆరు|ఏడు|ఎనిమిది|తొమ్మిది|పది|పదిహేను|ఇరవై|ముప్పై|యాభై|అర"

    r"|వన్|టూ|త్రీ|ఫోర్|ఫైవ్|సిక్స్|సెవెన్|ఎయిట్|నైన్|టెన్)"

    r"|" + HI + r"(?:एक|दो|तीन|चार|पांच|पाँच|छह|सात|आठ|नौ|दस|बीस|पचास|आधा|आधे|डेढ़))"

)

UNIT = (

    r"\s*(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|o'?clock|[ap]\.?m\b|baje|rupees?|rs\b|thousand|lakhs?|k\b|/-"

    r"|నిమిష|సెకన|గంట|మినిట్|అవర్|బజే|రూపాయ|వేల|వేయి|వెయ్యి|లక్ష"

    r"|मिनट|सेकंड|घंट|बजे|रुपए|रुपये|रुपया|हज़ार|हजार|लाख)[\wఀ-౿ऀ-ॿ]*"

)

MONEY_RE = re.compile(r"(?:₹|\brs\.?|\binr)\s*[\d,]+(?:\.\d+)?", re.I)

AMOUNT_RE = re.compile(NUMBER + UNIT, re.I)

# Signs of a callback time: "in 10 minutes", "after 5", "సాయంత్రం", "शाम को", "3 baje".

# A bare "later" is no time: it booked a callback 5 minutes later

TIME_WORDS_RE = re.compile(

    r"\d{1,2}\s*(?:minutes?|mins?|hours?|hrs?|[ap]\.?m\b|o'?clock|baje)|\b(?:at|around|by|after|before)\s+\d{1,2}\b"

    r"|\b\d{1,2}[:.]\d{2}\b|minute|\bmins?\b|hour|evening|morning|afternoon|night|today|tonight|o'?clock|\b[ap]\.?m\b"

    r"|నిమిష|గంట|అవర్|మినిట|సాయంత్రం|ఉదయం|పొద్దున|మధ్యాహ్న|మధ్యానం|రాత్రి|ఈరోజు|ఇవాళ|ఈవాళ|బజే"

    r"|मिनट|घंट|शाम|सुबह|दोपहर|रात|आज|बजे|baje",

    re.I,

)

# A clock time in the model's notes ("at 3 PM", "after 5 pm", "15:00")

CLOCK_RE = re.compile(

    r"\s*\b(?:at|after|around|by|before)?\s*\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?|hrs?|o'?clock)(?=\W|$)"

    r"|\s*\b(?:at|after)?\s*\d{1,2}:\d{2}\b",

    re.I,

)





# Days said relative to today, for a callback day the model left out ("రేపు ఐదు గంటలకు")

RELATIVE_DAYS = (

    (2, re.compile(r"(?:ఎ|యె)ల్లుండ|परसों|day after tomorrow|(?:ఆ|ా)ఫ్\S*\s*[టత]ుమారో|डे आफ्टर टुमॉरो", re.I)),

    (1, re.compile(r"రేపు|tomorrow|[టత]ుమారో|टुमॉरो|टुमारो|" + HI + "कल" + HI_END, re.I)),

    (0, re.compile(r"ఈరోజు|ఇవాళ|ఈవాళ|ఈ రోజు|" + HI + "आज" + HI_END + "|today|tonight|இன்று|ಇಂದು", re.I)),
    (2, re.compile(r"நாளை மறுநாள்|ನಾಡಿದ್ದು", re.I)),
    (1, re.compile(r"நாளை|ನಾಳೆ", re.I)),

)





# Hindi कल is both yesterday and tomorrow: with a past-tense verb ("कल कर दिया") it

# is yesterday, so it names no day ahead

HINDI_PAST_RE = re.compile(r"किया|दिया|दे दिया|था|थी|थे|गया|गई|हुआ|हो गया")





def relative_day(texts: list[str]) -> date | None:

    """Today, tomorrow or the day after, from the customer's latest words that say one."""

    for text in reversed(texts):

        if "कल" in text and HINDI_PAST_RE.search(text):

            continue

        for ahead, pattern in RELATIVE_DAYS:

            if pattern.search(text):

                return today() + timedelta(days=ahead)

    return None





# The day the customer named, worked out by the app and handed to the model, so it

# never asks "which day?" again: durations ("10 days", "టండేస్లో", "ఒక వారం", "दस दिन"),

# tomorrow, month end, "25th" / "25కి" / "25 October", weekdays

NUMBERS = {

    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,

    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,

    "ఒక": 1, "ఒకటి": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5, "అయిదు": 5, "ఆరు": 6, "ఏడు": 7,

    "ఎనిమిది": 8, "తొమ్మిది": 9, "పది": 10, "పద్నాలుగు": 14, "పదిహేను": 15, "ఇరవై": 20, "ముప్పై": 30, "నలభై": 40, "యాభై": 50,

    # English said in Telugu mode, in Telugu letters as the transcriber writes it ("టండేస్")

    "వన్": 1, "టూ": 2, "త్రీ": 3, "ఫోర్": 4, "ఫైవ్": 5, "సిక్స్": 6, "సెవెన్": 7, "ఎయిట్": 8, "నైన్": 9,

    "టెన్": 10, "టన్": 10, "టం": 10, "టెం": 10, "ఫిఫ్టీన్": 15, "ట్వెంటీ": 20,

    # Run into the unit in Telangana speech: "రెండ్రోజుల్లో", "మూడ్రోజులు", "నాల్రోజులు"

    "రెండ్": 2, "మూడ్": 3, "నాల్": 4, "నాలుగ్": 4, "ఆర్": 6, "ఏడ్": 7, "పద్": 10,

    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "छै": 6, "सात": 7, "आठ": 8, "नौ": 9,

    "दस": 10, "चौदह": 14, "पंद्रह": 15, "बीस": 20, "तीस": 30, "चालीस": 40, "पचास": 50, "फाइव": 5, "टेन": 10,
    "ஒன்று": 1, "ஒரு": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5, "ஆறு": 6, "ஏழு": 7, "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10, "பதினான்கு": 14, "நாற்பது": 40,
    "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5, "ಆರು": 6, "ಏಳು": 7, "ಎಂಟು": 8, "ಒಂಬತ್ತು": 9, "ಹತ್ತು": 10, "ಹದಿನಾಲ್ಕು": 14, "ಪದ್ನಾಲ್ಕು": 14, "ನಲವತ್ತು": 40,

}

NOT_IN_A_WORD = r"(?<![\w\u0C00-\u0C7F\u0900-\u097F])"

DURATION_RE = re.compile(

NOT_IN_A_WORD + r"(?P<n>\d{1,2}|" + "|".join(sorted(NUMBERS, key=len, reverse=True)) + r")\s*(?:"

    r"(?P<day>days?|రోజు|డేస|డేశ|డే|డె(?=స|ర్|లో)|दिन|डेज़|डेज|डे|நாள்|நாட்கள்|ದಿನ|ದಿನಗಳು)|(?P<week>weeks?|వారం|వారాల|వీక్|हफ्त|हफ़्त|सप्ताह|वीक|வாரம்|வாரங்கள்|ವಾರ|ವಾರಗಳು)"

    r"|(?P<month>months?|నెల|మంత్|महीन|मंथ|மாதம்|மாதங்கள்|ತಿಂಗಳು|ತಿಂಗಳ|ಮಾಸ))",

    re.I,

)

# "A week" with no number: "వారం రోజుల్లో", "వారం లోపల", "हफ्ते भर में". A weekday

# ("సోమవారంలో") has a letter before "వారం"; "వచ్చే వారం" (next week) names no day

WEEK_ALONE_RE = re.compile(

    TE + r"వారం\s*(?:రోజు|లోప|లో(?![ఀ-౿])|టైం|టైమ్)|" + HI + r"हफ़?्त[ेा]\s*भर",

)

NOT_A_SPAN = {"వచ్చే", "ఈ", "ఆ", "పోయిన", "ఇదే", "ఏ", "నెక్స్ట్", "లాస్ట్", "अगले", "पिछले", "इस", "उस"}

MONTH_END_RE = re.compile(

    r"month[\s-]*end|end of (?:the |this )?month|మంత్\s*ఎండ్|మంతెండ|మంతెందు|నెలాఖర|నెల\s*చివర"

    r"|మ[ంన]\S{0,3}\s*(?:\S?ెండ|ఎండ)(?:ి?\s*కి|్)"

    r"|महीने\s*(?:के|का)\s*(?:आखिर|अंत|लास्ट)|मंथ\s*एंड",

    re.I,

)

MONTH_WORDS = {name: i + 1 for names in (MONTH_NAMES["te"], MONTH_NAMES["hi"], MONTH_NAMES["ta"], MONTH_NAMES["kn"]) for i, name in enumerate(names)}

MONTH_WORDS.update({f"{date(2000, i, 1):%B}".lower(): i for i in range(1, 13)})

_MONTHS = "|".join(sorted(MONTH_WORDS, key=len, reverse=True))

EXPLICIT_ISO_RE = re.compile(r"(?<!\d)(?P<y>20\d{2})-(?P<m>\d{2})-(?P<d>\d{2})(?!\d)")
EXPLICIT_TEXT_DATE_RE = re.compile(
    r"(?<!\d)(?P<d1>\d{1,2})(?:st|nd|rd|th)?\s+(?P<m1>" + _MONTHS + r")\s*,?\s*(?P<y1>20\d{2})(?!\d)"
    r"|(?P<m2>" + _MONTHS + r")\s+(?P<d2>\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(?P<y2>20\d{2})(?!\d)",
    re.I,
)

DAY_OF_MONTH_RE = re.compile(

    r"(?<![\d₹$.,])(?P<d>[0-3]?\d)\s*(?:(?:st|nd|rd|th|వ)?\s*(?:of\s+)?(?P<m>" + _MONTHS + r")|st|nd|rd|th|వ\s*తేదీ|వ\s*తారీఖ|తేదీ|తారీఖ"

    r"|కల్లా|కి|तारीख|तारीक|tarikh|को)(?![a-z])"

    r"|(?P<m2>" + _MONTHS + r")\s*(?P<d2>[0-3]?\d)(?![\d,.:])",

    re.I,

)

WEEKDAY_WORDS = [  # Monday first; English, Telugu, English in Telugu letters, Hindi

    ("monday", "సోమవార", "మండే", "सोमवार", "मंडे"), ("tuesday", "మంగళవార", "ట్యూస్డే", "मंगलवार"),

    ("wednesday", "బుధవార", "వెడ్నెస్డే", "बुधवार"), ("thursday", "గురువార", "థర్స్డే", "गुरुवार", "बृहस्पतिवार"),

    ("friday", "శుక్రవార", "ఫ్రైడే", "शुक्रवार", "फ्राइडे"), ("saturday", "శనివార", "సాటర్డే", "शनिवार"),

    ("sunday", "ఆదివార", "సండే", "रविवार", "इतवार", "संडे"),

]

# Clauses: in "ఇప్పుడు కుదరదండి, ఐదు రోజుల్లో" the no and the day are apart

CLAUSE_RE = re.compile(r",(?!(?:\s*\d{4}\b))|[.;!?।]|\s(?:but|కానీ|लेकिन)\s", re.I)





def _add_months(day: date, months: int) -> date:

    month = day.month - 1 + months

    year, month = day.year + month // 12, month % 12 + 1

    return date(year, month, min(day.day, _month_end(date(year, month, 1)).day))





def _month_end(day: date) -> date:

    return date(day.year + day.month // 12, day.month % 12 + 1, 1) - timedelta(days=1)





def _day_of_month(d: int, month: int | None, start: date) -> date | None:

    """The next d-th (of `month`, if given) from `start` on."""

    for ahead in range(13):

        first = _add_months(start.replace(day=1), ahead)

        if month and first.month != month:

            continue

        if d > _month_end(first).day:

            continue

        if (day := first.replace(day=d)) >= start:

            return day

    return None





PAST_DATE_RE = re.compile(
    r"\b(?:ago|yesterday|last\s+(?:week|month|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|paid|already\s+paid|was\s+paid|had\s+paid)\b|"
    r"చెల్లించా|చెల్లించాను|కట్టేశా|కట్టాను|ఇచ్చేశా|ఇచ్చాను|నిన్న|"
    r"किया|दिया|दे दिया|था|थी|थे|गया|गई|हुआ|हो गया|कल\s+कर दिया|நேற்று|செலுத்திவிட்டேன்|ನಿನ್ನೆ|ಪಾವತಿಸಿದೆ",
    re.I,
)
NEGATED_DATE_RE = re.compile(r"(?:\bnot\s+|\bno\s+|\bnever\s+|కాదు\s*|వద్దు\s*|कभी नहीं\s*|नहीं\s*|வேண்டாம்\s*|ಇಲ್ಲ\s*)$", re.I)
NEXT_WEEK_RE = re.compile(r"\bnext\s+|వచ్చే\s*|अगले\s*|அடுத்த\s*|ಮುಂದಿನ\s*", re.I)


def spoken_date(text: str, refused=None, *, reference_date: date | None = None) -> tuple[date, str] | None:
    """Resolve a date from one utterance; durations use calendar days and IST date context.

    The caller must pass only the current utterance, never the full conversation history.
    """
    start = _as_date(reference_date) or today()
    found: list[tuple[int, date, str]] = []
    offset = 0
    for clause in CLAUSE_RE.split(text or ""):
        clause_start = offset
        offset += len(clause) + 1
        raw = clause.strip()
        if not raw or (refused and refused(raw)):
            continue
        # Ignore historical-payment clauses; a later explicit future clause still wins.
        if PAST_DATE_RE.search(raw) and not re.search(r"\b(?:will|going to|pay|promise|చెల్లిస్తా|కడతా|करूँगा|करूंगा|भरूँगा|भरूंगा)\b", raw, re.I):
            continue
        clean = MONEY_RE.sub(" ", raw)
        clean_for_dates = AMOUNT_RE.sub(" ", clean)
        for pattern in (EXPLICIT_ISO_RE, EXPLICIT_TEXT_DATE_RE):
            for m in pattern.finditer(clean):
                try:
                    if "y" in m.groupdict() and m.group("y"):
                        exact = date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
                    else:
                        day_value = int(m.group("d1") or m.group("d2"))
                        month_name = (m.group("m1") or m.group("m2")).lower()
                        year_value = int(m.group("y1") or m.group("y2"))
                        exact = date(year_value, MONTH_WORDS[month_name], day_value)
                except (ValueError, KeyError, TypeError):
                    continue
                if exact >= start:
                    found.append((clause_start + m.start(), exact, m.group(0)))
        for m in DURATION_RE.finditer(clean):
            tail = clean[m.end():m.end() + 20]
            if re.match(r"\s*(?:ago|back|క్రితం|पहले|முன்பு|ಹಿಂದೆ)", tail, re.I):
                continue
            n = int(m["n"]) if m["n"].isdigit() else NUMBERS.get(m["n"].lower())
            if n is None:
                continue
            day = start + timedelta(days=n) if m["day"] else start + timedelta(weeks=n) if m["week"] else _add_months(start, n)
            found.append((clause_start + m.start(), day, m.group(0)))
        for m in WEEK_ALONE_RE.finditer(clean):
            before = clean[:m.start()].split()
            if not before or before[-1] not in NOT_A_SPAN:
                found.append((clause_start + m.start(), start + timedelta(weeks=1), m.group(0)))
        for m in MONTH_END_RE.finditer(clean):
            found.append((clause_start + m.start(), _month_end(start), m.group(0)))
        for m in DAY_OF_MONTH_RE.finditer(clean_for_dates):
            d = int(m["d"] or m["d2"])
            month = MONTH_WORDS.get((m["m"] or m["m2"] or "").lower())
            if 1 <= d <= 31 and (day := _day_of_month(d, month, start)):
                found.append((clause_start + m.start(), day, m.group(0)))
        lowered = clean.lower()
        for i, names in enumerate(WEEKDAY_WORDS):
            for name in names:
                at = lowered.find(name.lower())
                if at < 0:
                    continue
                prefix = lowered[max(0, at - 24):at]
                if NEGATED_DATE_RE.search(prefix):
                    continue
                delta = (i - start.weekday()) % 7
                if NEXT_WEEK_RE.search(prefix):
                    delta = delta + 7 if delta else 7
                elif delta == 0 and not re.search(
                    r"\b(?:today|this day)\b|ఈరోజు|ఇవాళ|ఈవాళ|ఈ రోజు|आज|இன்று|ಇಂದು", clean, re.I
                ):
                    # A bare weekday that is today is ambiguous: today or next week.
                    continue
                found.append((clause_start + at, start + timedelta(days=delta), name))
        if not ("कल" in clean and HINDI_PAST_RE.search(clean)):
            for ahead, pattern in RELATIVE_DAYS:
                m = pattern.search(clean)
                if m:
                    found.append((clause_start + m.start(), start + timedelta(days=ahead), m.group(0)))
                    break
    if not found:
        return None
    # If the utterance contains incompatible dates, only a clear correction may make
    # the last date authoritative. Never silently choose between "Friday or Monday".
    distinct_dates = {item[1] for item in found}
    correction_cue = re.search(
        r"\b(?:but|actually|instead|rather|sorry|no|not)\b|కానీ|కాదు|వద్దు|"
        r"लेकिन|नहीं|அல்ல|இல்லை|ಆದರೆ|ಬೇಡ",
        text or "", re.I,
    )
    if len(distinct_dates) > 1 and not correction_cue:
        return None
    _, resolved, words = max(found, key=lambda item: item[0])
    return resolved, words.strip()



def _latest_text(texts: list[str] | str) -> str:
    if isinstance(texts, str):
        return texts
    for text in reversed(texts or []):
        if isinstance(text, str) and text.strip():
            return text
    return ""


def said_a_date(texts: list[str] | str) -> bool:
    text = AMOUNT_RE.sub(" ", MONEY_RE.sub(" ", _latest_text(texts)))
    return bool(DATE_WORDS_RE.search(text))


def said_a_time(texts: list[str] | str) -> bool:
    return bool(TIME_WORDS_RE.search(MONEY_RE.sub(" ", _latest_text(texts))))



# The exact moment a callback was asked for, from the words of whoever answered: "in 30

# minutes", "ఒక గంట తర్వాత", "అరగంటలో", "సాయంత్రం ఐదున్నరకి", "4 PM", "शाम 5 बजे". The model's

# English notes carried only clock times, so "after one hour" was booked 5 minutes later

CLOCK_HOURS = {

    "ఒంటి": 1, "ఒకటి": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5, "అయిదు": 5, "ఆరు": 6, "ఏడు": 7,

    "ఎనిమిది": 8, "తొమ్మిది": 9, "పది": 10, "పదకొండు": 11, "పన్నెండు": 12,

    "వన్": 1, "టూ": 2, "త్రీ": 3, "ఫోర్": 4, "ఫైవ్": 5, "సిక్స్": 6, "సెవెన్": 7, "ఎయిట్": 8, "నైన్": 9, "టెన్": 10,

    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,

    "ग्यारह": 11, "बारह": 12,

    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,

    "eleven": 11, "twelve": 12,

}

# "ఐదున్నర" 5:30 and "ఐదింటికి" at five: the hour runs into the word

TE_HALF_PAST = {"ఒకటిన్నర": 1, "రెండున్నర": 2, "మూడున్నర": 3, "నాలుగున్నర": 4, "ఐదున్నర": 5, "అయిదున్నర": 5,

                "ఆరున్నర": 6, "ఏడున్నర": 7, "ఎనిమిదిన్నర": 8, "తొమ్మిదిన్నర": 9, "పదిన్నర": 10,

                "పదకొండున్నర": 11, "పన్నెండున్నర": 12}

TE_AT_HOUR = {"రెండింటి": 2, "మూడింటి": 3, "నాలుగింటి": 4, "ఐదింటి": 5, "అయిదింటి": 5, "ఆరింటి": 6, "ఏడింటి": 7,

              "ఎనిమిదింటి": 8, "తొమ్మిదింటి": 9, "పదింటి": 10, "పదకొండింటి": 11, "పన్నెండింటి": 12}

_WORDS = lambda d: "|".join(sorted(d, key=len, reverse=True))  # noqa: E731

_N = r"(?P<n>\d{1,3}|" + _WORDS(NUMBERS) + ")"


MINUTES_LATER_RE = re.compile(NOT_IN_A_WORD + _N + r"\s*(?:minutes?|mins?|నిమిష|నిముష|మినిట|मिनट)", re.I)

HALF_HOUR_RE = re.compile(r"అర\s*గంట|హాఫ్\s*(?:ఏన్\s*|ఎన్\s*)?అవర్|half\s+(?:an\s+)?hour|आध[ाे]\s*घंट", re.I)

HOUR_AND_HALF_RE = re.compile(r"గంటన్నర|ఒకటిన్నర\s*గంట|an?\s+hour\s+and\s+a\s+half|one\s+and\s+a\s+half\s+hours?|डेढ़\s*घंट", re.I)

HOURS_LATER_RE = re.compile(

    r"(?:\b(?:in|after)\s+(?:an?|" + _N + r")\s*hours?\b|" + NOT_IN_A_WORD + _N.replace("<n>", "<n2>")

    + r"\s*hours?\s*(?:later|after|from now)\b)"

    r"|(?:" + NOT_IN_A_WORD + r"(?P<n3>ఒక|రెండు|మూడు|వన్|టూ|త్రీ|\d)\s*)?గంట(?:ల|లు)?\s*(?:తర్వాత|తరువాత|అయ్యాక|ఆగి|లో(?![ఀ-౿]))"

    # "ఒక వన్ అవర్ లో", "టూ అవర్స్ తర్వాత": English said in Telugu letters

    r"|(?:" + NOT_IN_A_WORD + r"(?:ఒక\s*)?(?P<n5>వన్|టూ|త్రీ|ఫోర్|ఫైవ్|ఒక|రెండు|మూడు|\d)\s*)?అవర్(?:స్|్స్)?\s*(?:తర్వాత|తరువాత|అయ్యాక|ఆగి|లో|లోపల)?"

    r"|(?:" + NOT_IN_A_WORD + r"(?P<n4>एक|दो|तीन|\d)\s*)?घंट[ेा]\s*(?:बाद|में)",

    re.I,

)

# Full clock times are looked for first: "call at 5:30 PM" matched "at 5" and lost the 30 minutes

FULL_CLOCK_RE = re.compile(

    r"\b(?P<h1>\d{1,2})(?::(?P<m1>\d{2}))?\s*(?P<ap>[ap])\.?\s*m\b"                       # 5 pm, 5:30 PM

    r"|\b(?P<h2>\d{1,2}):(?P<m2>\d{2})\b",                                              # 17:00, 5:30

    re.I,

)

CLOCK_TIME_RE = re.compile(

    r"half\s+past\s+(?P<h3>\d{1,2}|" + _WORDS(CLOCK_HOURS) + r")"                      # half past five

    r"|(?P<h4>\d{1,2}|" + _WORDS(CLOCK_HOURS) + r")\s*o'?\s*clock"                       # five o'clock

    r"|\b(?:at|after|around|by)\s+(?P<h5>\d{1,2}|" + _WORDS(CLOCK_HOURS) + r")\b"         # at 5

    r"|(?P<half>" + _WORDS(TE_HALF_PAST) + r")"                                          # ఐదున్నర

    r"|(?P<inti>" + _WORDS(TE_AT_HOUR) + r")"                                            # ఐదింటికి

    r"|" + NOT_IN_A_WORD + r"(?P<h6>\d{1,2}|" + _WORDS(CLOCK_HOURS) + r")\s*గంట(?:ల|ి|)\s*(?:కు|కి|కల్లా|తర్వాత|తరువాత)"  # గంటికి

    r"|साढ़े\s*(?P<h7>\d{1,2}|" + _WORDS(CLOCK_HOURS) + r")"                              # साढ़े पांच

    r"|(?P<h8>\d{1,2}|" + _WORDS(CLOCK_HOURS) + r")\s*बजे"                               # 5 बजे

    r"|(?P<h9>\d{1,2})\s*(?:కు|కి)(?![ఀ-౿])",                                           # 5 కి

    re.I,

)

MORNING_RE = re.compile(r"ఉదయం|పొద్దున|మార్నింగ్|morning|सुबह|मॉर्निंग", re.I)

AFTERNOON_RE = re.compile(r"మధ్యాహ్న|మధ్యానం|ఆఫ్టర్నూన్|afternoon|दोपहर", re.I)

EVENING_RE = re.compile(r"సాయంత్రం|సాయంకాలం|ఈవెనింగ్|evening|शाम", re.I)

NIGHT_RE = re.compile(r"రాత్రి|నైట్|\bnight|tonight|रात", re.I)





def _hour_of_day(hour: int, text: str, ampm: str | None = None) -> int:

    """A spoken hour on the 24-hour clock: "సాయంత్రం 5" is 17; without am/pm or a part

    of the day, 8-11 is the morning and 12-7 the afternoon or evening, as calls run."""

    if hour >= 13:

        return hour

    if ampm:

        return hour % 12 + (12 if ampm.lower() == "p" else 0)

    if MORNING_RE.search(text):

        return hour % 12

    if AFTERNOON_RE.search(text) or EVENING_RE.search(text) or NIGHT_RE.search(text):

        return hour if hour == 12 else hour + 12

    return hour if 8 <= hour <= 12 else hour + 12





def _number(word: str | None, table: dict) -> int | None:

    if not word:

        return None

    return int(word) if word.isdigit() else table.get(word.lower())





def callback_time(texts: list[str] | str, day: date | None = None, now: datetime | None = None) -> datetime | None:
    """Resolve a callback datetime from the latest utterance. Vague dayparts need clarification."""
    now = now or datetime.now(IST)
    if now.tzinfo is None:
        # Naive values are interpreted in the application's configured timezone.
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)
    text = MONEY_RE.sub(" ", _latest_text(texts))
    if not text.strip():
        return None
    if m := MINUTES_LATER_RE.search(text):
        n = _number(m.group("n"), {**NUMBERS, **CLOCK_HOURS})
        if n is not None and 1 <= n <= 240:
            return now + timedelta(minutes=n)
    if HOUR_AND_HALF_RE.search(text):
        return now + timedelta(minutes=90)
    if HALF_HOUR_RE.search(text):
        return now + timedelta(minutes=30)
    if m := HOURS_LATER_RE.search(text):
        word = next((g for g in (m.group("n"), m.group("n2"), m.group("n3"), m.group("n4"), m.group("n5")) if g), None)
        hours = _number(word, {**NUMBERS, **CLOCK_HOURS}) if word else 1
        if hours is not None and 1 <= hours <= 12:
            return now + timedelta(hours=hours)
    hour, minute, explicit_clock = None, 0, False
    if m := FULL_CLOCK_RE.search(text):
        h = int(m.group("h1") or m.group("h2"))
        minute = int(m.group("m1") or m.group("m2") or 0)
        if h <= 23 and minute <= 59:
            hour = _hour_of_day(h, text, m.group("ap"))
            explicit_clock = True
    elif m := CLOCK_TIME_RE.search(text):
        explicit_clock = True
        if m.group("half"):
            hour, minute = _hour_of_day(TE_HALF_PAST[m.group("half")], text), 30
        elif m.group("inti"):
            hour = _hour_of_day(TE_AT_HOUR[m.group("inti")], text)
        elif m.group("h7"):
            hour, minute = _hour_of_day(_number(m.group("h7"), CLOCK_HOURS) or 0, text), 30
        else:
            raw = next((m.group(k) for k in ("h3", "h4", "h5", "h6", "h8", "h9") if m.group(k)), None)
            h = _number(raw, CLOCK_HOURS)
            if h is not None and 0 <= h <= 23:
                hour = _hour_of_day(h, text)
                minute = 30 if m.group("h3") else 0
    if not explicit_clock or hour is None or not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    explicit_day = day
    if explicit_day is None:
        parsed = spoken_date(text, reference_date=now.date())
        if parsed:
            explicit_day = parsed[0]
    on = explicit_day or now.date()
    at = datetime.combine(on, datetime.min.time(), tzinfo=now.tzinfo).replace(hour=hour, minute=minute)
    # Never silently roll a past clock time into tomorrow. Without an explicit future
    # date, that would be an unconfirmed scheduling decision.
    if at <= now:
        return None
    return at


# ---------------------------------------------------------------------------
# Application integration adapters
# ---------------------------------------------------------------------------
# The production API schemas are application-specific and are intentionally injected.
# These functions enforce validation before making one API call; they never retry an
# uncertain write because a retry can duplicate a payment promise or reschedule action.


def _api_succeeded(result: Any) -> bool:
    """Conservatively recognize explicit success in common adapter response shapes."""
    if result is True:
        return True
    if result is False or result is None:
        return False
    if isinstance(result, dict):
        if result.get("success") is True or result.get("ok") is True:
            return True
        status = str(result.get("status", "")).strip().lower()
        return status in {"success", "succeeded", "scheduled", "rescheduled", "saved", "ok"}
    status_code = getattr(result, "status_code", None)
    if isinstance(status_code, int):
        return 200 <= status_code < 300
    return False


# These are intentionally narrow: generic acknowledgement words alone are not enough
# to convert a collection conversation into a confirmed payment promise.
_AFFIRMATIVE_CONFIRMATION_RE = re.compile(
    r"^(?:yes|yes,? correct|correct|confirmed|i confirm|అవును|అవునండి|ఖచ్చితంగా|"
    r"అదే తేదీ|ఆ తేదీకే|ఆ తేదీకి చెల్లిస్తాను|हाँ|जी हाँ|बिल्कुल|சரி,? உறுதி|ஆம்|ಹೌದು|ಖಚಿತವಾಗಿ)[.! ]*$",
    re.I,
)
_NON_COMMITMENT_RE = re.compile(
    r"\b(?:maybe|perhaps|try|trying|if possible|hopefully|not sure|can't confirm|cannot confirm|"
    r"already paid|paid already|payment done|will check|check and tell|later|callback|call me|"
    r"won't pay|will not pay|refuse|dispute|wrong invoice)\b|"
    r"ప్రయత్నిస్తా|చూసి చెప్తా|తర్వాత చెప్తా|ఇప్పుడే చెప్పలేను|చెల్లించలేను|ఇప్పటికే కట్టా|"
    r"बाद में बताऊँगा|कोशिश करूँगा|पहले ही भुगतान|भुगतान कर दिया|नहीं दूँगा|"
    r"ஏற்கனவே செலுத்த|பிறகு சொல்கிறேன்|முயற்சி செய்கிறேன்|கட்ட முடியாது|"
    r"ಈಗಾಗಲೇ ಪಾವತ|ನಂತರ ಹೇಳುತ್ತೇನೆ|ಪ್ರಯತ್ನಿಸುತ್ತೇನೆ|ಪಾವತಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ",
    re.I,
)


def _decimal_amount(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    # Monetary inputs are stored to paise precision; never silently round customer commitments.
    if amount != amount.quantize(Decimal("0.01")):
        return None
    return amount.quantize(Decimal("0.01"))


def save_validated_ptp(
    *,
    call: dict,
    payment_date_expression: str,
    confirmation_utterance: str,
    readback_date: str | date,
    readback_confirmed: bool,
    explicit_payment_commitment: bool = False,
    payment_amount: Any,
    save_ptp_api: Callable[[dict], Any],
    allow_partial_payment: bool = False,
    is_success: Callable[[Any], bool] = _api_succeeded,
    as_of: date | None = None,
) -> dict:
    """Validate a PTP and persist it only after explicit confirmation of a date read-back.

    Required flow:
      1. Capture the customer's original payment-date expression.
      2. Resolve and read back the exact normalized date.
      3. Pass the customer's explicit confirmation and that exact read-back date here.
      4. Persist through the existing API adapter only after all guards pass.

    ``readback_confirmed`` must be set by the conversation state machine only after the
    confirmation follows the exact date read-back; it must not be inferred from a generic
    LLM label. ``save_ptp_api`` maps this normalized payload to the real application API.
    """
    if not isinstance(call, dict):
        return {"ok": False, "code": "INVALID_CALL", "message": "Call context is invalid."}
    if not callable(save_ptp_api):
        return {"ok": False, "code": "INVALID_ADAPTER", "message": "PTP save adapter is unavailable."}
    for field in ("call_id", "customer_id", "invoice_no"):
        value = call.get(field)
        if value is None or not str(value).strip():
            return {"ok": False, "code": f"MISSING_{field.upper()}", "message": f"Required {field} is missing."}

    utterance = (confirmation_utterance or "").strip()
    if not explicit_payment_commitment:
        return {"ok": False, "code": "NO_EXPLICIT_COMMITMENT", "message": "An explicit payment commitment is required."}
    if not readback_confirmed or not _AFFIRMATIVE_CONFIRMATION_RE.fullmatch(utterance):
        return {"ok": False, "code": "READBACK_NOT_CONFIRMED", "message": "The exact payment date has not been explicitly confirmed."}
    if _NON_COMMITMENT_RE.search(utterance) or _NON_COMMITMENT_RE.search(payment_date_expression or ""):
        return {"ok": False, "code": "NON_COMMITMENT_RESPONSE", "message": "The response does not confirm a payment commitment."}

    parsed = spoken_date(payment_date_expression or "", reference_date=as_of)
    if parsed is None:
        return {"ok": False, "code": "DATE_UNCLEAR", "message": "A clear payment date is required."}
    payment_date = validate_promise_date(call, parsed[0], as_of=as_of)
    normalized_readback = _as_date(readback_date)
    if payment_date is None:
        return {"ok": False, "code": "DATE_OUT_OF_POLICY", "message": "Payment date is invalid or outside the permitted PTP window."}
    if normalized_readback is None or normalized_readback != payment_date:
        return {"ok": False, "code": "READBACK_DATE_MISMATCH", "message": "The confirmed date does not match the parsed payment date."}

    amount = _decimal_amount(payment_amount)
    if amount is None:
        return {"ok": False, "code": "INVALID_AMOUNT", "message": "A valid positive payment amount is required."}
    balance = _decimal_amount(call.get("balance_due"))
    if balance is None:
        return {"ok": False, "code": "MISSING_VERIFIED_BALANCE", "message": "A verified outstanding balance is required."}
    if amount > balance:
        return {"ok": False, "code": "AMOUNT_EXCEEDS_BALANCE", "message": "The committed amount exceeds the verified outstanding balance."}
    if amount < balance and not allow_partial_payment:
        return {"ok": False, "code": "PARTIAL_PAYMENT_NOT_AUTHORIZED", "message": "Partial payment is not authorized for this account."}

    payload = {
        "call_id": str(call["call_id"]),
        "customer_id": str(call["customer_id"]),
        "invoice_no": str(call["invoice_no"]),
        "payment_amount": str(amount),
        "payment_date": payment_date.isoformat(),
        "date_expression": parsed[1],
    }
    try:
        result = save_ptp_api(payload)
        succeeded = bool(is_success(result))
    except Exception as exc:
        # Avoid logging exception text, which can contain request payloads or customer data.
        logger.error("RIA PTP persistence adapter failed (%s)", type(exc).__name__)
        return {"ok": False, "code": "SAVE_FAILED", "message": "Payment commitment could not be saved."}
    if not succeeded:
        return {"ok": False, "code": "SAVE_NOT_CONFIRMED", "message": "Payment commitment save was not confirmed."}
    return {
        "ok": True,
        "code": "PTP_SAVED",
        "payment_date": payment_date.isoformat(),
        "payment_amount": str(amount),
    }


def reschedule_existing_callback(
    *,
    call_id: str,
    latest_customer_utterance: str,
    reschedule_api: Callable[[dict], Any],
    now: datetime | None = None,
    is_success: Callable[[Any], bool] = _api_succeeded,
    minimum_notice_minutes: int = 0,
    maximum_days_ahead: int = 30,
) -> dict:
    """Reschedule the existing call only after resolving a valid future local datetime.

    No create-call API is used. The adapter must update the same call ID. No blind retries
    are made after an exception or an uncertain response to avoid duplicate side effects.
    """
    if not isinstance(call_id, str) or not call_id.strip():
        return {"ok": False, "code": "MISSING_CALL_ID", "message": "Existing call ID is required."}
    if not callable(reschedule_api):
        return {"ok": False, "code": "INVALID_ADAPTER", "message": "Callback rescheduling adapter is unavailable."}
    if isinstance(minimum_notice_minutes, bool) or not isinstance(minimum_notice_minutes, int) or minimum_notice_minutes < 0:
        return {"ok": False, "code": "INVALID_SCHEDULING_POLICY", "message": "Callback scheduling policy is invalid."}
    if isinstance(maximum_days_ahead, bool) or not isinstance(maximum_days_ahead, int) or maximum_days_ahead < 1 or maximum_days_ahead > 365:
        return {"ok": False, "code": "INVALID_SCHEDULING_POLICY", "message": "Callback scheduling policy is invalid."}

    now = now or datetime.now(IST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=IST)
    else:
        now = now.astimezone(IST)
    when = callback_time(latest_customer_utterance, now=now)
    if when is None:
        return {"ok": False, "code": "CALLBACK_TIME_UNCLEAR", "message": "A valid future callback date and time are required."}
    when = when.astimezone(IST)
    if when < now + timedelta(minutes=minimum_notice_minutes):
        return {"ok": False, "code": "CALLBACK_TOO_SOON", "message": "The requested callback does not meet the minimum notice period."}
    if when > now + timedelta(days=maximum_days_ahead):
        return {"ok": False, "code": "CALLBACK_TOO_FAR", "message": "The requested callback is beyond the permitted scheduling window."}

    payload = {"call_id": call_id.strip(), "scheduled_at": when.isoformat()}
    try:
        result = reschedule_api(payload)
        succeeded = bool(is_success(result))
    except Exception as exc:
        logger.error("RIA callback rescheduling adapter failed (%s)", type(exc).__name__)
        return {"ok": False, "code": "RESCHEDULE_FAILED", "message": "Callback rescheduling could not be confirmed."}
    if not succeeded:
        return {"ok": False, "code": "RESCHEDULE_NOT_CONFIRMED", "message": "Callback rescheduling was not confirmed."}
    return {"ok": True, "code": "CALLBACK_RESCHEDULED", "call_id": call_id.strip(), "scheduled_at": when.isoformat()}

