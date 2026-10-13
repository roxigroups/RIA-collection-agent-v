"""Settings from backend/.env, read in one place."""
from __future__ import annotations

import os

from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BACKEND_DIR, ".env"), override=True)


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


# The model that writes RIA's replies
LLM_MODEL = os.getenv("RIA_LLM_MODEL", "gpt-4.1-mini")
# The opening language when the call sheet names none
DEFAULT_LANGUAGE = os.getenv("COLLECTION_LANGUAGE", "te")
# Fixed lines with no customer details are synthesized once and kept here
TTS_CACHE_DIR = os.path.join(BACKEND_DIR, "tts_cache")

# Turn-taking. VAD_MIN_SILENCE_DURATION is the pause that ends the customer's turn:
# at 0.25-0.4 s sentences with a pause arrived in two pieces (RIA answered half)
VAD_MIN_SILENCE = env_float("VAD_MIN_SILENCE_DURATION", 0.5)
VAD_MIN_SPEECH = env_float("VAD_MIN_SPEECH_DURATION", 0.15)
VAD_THRESHOLD = env_float("VAD_ACTIVATION_THRESHOLD", 0.6)
ENDPOINTING_MIN_DELAY = env_float("ENDPOINTING_MIN_DELAY", 0.1)
ENDPOINTING_MAX_DELAY = env_float("ENDPOINTING_MAX_DELAY", 2.5)
# Barge-in: the customer talking over RIA stops her after this much speech; a
# wordless sound resumes her sentence instead
INTERRUPT_MIN_SECONDS = env_float("INTERRUPT_MIN_SECONDS", 0.3)
FALSE_INTERRUPTION_TIMEOUT = env_float("FALSE_INTERRUPTION_TIMEOUT", 1.5)
# Words transcribed before she stops: 0 = on their voice at once. 1 waited for the
# transcriber and kept her talking ~1 s over the customer
INTERRUPT_MIN_WORDS = int(env_float("INTERRUPT_MIN_WORDS", 0))

# Prices for the per-call cost line in the logs (USD)
LLM_USD_PER_M = (0.40, 0.10, 1.60)  # gpt-4.1-mini: input, cached input, output per 1M tokens
TTS_USD_PER_CHAR = 0.195 / 10_000   # Smallest Lightning v3.1 Pro
# The transcriber: "openai" (RIA_STT_MODEL, gpt-transcribe) or "pulse" (Smallest)
STT_PROVIDER = os.getenv("RIA_STT", "openai").lower()
STT_MODEL = os.getenv("RIA_STT_MODEL", "gpt-transcribe")
STT_USD_PER_MIN = env_float("STT_USD_PER_MIN", (0.0045 if STT_MODEL.startswith("gpt-transcribe") else 0.006)
                            if STT_PROVIDER == "openai" else 0.004)
SIP_USD_PER_MIN = 0.004             # LiveKit Cloud third-party SIP
