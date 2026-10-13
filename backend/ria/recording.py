"""The call's own recording: kept after the call, each transcript turn timed against it,
and the customer's turns transcribed again from it."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil

import av
import numpy as np

from ria import settings, voice

logger = logging.getLogger("ria-agent")

RECORDINGS_DIR = os.path.join(settings.BACKEND_DIR, "recordings")
RATE = 16000
# Around a customer turn: speech starts a little before the voice detector fires and
# trails off after it stops
LEAD, TAIL = 0.25, 0.4


async def keep(session, call_id: str) -> tuple[str | None, float | None]:
    """The session's stereo recording (customer left, RIA right, on one timeline) copied
    out of the job's temporary folder, which is deleted after the call. Returns the file
    name in RECORDINGS_DIR and the wall-clock time the recording starts at."""
    recorder = getattr(session, "_recorder_io", None)  # LiveKit's recorder; no public handle
    if recorder is None or recorder.output_path is None:
        return None, None
    started = recorder.recording_started_at
    if recorder.recording:
        await recorder.aclose()  # flushes the file; LiveKit's own close afterwards does nothing
    if not recorder.output_path.exists():
        return None, None
    name = f"{call_id}.ogg"
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    await asyncio.to_thread(shutil.copyfile, recorder.output_path, os.path.join(RECORDINGS_DIR, name))
    return name, started


async def archive_to_gcs(name: str) -> str | None:
    """Uploads a local recording to Google Cloud Storage (GCS) if GCS_RECORDINGS_BUCKET is configured.
    Returns the cloud URL or None if GCS is disabled or the upload fails (keeps local file)."""
    bucket_name = os.getenv("GCS_RECORDINGS_BUCKET", "").strip()
    if not name or not bucket_name:
        return None
    local_path = os.path.join(RECORDINGS_DIR, name)
    if not os.path.exists(local_path):
        return None

    def _upload():
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(f"recordings/{name}")
            blob.upload_from_filename(local_path, content_type="audio/ogg")
            logger.info("Archived recording %s to gs://%s/recordings/%s", name, bucket_name, name)
            return f"https://storage.googleapis.com/{bucket_name}/recordings/{name}"
        except Exception as exc:
            logger.warning("GCS upload failed for %s (%s); keeping local recording", name, exc)
            return None

    return await asyncio.to_thread(_upload)


def _letters(text: str) -> str:
    return re.sub(r"[\W_]+", "", text)


def timed(turns: list[dict], started: float | None) -> list[dict]:
    """Each turn's wall-clock span ("at", "until") as seconds into the recording ("t", "d").
    Customer turns over the same speech become one: the live transcriber sometimes caught
    only the first word ("ఆ.") and the backup the whole sentence, which then showed twice."""
    out: list[dict] = []
    for turn in turns:
        turn = dict(turn)
        at, until = turn.pop("at", None), turn.pop("until", None)
        if started is not None and at is not None:
            turn["t"] = round(max(at - started, 0.0), 2)
            turn["d"] = round(max((until or at) - at, 0.0), 2)
        same = next((o for o in reversed(out) if o.get("who") == "Retailer" and "t" in o), None) \
            if turn.get("who") == "Retailer" and "t" in turn else None
        if same and turn["t"] < same["t"] + same["d"] + 0.2:
            end = max(same["t"] + same["d"], turn["t"] + turn["d"])
            same["t"] = min(same["t"], turn["t"])
            same["d"] = round(end - same["t"], 2)
            a, b = same["txt"], turn["txt"]
            # The fuller text wins; two different parts are kept in order
            same["txt"] = b if _letters(a) in _letters(b) else a if _letters(b) in _letters(a) else f"{a} {b}"
            continue
        out.append(turn)
    return out


def customer_audio(name: str) -> np.ndarray:
    """The customer's channel of a recording, 16 kHz mono int16."""
    resampler = av.AudioResampler(format="s16", layout="stereo", rate=RATE)
    chunks = []
    with av.open(os.path.join(RECORDINGS_DIR, name)) as container:
        for frame in container.decode(audio=0):
            chunks += [f.to_ndarray().reshape(-1, 2)[:, 0] for f in resampler.resample(frame)]
    chunks += [f.to_ndarray().reshape(-1, 2)[:, 0] for f in resampler.resample(None)]
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)


async def retranscribe(name: str, turns: list[dict], keywords: list[str]) -> list[dict]:
    """Customer turns the live transcriber caught only a fragment of ("ఆ.", "హా" for a whole
    sentence) transcribed again from the recording, the whole turn at once. Others keep the
    live text: on a test call it was right where a second pass made "డ్యూ" into "ఫుడ్ యూ"."""
    audio = await asyncio.to_thread(customer_audio, name)
    limit = asyncio.Semaphore(4)

    async def one(turn: dict) -> dict:
        if turn.get("who") != "Retailer" or "t" not in turn or len(_letters(turn["txt"])) > 3:
            return turn
        start, end = int((turn["t"] - LEAD) * RATE), int((turn["t"] + turn["d"] + TAIL) * RATE)
        clip = audio[max(start, 0):max(end, 0)]
        if clip.size < 0.3 * RATE:
            return turn
        async with limit:
            try:
                text = await voice.transcribe_pcm(clip, RATE, turn.get("lang", "te"), keywords)
            except Exception:
                logger.exception("Re-transcribing a turn failed; keeping the live text")
                return turn
        if len(_letters(text)) > len(_letters(turn["txt"])):
            return {**turn, "txt": text, "live": turn["txt"]}
        return turn

    return list(await asyncio.gather(*(one(t) for t in turns)))
