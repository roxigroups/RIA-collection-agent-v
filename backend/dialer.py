"""Places queued invoice calls through Vobiz (LiveKit SIP).

The dashboard queues one call per invoice when a call sheet is imported.
Dialer.run() works through them in import order inside each company's calling
hours, DIALER_CONCURRENCY at a time, and turns due retries and callbacks into
calls too. The agent (agent.py) records each answered call; calls nobody
answered are recorded here. Both use the PostgreSQL database in DATABASE_URL.
"""
import asyncio
import contextlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

from livekit import api

from db_driver import DatabaseDriver

logger = logging.getLogger("ria-dialer")

IST = timezone(timedelta(hours=5, minutes=30))
DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y")
# SIP status -> outcome for calls that were never answered
SIP_OUTCOMES = {486: "BUSY", 600: "BUSY", 408: "NO-ANSWER", 480: "NO-ANSWER", 487: "NO-ANSWER"}
# Languages RIA can open a call in (prompts.COLLECTION_OPENINGS)
LANGUAGES = {"te": "te", "telugu": "te", "hi": "hi", "hindi": "hi", "en": "en", "english": "en"}


def phone_e164(raw: str) -> str:
    """Indian mobile as +91XXXXXXXXXX, or "" if it isn't one."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return f"+91{digits}" if re.fullmatch(r"[6-9]\d{9}", digits) else ""


def parse_invoice(row: dict) -> tuple[dict | None, str]:
    """Cleans one imported row; returns (invoice, "") or (None, reason).
    
    Phone number is strictly mandatory for placing a call. Name, invoice number,
    due date, and amount are optional; missing values are handled gracefully.
    """
    row = {k: str(v or "").strip() for k, v in row.items()}
    raw_phone = row.get("phone") or row.get("phno") or ""
    if not raw_phone:
        return None, "missing phone number"
    phone = phone_e164(raw_phone)
    if not phone:
        return None, f"not an Indian mobile number: {raw_phone}"

    # Name and business
    raw_name = (row.get("name") or row.get("business") or row.get("business_name") or "").strip()
    name = raw_name[:80] if raw_name else "Customer"
    business = (row.get("business") or row.get("business_name") or "")[:120].strip()

    # Amount (optional; must be non-negative if provided)
    amount = None
    raw_amount = row.get("amount") or row.get("invoice_amount") or ""
    if raw_amount:
        try:
            parsed_amt = float(re.sub(r"[₹,\s]|Rs\.?|INR", "", raw_amount, flags=re.I))
            if parsed_amt < 0:
                return None, "amount cannot be negative"
            amount = parsed_amt
        except ValueError:
            return None, f"bad amount: {raw_amount}"

    # Due date (optional)
    due = None
    raw_due = row.get("due_date") or row.get("dueDate") or row.get("invoice_date") or ""
    if raw_due:
        for fmt in DATE_FORMATS:
            try:
                due = datetime.strptime(raw_due, fmt).date()
                break
            except ValueError:
                continue
        else:
            return None, f"bad due_date (use DD-MM-YYYY): {raw_due}"

    # Invoice number (optional)
    invoice_no = (row.get("invoice_no") or row.get("invoice_number") or "").strip()[:60]

    # Language (optional)
    language = row.get("language", "").lower().strip()
    if language and language not in LANGUAGES:
        return None, f"unsupported language: {row['language']} (Telugu, Hindi or English)"

    return {
        "customer_name": name,
        "phone": phone,
        "business": business,
        "invoice_no": invoice_no,
        "amount": amount,
        "due_date": due.isoformat() if due else None,
        "language": LANGUAGES.get(language, ""),
        "has_customer_name": bool(raw_name),
        "has_invoice_no": bool(invoice_no),
        "has_amount": amount is not None and amount > 0,
        "has_due_date": due is not None,
    }, ""



def calling_hours() -> tuple[int, int]:
    # RBI fair-practice guidance: recovery calls only between 8 am and 7 pm
    start, end = os.getenv("COLLECTION_CALL_HOURS", "8-19").split("-")
    return int(start), int(end)


def within_calling_hours(rules: dict | None = None) -> bool:
    """Inside COLLECTION_CALL_HOURS and the company's own hours (Settings > rules)."""
    # Test calls after hours: set for one run in the shell, never in .env
    if os.getenv("RIA_TEST_ANY_HOUR") == "1":
        return True
    start, end = calling_hours()
    now = datetime.now(IST)
    if not start <= now.hour < end:
        return False
    rules = rules or {}
    hhmm = now.strftime("%H:%M")
    return rules.get("starthour", "00:00") <= hhmm < rules.get("endhour", "24:00")


def utc_now() -> str:
    # With the offset: PostgreSQL would read a bare time as the server's local time
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Dialer:
    def __init__(self, db: DatabaseDriver) -> None:
        self.db = db
        # Imported call sheets are dialed right away; DIALER_START_PAUSED=1 holds them
        self.paused = os.getenv("DIALER_START_PAUSED", "0") == "1"
        self.trunk_id = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID", "").strip()
        self.concurrency = max(1, int(os.getenv("DIALER_CONCURRENCY", "1")))
        # Cost guard: hang up calls longer than this
        self.max_minutes = int(os.getenv("MAX_CALL_MINUTES", "5"))
        self.active: set[asyncio.Task] = set()
        # Shown on the dashboard so a stopped or failing dialer isn't mistaken for "ready"
        self.running = False
        self.error = ""

    def status(self) -> dict:
        start, end = calling_hours()
        return {
            "paused": self.paused,
            "configured": bool(self.trunk_id),
            "in_calling_hours": within_calling_hours(),
            "calling_hours": f"{start:02d}:00–{end:02d}:00 IST",
            "concurrency": self.concurrency,
            "max_minutes": self.max_minutes,
            "active": len(self.active),
            "running": self.running,
            "error": self.error,
        }

    def _save_heartbeat(self) -> None:
        try:
            self.db.set_system_state("dialer", self.status())
        except Exception:
            pass

    async def run(self) -> None:
        if not self.trunk_id:
            logger.warning("LIVEKIT_SIP_OUTBOUND_TRUNK_ID is missing; run setup_vobiz.py. Not dialing.")
            return
        await asyncio.to_thread(self.db.recover_stale_calls, self.max_minutes)
        lk = api.LiveKitAPI()
        self.running = True
        self._save_heartbeat()
        try:
            while True:
                try:
                    self._save_heartbeat()
                    free = self.concurrency - len(self.active)
                    if free > 0 and not self.paused and within_calling_hours():
                        # Retries and callbacks that are due join the calls to dial
                        await asyncio.to_thread(self.db.promote_due_callbacks)
                        queued = await asyncio.to_thread(self.db.queued_calls, free * 4)
                        for call in queued:
                            if free <= 0:
                                break
                            rules = (call.get("tenant_config") or {}).get("rules")
                            if not within_calling_hours(rules):
                                continue
                            if await asyncio.to_thread(self.db.claim_call, call["call_id"]):
                                task = asyncio.create_task(self._place_call(lk, call))
                                self.active.add(task)
                                task.add_done_callback(self.active.discard)
                                free -= 1
                    self.error = ""
                except Exception as exc:
                    # Keep dialing after a database or LiveKit hiccup instead of dying silently
                    logger.exception("Dialer loop failed; retrying")
                    self.error = str(exc)[:200] or type(exc).__name__
                    await asyncio.sleep(10)
                await asyncio.sleep(2)
        finally:
            self.running = False
            self._save_heartbeat()
            await lk.aclose()

    async def _place_call(self, lk: api.LiveKitAPI, call: dict) -> None:
        try:
            await self._dial(lk, call)
        except Exception:
            # Don't leave the row stuck in dialing/live on the dashboard
            logger.exception("Call %s: dialer error", call["call_id"])
            await asyncio.to_thread(self.db.end_collection_call, call["call_id"])

    async def _dial(self, lk: api.LiveKitAPI, call: dict) -> None:
        call_id = call["call_id"]
        room = f"call-out-{call_id[:12]}"
        logger.info("Calling %s %s for %s", call["customer_name"], call["phone"], call["invoice_no"])
        request = api.CreateSIPParticipantRequest(
            sip_trunk_id=self.trunk_id,
            sip_call_to=call["phone"],
            room_name=room,
            participant_identity=f"phone-{call['phone']}",
            participant_name=call["customer_name"],
            # The agent loads the invoice from the database by call_id
            participant_metadata=json.dumps({"call_id": call_id}),
            krisp_enabled=os.getenv("NOISE_CANCELLATION", "off").strip("\"' ").lower() not in ("off", "0", "false", "none", ""),
            wait_until_answered=True,
        )
        request.ringing_timeout.seconds = 30
        request.max_call_duration.seconds = self.max_minutes * 60
        try:
            await lk.sip.create_sip_participant(request)
        except Exception as exc:
            # The agent already joined the room; close it so RIA doesn't wait there
            await self._close_room(lk, room)
            if isinstance(exc, api.SipCallError):
                outcome = SIP_OUTCOMES.get(exc.sip_status_code or 0, "FAILED")
                notes = f"SIP {exc.sip_status_code} {exc.sip_status or ''}".strip()
            else:
                outcome, notes = "FAILED", str(getattr(exc, "message", exc))[:300]
            await asyncio.to_thread(
                self.db.save_collection_call,
                call_id, status="done", outcome=outcome, notes=notes, ended_at=utc_now(),
            )
            # Recorded here: no agent took part (retries are booked from the outcome)
            await asyncio.to_thread(self.db.finalize_call, call_id)
            logger.info("Call %s not answered: %s", call_id, outcome)
            return

        if not await self._agent_joined(lk, room, timeout=6):
            # RIA isn't in the call (the agent was down or turned it away): hang up at once
            # rather than leave the customer in silence (a call once ran 90 s like that),
            # and retry it like an unanswered call
            logger.warning("Call %s: RIA didn't join the call; hanging up, it will be retried", call_id)
            await self._close_room(lk, room)
            await asyncio.to_thread(
                self.db.save_collection_call, call_id, status="done", outcome="NO-ANSWER",
                notes="RIA didn't join the call; hung up at once and retried.", ended_at=utc_now(),
            )
            await asyncio.to_thread(self.db.finalize_call, call_id)
            return

        await self._wait_for_room_close(lk, room, self.max_minutes * 60 + 60)
        # Give the agent a moment to write the outcome after the line drops
        for _ in range(10):
            row = await asyncio.to_thread(self.db.get_collection_call, call_id)
            if not row or row["status"] == "done":
                return
            await asyncio.sleep(1)
        await asyncio.to_thread(self.db.end_collection_call, call_id)

    async def _agent_joined(self, lk: api.LiveKitAPI, room: str, timeout: float) -> bool:
        """RIA is in the room, or joins within `timeout` s (she normally joins while it rings)."""
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            try:
                people = (await lk.room.list_participants(api.ListParticipantsRequest(room=room))).participants
            except Exception:
                return True  # can't tell (the room may be gone already): never hang up on a guess
            if any(p.kind == api.ParticipantInfo.Kind.AGENT for p in people):
                return True
            if asyncio.get_running_loop().time() >= deadline:
                return False
            await asyncio.sleep(0.5)

    async def _wait_for_room_close(self, lk: api.LiveKitAPI, room: str, limit: float) -> None:
        deadline = asyncio.get_running_loop().time() + limit
        while asyncio.get_running_loop().time() < deadline:
            rooms = await lk.room.list_rooms(api.ListRoomsRequest(names=[room]))
            if not rooms.rooms:
                return
            await asyncio.sleep(3)
        await self._close_room(lk, room)

    async def _close_room(self, lk: api.LiveKitAPI, room: str) -> None:
        try:
            await lk.room.delete_room(api.DeleteRoomRequest(room=room))
        except Exception:
            pass  # already gone


if __name__ == "__main__":
    import signal
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("🚀 Starting RIA standalone dialer daemon...")

    db = DatabaseDriver()
    d = Dialer(db)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    stop_event = asyncio.Event()

    def handle_exit(sig, frame):
        logger.info("Received exit signal (%s); initiating graceful shutdown...", sig)
        d.running = False
        loop.call_soon_threadsafe(stop_event.set)

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(Exception):
            signal.signal(sig, handle_exit)

    async def main():
        dialer_task = asyncio.create_task(d.run())
        await stop_event.wait()
        dialer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await dialer_task

    try:
        loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("Dialer daemon stopped.")
