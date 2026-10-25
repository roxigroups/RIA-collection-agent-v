"""One phone call, from pickup to hang-up.

Outbound calls are placed by the dialer (server.py) and carry their call id;
an inbound call to the Vobiz number is matched to the caller's latest invoice.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import date

from livekit import rtc
from livekit.agents import Agent, AgentSession, JobContext, JobProcess, metrics
from livekit.agents.voice import room_io
from livekit.plugins import noise_cancellation, silero

from dialer import phone_e164, utc_now
from ria import dates, recording, script, settings, voice
from ria.agent import DB, CollectionAgent, speakable
from ria.languages import opening_language
from ria.script import pick

logger = logging.getLogger("ria-agent")
logger.setLevel(logging.INFO)


def prewarm(proc: JobProcess) -> None:
    # VAD loaded once per worker process. The activation threshold and minimum
    # speech length keep fans, traffic and clicks from counting as the customer
    proc.userdata["vad"] = silero.VAD.load(
        min_silence_duration=settings.VAD_MIN_SILENCE,
        min_speech_duration=settings.VAD_MIN_SPEECH,
        activation_threshold=settings.VAD_THRESHOLD,
    )


def is_phone_call(participant) -> bool:
    return participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP


def is_test_caller(participant) -> bool:
    # A simulated customer (simulate_call.py), allowed only when the agent runs with RIA_ALLOW_TEST_CALLER=1
    return os.getenv("RIA_ALLOW_TEST_CALLER") == "1" and participant.identity.startswith("test-caller-")


async def wait_until_answered(ctx: JobContext, participant, timeout: float = 60.0) -> bool:
    # An outbound call's SIP participant joins while the phone still rings; a
    # greeting before pickup would play into the ringtone
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if participant.attributes.get("sip.callStatus", "active") == "active":
            return True
        if participant.identity not in ctx.room.remote_participants:
            return False
        await asyncio.sleep(0.2)
    return False


def load_call(participant) -> dict | None:
    """The invoice call (call sheet row) this participant belongs to, or None."""
    try:
        metadata = json.loads(participant.metadata or "{}")
    except ValueError:
        metadata = {}
    if isinstance(metadata, dict) and metadata.get("call_id"):
        return DB.get_collection_call(metadata["call_id"])
    phone = phone_e164(participant.attributes.get("sip.phoneNumber", ""))
    latest = DB.latest_call_for_phone(phone) if phone else None
    return DB.get_collection_call(DB.start_inbound_call(latest)) if latest else None


def noise_filter():
    """NOISE_CANCELLATION: "off" disables filter (recommended for self-hosted LiveKit to
    prevent 404 license stalls); "bvc" or "nc" requires LiveKit Cloud."""
    mode = os.getenv("NOISE_CANCELLATION", "off").lower()
    if mode == "off":
        return None
    return noise_cancellation.NC() if mode == "nc" else noise_cancellation.BVCTelephony()


def make_session(ctx: JobContext, stt, tts) -> AgentSession:
    return AgentSession(
        stt=stt,
        llm=voice.make_llm(),
        tts=tts,
        vad=ctx.proc.userdata["vad"],
        user_away_timeout=settings.USER_AWAY_TIMEOUT,
        turn_handling={
            "turn_detection": "vad",
            "endpointing": {"min_delay": settings.ENDPOINTING_MIN_DELAY, "max_delay": settings.ENDPOINTING_MAX_DELAY},
            "interruption": {
                "mode": "vad",
                "min_duration": settings.INTERRUPT_MIN_SECONDS,
                "min_words": settings.INTERRUPT_MIN_WORDS,
                "resume_false_interruption": True,
                "false_interruption_timeout": settings.FALSE_INTERRUPTION_TIMEOUT,
            },
            # Off: it saved only ~0.1 s, and the app's notes to the model (a day it heard, a
            # refusal) change the conversation after the draft, which then goes to waste
            "preemptive_generation": {"enabled": False},
        },
    )


class CallCosts:
    """API spend for the call log line ("cost for 1.2 min: ...")."""

    def __init__(self) -> None:
        self.llm_usd = 0.0
        self.stt_seconds = 0.0
        self.tts_chars = 0
        self.started = time.monotonic()

    def add(self, m) -> None:
        if isinstance(m, metrics.LLMMetrics):
            fresh_in = m.prompt_tokens - m.prompt_cached_tokens
            p_in, p_cached, p_out = settings.LLM_USD_PER_M
            self.llm_usd += (fresh_in * p_in + m.prompt_cached_tokens * p_cached + m.completion_tokens * p_out) / 1e6
        elif isinstance(m, metrics.STTMetrics):
            self.stt_seconds += m.audio_duration
        elif isinstance(m, metrics.TTSMetrics):
            self.tts_chars += m.characters_count

    def log(self, call_id: str, line_chars: int) -> None:
        inr = float(os.getenv("USD_INR", "88"))
        minutes = max((time.monotonic() - self.started) / 60, 1 / 60)
        llm_inr = self.llm_usd * inr
        stt_inr = minutes * settings.STT_USD_PER_MIN * inr
        tts_inr = (self.tts_chars + line_chars) * settings.TTS_USD_PER_CHAR * inr
        line_inr = minutes * (float(os.getenv("VOBIZ_INR_PER_MIN", "0.5")) + settings.SIP_USD_PER_MIN * inr)
        apis = llm_inr + stt_inr + tts_inr
        logger.info("Call %s cost for %.1f min: APIs ₹%.2f (₹%.2f/min: LLM ₹%.2f, STT ₹%.2f, voice ₹%.2f), "
                    "line ₹%.2f est., total ₹%.2f/min", call_id, minutes, apis, apis / minutes, llm_inr, stt_inr,
                    tts_inr, line_inr, (apis + line_inr) / minutes)


async def entrypoint(ctx: JobContext) -> None:
    logger.info("Connecting to room: %s", ctx.room.name)
    await ctx.connect()
    try:
        participant = await ctx.wait_for_participant()
    except RuntimeError:
        logger.info("Caller left %s before RIA joined; nothing to do", ctx.room.name)
        return
    if not is_phone_call(participant) and not is_test_caller(participant):
        logger.info("%s is not a phone call; RIA only handles calls", participant.identity)
        return

    script.load()  # prompts.py as it is now: edits apply from this call on
    prompts = script.PROMPTS
    call = await asyncio.to_thread(load_call, participant)
    language = opening_language((call or {}).get("language"), settings.DEFAULT_LANGUAGE, prompts.COLLECTION_OPENINGS)

    tts = voice.make_tts()
    customer_name = (call or {}).get("customer_name", "").strip()
    has_name = bool(customer_name and customer_name.lower() not in ("customer", "unknown", "sir", "madam"))
    company_name = (call or {}).get("company", "")
    fields = {"company": company_name, "customer": customer_name if has_name else ""}

    has_amount = bool(call and call.get("amount") is not None and float(call["amount"]) > 0)
    has_inv = bool(call and call.get("invoice_no") and str(call["invoice_no"]).strip())
    has_due = bool(call and call.get("due_date"))

    if call:
        amount_str = dates.format_inr(float(call["amount"])) if has_amount else ""
        overdue_str = ""
        if has_due:
            try:
                due_val = call["due_date"]
                due_dt = date.fromisoformat(due_val) if isinstance(due_val, str) else due_val
                overdue_str = dates.overdue_phrase(due_dt, language)
            except Exception:
                overdue_str = ""
        fields.update(invoice_no=call.get("invoice_no") or "", amount=amount_str, overdue=overdue_str)

    lines = voice.FixedLines(tts, fields)

    # Made while the phone rings: adaptive greeting and follow-up line
    if call:
        opening = pick(prompts.COLLECTION_OPENINGS, language) if has_name else pick(getattr(prompts, "COLLECTION_OPENINGS_GENERIC", prompts.COLLECTION_OPENINGS), language)
    else:
        opening = pick(prompts.UNKNOWN_CALLER, language)

    lines.prepare(opening)
    if call:
        if has_inv and has_amount:
            amt_lines = prompts.COLLECTION_AMOUNT_LINES
        elif has_amount:
            amt_lines = getattr(prompts, "COLLECTION_AMOUNT_NO_INV", prompts.COLLECTION_AMOUNT_LINES)
        elif has_inv:
            amt_lines = getattr(prompts, "COLLECTION_INV_NO_AMOUNT", prompts.COLLECTION_AMOUNT_LINES)
        else:
            amt_lines = getattr(prompts, "COLLECTION_GENERIC_FOLLOWUP", prompts.COLLECTION_AMOUNT_LINES)

        lines.prepare(pick(amt_lines, language))
        who_line = prompts.COLLECTION_WHO_ASK if has_name else getattr(prompts, "COLLECTION_PAYMENTS_ASK", prompts.COLLECTION_WHO_ASK)
        lines.prepare(pick(who_line, language))
        lines.prepare(pick(prompts.CALLBACK_TIME_ASK, language))  # no call details: from the disk cache
        if hasattr(prompts, "COLLECTION_CONFIRM_PAID"):
            lines.prepare(pick(prompts.COLLECTION_CONFIRM_PAID, language))


    if not await wait_until_answered(ctx, participant):
        logger.info("Call in %s was not answered; nothing to do", ctx.room.name)
        lines.cancel()
        return

    keywords = voice.stt_keywords(call)
    stt = voice.make_stt(language, keywords)
    session = make_session(ctx, stt, tts)
    room_options = room_io.RoomOptions(audio_input=room_io.AudioInputOptions(noise_cancellation=noise_filter()))

    if not call:
        # Inbound call from a number with no invoice on record
        await session.start(room=ctx.room, agent=Agent(instructions=""), room_options=room_options)
        await (await lines.say(session, opening))
        await ctx.delete_room()
        return

    call_id = call["call_id"]
    await asyncio.to_thread(
        DB.save_collection_call, call_id, status="live", answered_at=utc_now(),
        phone=phone_e164(participant.attributes.get("sip.phoneNumber", "")) or call["phone"],
    )
    agent = CollectionAgent(call, language, lines, stt)
    costs = CallCosts()
    transcript: list[dict] = []  # the conversation as the dashboard shows it

    def hang_up_after(template_lines: dict | None) -> None:
        async def run() -> None:
            deadline = time.monotonic() + 10
            while session.agent_state == "speaking" and time.monotonic() < deadline:
                await asyncio.sleep(0.05)  # let a sentence already playing finish
            if template_lines:
                await (await lines.say(session, pick(template_lines, agent.language), interruptible=False))
            await asyncio.sleep(0.3)
            session.shutdown()

        asyncio.create_task(run())

    # The outcome is saved: the closing line for it (or the general one), then hang up
    agent.on_finished = lambda code: hang_up_after(prompts.CLOSING_LINES.get(code) or prompts.COLLECTION_GOODBYES)

    def voicemail(text: str) -> None:
        # Counted as not answered, so the usual retry follows
        logger.info("Call %s: voicemail (%r); hanging up", call_id, text)

        async def run() -> None:
            await asyncio.to_thread(DB.save_collection_call, call_id, outcome="NO-ANSWER",
                                    notes="Voicemail / network message; no one answered.")
            session.shutdown()

        asyncio.create_task(run())

    agent.on_voicemail = voicemail

    timing = {"customer_done": None}

    @session.on("metrics_collected")
    def _count(ev) -> None:
        costs.add(ev.metrics)

    @session.on("conversation_item_added")
    def _record(ev) -> None:
        role, text = getattr(ev.item, "role", None), (getattr(ev.item, "text_content", None) or "").strip()
        if role == "assistant":
            agent.last_line_interrupted = bool(getattr(ev.item, "interrupted", False))
        if role == "assistant" and (text := speakable(text).strip()):
            cut = bool(getattr(ev.item, "interrupted", False))
            logger.info("RIA%s: %s", " (interrupted)" if cut else "", text)
            # When it played, for "Listen turn" on the recording
            played = getattr(ev.item, "metrics", None) or {}
            transcript.append({"who": "RIA", "lang": agent.language, "txt": text, "cut": cut,
                               "at": played.get("started_speaking_at"), "until": played.get("stopped_speaking_at")})

    def heard_customer(text: str) -> None:
        # Recorded where the turn is handled: a turn the app answers itself (who line,
        # instant yes, callback) never reaches the conversation, and wasn't logged or saved
        logger.info("Customer (%s): %s", agent.language, text)
        transcript.append({"who": "Retailer", "lang": agent.language, "txt": text,
                           "at": speech["start"], "until": speech["end"] or time.time()})
        speech["start"] = None

    agent.on_heard = heard_customer
    # The customer's speech since their last turn (wall clock, the recording's timeline)
    speech: dict[str, float | None] = {"start": None, "end": None}
    heard = {"at": 0.0}  # when the last transcript arrived

    @session.on("user_input_transcribed")
    def _stt(ev) -> None:
        heard["at"] = time.monotonic()
        if os.getenv("RIA_DEBUG_STT") == "1":
            logger.info("Call %s STT %s: %r", call_id, "final" if ev.is_final else "interim", ev.transcript)

    async def check_heard(spoke_from: float, spoke_until: float) -> None:
        # The customer spoke but Pulse returned nothing (it skips some sentences
        # entirely): their saved audio goes to a second transcriber, and RIA answers
        # what they said. Only if that fails too is the customer asked to repeat
        # Pulse's text comes ~0.3 s after they stop, gpt-4o-transcribe's ~1 s
        await asyncio.sleep(2.0 if settings.STT_PROVIDER == "openai" else 1.2)
        if heard["at"] >= spoke_from or agent.finished:
            return
        logger.warning("Call %s: customer spoke but no transcript came; using the backup transcriber", call_id)
        frames = agent.audio_between(spoke_from - 0.3, spoke_until + 0.3)
        try:
            text = await voice.transcribe_backup(frames, agent.language, keywords) if frames else ""
        except Exception:
            logger.exception("Call %s: backup transcription failed", call_id)
            text = ""
        if heard["at"] >= spoke_from or agent.finished:
            return  # Pulse's transcript came after all
        stt.update_options(language=voice.stt_languages(agent.language))  # a fresh connection for the next turn
        if text:
            logger.info("Call %s: backup transcript: %r", call_id, text)
            # The turn is the speech it was made from (the live transcriber may have
            # caught its first word as a turn of its own; the recording merges them)
            to_wall = time.time() - time.monotonic()
            speech["start"], speech["end"] = spoke_from + to_wall, spoke_until + to_wall
            await agent.answer_backup(text)
        else:
            await lines.say(session, pick(prompts.COLLECTION_REPEAT, agent.language))

    @session.on("agent_state_changed")
    def _latency(ev) -> None:
        if ev.new_state == "speaking" and timing["customer_done"]:
            logger.info("Call %s reply latency %.0fms (after the customer's %.1fs pause)", call_id,
                        (time.monotonic() - timing["customer_done"]) * 1000 + settings.VAD_MIN_SILENCE * 1000,
                        settings.VAD_MIN_SILENCE)
            timing["customer_done"] = None

    silences = {"count": 0, "last_speech": time.monotonic()}

    async def ask_if_there() -> None:
        asked_at = time.monotonic()  # an answer that starts mid-question counts
        await (await lines.say(session, pick(prompts.COLLECTION_ARE_YOU_THERE, agent.language)))
        await asyncio.sleep(settings.USER_AWAY_TIMEOUT)
        if silences["last_speech"] < asked_at and not agent.finished:
            logger.info("Call %s: no response, hanging up", call_id)
            session.shutdown()

    @session.on("user_state_changed")
    def _user_state(ev) -> None:
        if ev.new_state == "speaking":
            silences["last_speech"] = time.monotonic()
            speech["start"] = speech["start"] or time.time()
        elif ev.old_state == "speaking":
            speech["end"] = time.time()
        if ev.old_state == "speaking" and ev.new_state == "listening":
            timing["customer_done"] = time.monotonic()
            if os.getenv("RIA_DEBUG_STT") == "1":
                logger.info("Call %s: customer stopped after %.1fs of speech (RIA %s)", call_id,
                            timing["customer_done"] - silences["last_speech"], session.agent_state)
            if timing["customer_done"] - silences["last_speech"] >= 0.6:
                asyncio.create_task(check_heard(silences["last_speech"], timing["customer_done"]))
        # 7 s with nobody talking (phone put down): ask once, then hang up
        if ev.new_state != "away" or agent.finished:
            return
        silences["count"] += 1
        if silences["count"] == 1:
            asyncio.create_task(ask_if_there())
        else:
            logger.info("Call %s: no response, hanging up", call_id)
            session.shutdown()

    await session.start(room=ctx.room, agent=agent, room_options=room_options, record=True)

    async def _record_end() -> None:
        costs.log(call_id, lines.tts_chars)
        if agent.debug_audio:
            await asyncio.to_thread(voice.save_wav, agent.debug_audio,
                                    os.path.join(settings.BACKEND_DIR, "debug_audio", f"{call_id}.wav"))
        # The recording, each turn timed on it, and the customer's turns heard again whole
        turns, name = transcript, None
        try:
            name, started = await recording.keep(session, call_id)
            turns = recording.timed(transcript, started)
            if name:
                turns = await asyncio.wait_for(recording.retranscribe(name, turns, keywords), timeout=25)
        except Exception:
            logger.exception("Call %s: saving the recording or its transcript failed", call_id)
            turns = recording.timed(transcript, None) if turns is transcript else turns
        audio_ref = name
        if name:
            try:
                gcs_url = await recording.archive_to_gcs(name)
                if gcs_url:
                    audio_ref = gcs_url
            except Exception:
                logger.warning("Call %s: GCS upload error, using local recording reference", call_id)
        await asyncio.to_thread(DB.end_collection_call, call_id, turns, audio_ref)

    async def _drop_line() -> None:
        await ctx.delete_room()

    ctx.add_shutdown_callback(_record_end)
    ctx.add_shutdown_callback(_drop_line)
    # Customer hung up, or the goodbye finished: end the job, which drops the phone line
    session.on("close", lambda ev: ctx.shutdown(reason="call ended"))

    # Interruptible: if the customer talks over the greeting, RIA stops and answers them
    await lines.say(session, opening)
    logger.info("Call %s started for %s in %s", call_id, call["invoice_no"], language)
