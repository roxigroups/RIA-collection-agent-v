"""The conversation language.

RIA speaks and transcribes Telugu, Hindi and English: Smallest Pulse is accurate
in each when told the language, while its auto-detect wrote Telugu in Hindi
letters. So the transcriber follows the conversation language and changes with it.

A change happens when the customer asks for a language by name (checked here, in
any script) or when the model hears them speaking another one (its
switch_language tool). With Telugu transcription, Hindi or English speech comes
out in Telugu letters ("ప్లీస్ స్పీక్ ఇన్ ఇంగ్లిష్"), which the model still reads.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

NAMES = {"te": "Telugu", "hi": "Hindi", "en": "English", "kn": "Kannada"}

# Language names a customer might use ("speak in Hindi", "తెలుగులో మాట్లాడండి",
# "हिंदी में बोलो"), in Latin, Telugu, Devanagari and Kannada letters (Pulse in
# Telugu mode sometimes writes English in Kannada letters)
REQUEST_NAMES = {
    "en": ("english", "ఇంగ్లీష్", "ఇంగ్లిష్", "इंग्लिश", "अंग्रेज़ी", "अंग्रेजी", "ಇಂಗ್ಲಿಷ್"),
    "hi": ("hindi", "हिंदी", "हिन्दी", "హిందీ", "హింది", "ಹಿಂದಿ"),
    "te": ("telugu", "తెలుగు", "तेलुगु", "तेलुगू", "ತೆಲುಗು"),
    "kn": ("kannada", "ಕನ್ನಡ", "కన్నడ", "कन्नड़", "ಕನ್ನಡ್"),
}
# A "not" next to a language name means the customer does NOT want it: "Please
# speak in English. I don't understand Telugu." switched to English and straight
# back. English puts the "not" before the name, Telugu and Hindi after it
NOT_BEFORE_RE = re.compile(r"^(?:don'?t|dont|doesn'?t|can'?t|cant|cannot|not|no|never|without)$", re.I)
NOT_AFTER_RE = re.compile(
    r"^(?:రాదు|రావు|తెలియదు|తెలీదు|అర్థం|అర్ధం|వద్దు|కాదు|రాదండి|వద్దండి)|^(?:नहीं|नही|मत|ना|नहि)|^(?:ಗೊತ್ತಿಲ್ಲ|ಬರಲ್ಲ|ಬೇಡ|ಅರ್ಥವಾಗಲ್ಲ|ಅರ್ಥವಿಲ್ಲ|ಅಲ್ಲ)$"
)
NOT_BEFORE, NOT_AFTER = 2, 3


# Telugu and Devanagari letters by sound, to compare a name said in any script with the
# name on the call sheet ("నేను వసీం", "वसीम बोल रहा हूँ" -> WASEEM)
CONSONANTS = dict(zip(
    "కఖగఘఙచఛజఝఞటఠడఢణతథదధనపఫబభమయరఱలళవశషసహ"
    "कखगघङचछजझञटठडढणतथदधनपफबभमयरऱलळवशषसह"
    "ಕಖಗಘಙಚಛಜಝಞಟಠಡಢಣತಥದಧನಪಫಬಭಮಯರಱಲಳವಶಷಸಹ",
    "k kh g gh n ch ch j jh n t th d dh n t th d dh n p f b bh m y r r l l v sh sh s h ".split() * 3,
))
VOWELS = dict(zip(
    "అఆఇఈఉఊఎఏఐఒఓఔअआइईउऊएऐओऔಅಆಇಈಉಊಎಏಐಒಓಔ",
    "a aa i ee u oo e e ai o o au a aa i ee u oo e ai o au a aa i ee u oo e e ai o o au".split(),
))
SIGNS = dict(zip(
    "ాిీుూెేైొోౌంః్ािीुूेैोौंःँ್ಾಿೀುೂೆೇೈೊೋೌಂಃ್",
    "aa i ee u oo e e ai o o au m h _ aa i ee u oo e ai o au m h n _ aa i ee u oo e e ai o o au m h _".split(),
))


def romanize(text: str) -> str:
    """Telugu and Devanagari in rough Latin letters ("వసీం" -> "vaseem"); the rest as is."""
    out = []
    for ch in text.lower():
        if ch in CONSONANTS:
            out.append(CONSONANTS[ch] + "a")  # the vowel every consonant carries
        elif ch in SIGNS:
            if out and out[-1].endswith("a") and SIGNS[ch] not in ("m", "h", "n"):
                out[-1] = out[-1][:-1]  # a vowel sign or virama replaces the carried vowel
            out.append("" if SIGNS[ch] == "_" else SIGNS[ch])
        elif ch in VOWELS:
            out.append(VOWELS[ch])
        elif ch != "\u093c":  # nukta
            out.append(ch)
    return "".join(out)


def _sound(word: str) -> str:
    """A name's sound: "Waseem", "vaseem", "వసీము" alike."""
    word = re.sub(r"[^a-z]", "", romanize(word))
    for a, b in (("w", "v"), ("z", "j"), ("ph", "f"), ("th", "t"), ("dh", "d"), ("kh", "k"), ("gh", "g"),
                 ("bh", "b"), ("sh", "s"), ("ee", "i"), ("ii", "i"), ("oo", "u"), ("uu", "u"), ("aa", "a"), ("q", "k")):
        word = word.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", word)


def says_name(text: str, name: str) -> bool:
    """Whether the customer said this first name, in any script ("నేను వసీం")."""
    want = _sound((name.split() or [""])[0])
    if len(want) < 3:
        return False
    for word in re.split(r"[\s,.!?।]+", text):
        heard = _sound(word)
        # The name may carry an ending ("వసీంనే", "it's Waseem"): compare its start too
        if any(SequenceMatcher(None, want, h).ratio() >= 0.8 for h in {heard, heard[: len(want) + 1]} if h):
            return True
    return False


def requested_language(text: str) -> str | None:
    """The language the customer asked for by name, if exactly one."""
    wanted, unwanted = set(), set()
    for part in re.split(r"[.,!?;।]", text.lower()):
        words = re.findall(r"[\w'ऀ-෿]+", part)
        for i, word in enumerate(words):
            for code, names in REQUEST_NAMES.items():
                if not any(n in word for n in names):
                    continue
                before = words[max(0, i - NOT_BEFORE):i]
                after = words[i + 1:i + 1 + NOT_AFTER]
                negated = any(NOT_BEFORE_RE.match(w) for w in before) or any(NOT_AFTER_RE.match(w) for w in after)
                (unwanted if negated else wanted).add(code)
    hits = wanted - unwanted
    return next(iter(hits)) if len(hits) == 1 else None


def opening_language(language: str | None, default: str, available: dict) -> str:
    """The call's first language: the sheet's, else the default, else any with an opening line."""
    for candidate in (language, default):
        if candidate in NAMES and candidate in available:
            return candidate
    return next(code for code in available if code in NAMES)
