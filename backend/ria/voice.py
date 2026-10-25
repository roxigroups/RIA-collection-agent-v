"""Speech in and out: Smallest Pulse (speech-to-text), gpt-4.1-mini, the cloned
voice, and the fixed lines the app speaks word for word."""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import re
import time
import wave

import numpy as np
from livekit import rtc
from livekit.agents import utils
from livekit.plugins import openai, smallestai

from ria import settings
from ria.script import fill

logger = logging.getLogger("ria-agent")




# Words the customer may say that the transcriber should spell right: the call adds
# the customer's and the company's names
STT_KEYWORDS = [
    "RIA", "payment", "invoice", "UPI", "PhonePe", "Google Pay",
    "అవునండి", "నేనే", "కట్టేశాను", "చేస్తాను",
    # Negations & Refusals (Telugu)
    "కట్టను", "కట్టనండి", "కట్టేది లేదు", "కట్టలేను", "కాదు", "కాదండి", "లేదు", "లేదండి", "కుదరదు", "డబ్బులు లేవు", "ఇవ్వను",
    # Negations & Refusals (Hindi)
    "नहीं दूँगा", "नहीं देंगे", "नहीं भरूँगा", "पैसे नहीं हैं", "गलत नंबर", "नहीं",
    # Negations & Refusals (English)
    "won't pay", "cannot pay", "not him", "wrong number", "no funds",
]


def _takes_hints(model: str) -> bool:
    """gpt-transcribe and gpt-live-transcribe take several languages and keywords."""
    return model.startswith(("gpt-transcribe", "gpt-live-transcribe"))


def stt_languages(language: str) -> str | list[str]:
    """The conversation language, plus English for the words customers mix in
    ("payment", "UPI", "already")."""
    if not _takes_hints(settings.STT_MODEL) or language == "en":
        return language
    return [language, "en"]


def stt_keywords(call: dict | None) -> list[str]:
    names = [(call or {}).get(k) for k in ("customer_name", "business", "company")]
    return list(dict.fromkeys([n for n in names if n] + STT_KEYWORDS))


def make_stt(language: str, keywords: list[str] | None = None):
    """The transcriber, in the conversation language. RIA_STT=openai (default):
    RIA_STT_MODEL, streaming. gpt-transcribe (the default) on phone-quality Telugu got
    ~5-10% of characters wrong where gpt-4o-transcribe got ~50-70%, often in Tamil or
    Latin letters, and it returned nothing for line noise where gpt-4o-transcribe made up
    words; just as fast. Smallest Pulse wrote Telugu in Tamil letters or returned nothing
    for whole turns. RIA_STT=pulse: Pulse, ~0.7 s faster, fine on clean audio."""
    if settings.STT_PROVIDER == "pulse":
        return smallestai.STT(
            model="pulse",
            language=language,
            sample_rate=24000,
            # Spoken numbers as digits: "ముప్పై ఒకటి" -> 31
            itn_normalize=True,
            # With a finalize message at a turn's end Pulse sent no transcript after it
            finalize_on_flush=False,
            # Pulse's own speech events arrived with the transcript and held back the
            # "customer stopped" signal; RIA's local voice detector gives it at once
            vad_events=False,
        )
    # No prompt: on a noisy line gpt-4o-transcribe wrote the prompt's own words as the
    # customer's ("కస్టమర్:", "బిల్ చెల్లింపు గురించి మాట్లాడండి") and the call went nowhere.
    # Keywords are hints, not text: with them line noise still came back empty
    if not _takes_hints(settings.STT_MODEL):
        return openai.STT(model=settings.STT_MODEL, language=language, use_realtime=True)
    return openai.STT(model=settings.STT_MODEL, language=stt_languages(language),
                      keywords=keywords or STT_KEYWORDS, use_realtime=True)


def wav_bytes(frames: list[rtc.AudioFrame], rate: int = 16000) -> bytes:
    """Mono 16-bit WAV of the frames, resampled to `rate`."""
    audio = utils.combine_frames(frames)
    resampler = rtc.AudioResampler(audio.sample_rate, rate, num_channels=1)
    pcm = utils.combine_frames(resampler.push(audio) + resampler.flush())
    wav = io.BytesIO()
    with wave.open(wav, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm.data.tobytes())
    return wav.getvalue()


def save_wav(frames: list[rtc.AudioFrame], path: str) -> None:
    """RIA_DEBUG_AUDIO: the customer's side of a call, for replaying through the transcriber."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rms = np.sqrt(np.mean(np.concatenate([np.frombuffer(f.data, dtype=np.int16) for f in frames]).astype(np.float32) ** 2))
    logger.info("Saved %s: %.0f s at %d Hz, average level %.0f", path, sum(f.duration for f in frames),
                frames[0].sample_rate, rms)
    with open(path, "wb") as out:
        out.write(wav_bytes(frames, frames[0].sample_rate))


async def transcribe_backup(frames: list[rtc.AudioFrame], language: str, keywords: list[str] | None = None) -> str:
    """The customer's words from saved audio, when Pulse returned nothing for them
    (it skipped "ఈ నెల ఏడో తేదీ UPI లో కట్టాను" entirely, every time)."""
    return await transcribe_wav(wav_bytes(frames), language, keywords)


async def transcribe_pcm(pcm: np.ndarray, rate: int, language: str, keywords: list[str] | None = None) -> str:
    """Mono int16 samples transcribed in one go (a turn cut from the call's recording)."""
    wav = io.BytesIO()
    with wave.open(wav, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(pcm.astype(np.int16).tobytes())
    return await transcribe_wav(wav.getvalue(), language, keywords)


async def transcribe_wav(wav: bytes, language: str, keywords: list[str] | None = None) -> str:
    from openai import AsyncOpenAI

    model = settings.STT_MODEL if settings.STT_PROVIDER == "openai" else "gpt-transcribe"
    hints = {"languages": [language] if language == "en" else [language, "en"], "keywords": keywords or STT_KEYWORDS} \
        if _takes_hints(model) else {"language": language}
    result = await AsyncOpenAI().audio.transcriptions.create(
        model=model, file=("turn.wav", wav, "audio/wav"), **hints,
    )
    return (result.text or "").strip()


def make_llm() -> openai.LLM:
    return openai.LLM(
        model=settings.LLM_MODEL,
        temperature=0.3,
        # One tool at a time: two outcomes saved in one turn made no sense
        parallel_tool_calls=False,
    )


def _add_number_language() -> None:
    """Send Smallest's number_pronunciation_language, which the LiveKit plugin
    doesn't expose: it sets how digits, ₹ amounts and dates are read (in English)
    while the voice keeps speaking Telugu."""
    from livekit.plugins.smallestai import tts as smallest_tts

    if getattr(smallest_tts, "_ria_number_language", False):
        return
    language = os.getenv("SMALLEST_NUMBER_LANGUAGE", "en").strip()
    if not language:
        return
    http_options = smallest_tts._to_smallest_options
    stream_payload = smallest_tts.SynthesizeStream._base_payload

    def with_numbers_http(opts):
        return {**http_options(opts), "number_pronunciation_language": language}

    def with_numbers_stream(self, *args, **kwargs):
        return {**stream_payload(self, *args, **kwargs), "number_pronunciation_language": language}

    smallest_tts._to_smallest_options = with_numbers_http
    smallest_tts.SynthesizeStream._base_payload = with_numbers_stream
    smallest_tts._ria_number_language = True


TTS_SAMPLE_RATE = int(settings.env_float("SMALLEST_TTS_SAMPLE_RATE", 16000))


def make_tts() -> smallestai.TTS:
    """The cloned voice on Smallest Lightning v3.1 Pro; language="auto" follows
    whatever language the text is in."""
    _add_number_language()
    return smallestai.TTS(
        model="lightning_v3.1_pro",
        voice_id=os.environ["SMALLEST_TTS_VOICE_ID"],
        language="auto",
        # Twice the phone line's 8 kHz: no loss on a call, and the first audio comes
        # ~0.2 s sooner than at 44.1 kHz
        sample_rate=TTS_SAMPLE_RATE,
        speed=settings.env_float("SMALLEST_TTS_SPEED", 1.0),
    )


class PreparedLine:
    """TTS audio for a fixed line, made ahead and playable from its first frame
    (a slow first TTS request once left a customer in silence for seconds)."""

    def __init__(self, tts, text: str, cache_path: str | None = None) -> None:
        self.frames: list[rtc.AudioFrame] = []
        self.done = False
        self._changed = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.from_cache = bool(cache_path) and self._load(cache_path)
        if not self.from_cache:
            self.task = asyncio.create_task(self._run(tts, text, cache_path))

    def _load(self, path: str) -> bool:
        try:
            with np.load(path) as data:
                pcm, rate = data["pcm"], int(data["rate"])
        except (OSError, ValueError, KeyError):
            return False
        step = rate // 50  # 20 ms frames
        self.frames = [
            rtc.AudioFrame(pcm[i : i + step].tobytes(), rate, 1, len(pcm[i : i + step]))
            for i in range(0, len(pcm), step)
        ]
        self.done = True
        return bool(self.frames)

    async def _run(self, tts, text: str, cache_path: str | None) -> None:
        try:
            async for ev in tts.synthesize(text):
                self.frames.append(ev.frame)
                self._changed.set()
            if cache_path and self.frames and self.frames[0].num_channels == 1:
                pcm = np.concatenate([np.frombuffer(f.data, dtype=np.int16) for f in self.frames])
                tmp = f"{cache_path}.{os.getpid()}.tmp.npz"
                np.savez(tmp, pcm=pcm, rate=self.frames[0].sample_rate)
                os.replace(tmp, cache_path)  # atomic: calls run in parallel
        except Exception:
            logger.exception("TTS failed for %r", text)
        finally:
            self.done = True
            self._changed.set()

    async def wait_first_frame(self, timeout: float) -> bool:
        """True once audio is available; False if none came in time (or TTS failed)."""
        deadline = time.monotonic() + timeout
        while not self.frames and not self.done:
            self._changed.clear()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            try:
                await asyncio.wait_for(self._changed.wait(), remaining)
            except asyncio.TimeoutError:
                return False
        return bool(self.frames)

    async def audio(self):
        i = 0
        while True:
            while i < len(self.frames):
                yield self.frames[i]
                i += 1
            if self.done:
                return
            self._changed.clear()
            if i < len(self.frames) or self.done:
                continue
            await self._changed.wait()


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?।])\s+")


def line_parts(template: str) -> list[tuple[str, bool]]:
    """A fixed line split into runs of sentences: (template part, has call details)."""
    parts: list[tuple[str, bool]] = []
    for sentence in SENTENCE_SPLIT_RE.split(template.strip()):
        # Anything but {company} differs per call ({customer}, {amount}, ...)
        personal = bool(re.search(r"\{(?!company\})\w+\}", sentence))
        if parts and parts[-1][1] == personal:
            parts[-1] = (f"{parts[-1][0]} {sentence}", personal)
        else:
            parts.append((sentence, personal))
    return parts


class FixedLines:
    """Lines spoken word for word in the cloned voice (greeting, amount, read-backs,
    goodbyes). Parts with no customer details come from a disk cache after the
    first call, so the TTS is billed only for the rest."""

    def __init__(self, tts, fields: dict) -> None:
        self.tts = tts
        self.fields = fields
        self.prepared: dict[str, PreparedLine] = {}
        self.tts_chars = 0
        self.voice_key = (f"{os.environ['SMALLEST_TTS_VOICE_ID']}|{os.getenv('SMALLEST_NUMBER_LANGUAGE', 'en')}"
                          f"|{os.getenv('SMALLEST_TTS_SPEED', '1.0')}|{TTS_SAMPLE_RATE}")

    def prepare(self, template: str, cache: bool = True) -> tuple[str, list[PreparedLine]]:
        """Starts synthesizing a line (if not already); returns its text and parts."""
        texts, lines = [], []
        for part, personal in line_parts(template):
            text = fill(part, self.fields)
            texts.append(text)
            if text not in self.prepared:
                cache_path = None
                if cache and not personal:
                    os.makedirs(settings.TTS_CACHE_DIR, exist_ok=True)
                    digest = hashlib.sha1(f"{self.voice_key}|{text}".encode()).hexdigest()
                    cache_path = os.path.join(settings.TTS_CACHE_DIR, f"{digest}.npz")
                self.prepared[text] = PreparedLine(self.tts, text, cache_path)
                if not self.prepared[text].from_cache:
                    self.tts_chars += len(text)
            lines.append(self.prepared[text])
        return " ".join(texts), lines

    async def say(self, session, template: str, interruptible: bool = True, cache: bool = True,
                  remember: bool = True):
        """Speaks a line; the customer can talk over it unless interruptible=False.
        remember=False keeps it out of the model's conversation."""
        text, lines = self.prepare(template, cache)

        def speak(**audio):
            try:
                return session.say(text, allow_interruptions=interruptible, add_to_chat_ctx=remember, **audio)
            except RuntimeError:
                return None  # the customer hung up while this line was getting ready

        if not await lines[0].wait_first_frame(timeout=6):
            # Never leave the customer in silence: stream it through the TTS instead
            logger.warning("No pre-made audio after 6 s for %r; streaming it", text[:40])
            return speak()

        async def frames():
            for line in lines:
                async for frame in line.audio():
                    yield frame

        return speak(audio=frames())

    def cancel(self) -> None:
        for line in self.prepared.values():
            if line.task:
                line.task.cancel()
