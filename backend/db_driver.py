"""PostgreSQL access for the agent, the dialer and the dashboard API.

Tables come from database/schema.sql (the ria-ui schema) plus our migrations.
Every dial is a row in outbound_calls: the dashboard queues it, the dialer
places it, the agent fills in the outcome, and finalize_call() then turns it
into what the dashboard shows: a `calls` record with the transcript, and a
promise to pay, ticket, retry or callback where the outcome calls for one.

Set DATABASE_URL in backend/.env (postgresql://user:pass@host:5432/ria_db).
"""
import atexit
import os
import re
import secrets
import threading
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone

from psycopg.rows import dict_row
from psycopg.types.json import Json
from psycopg_pool import ConnectionPool

IST = timezone(timedelta(hours=5, minutes=30))

# Language codes RIA works with <-> the names the dashboard shows
LANGUAGE_NAMES = {
    "te": "Telugu", "hi": "Hindi", "en": "English", "ta": "Tamil", "kn": "Kannada",
    "ml": "Malayalam", "mr": "Marathi", "bn": "Bengali", "gu": "Gujarati", "pa": "Punjabi", "or": "Odia",
}
LANGUAGE_CODES = {name.lower(): code for code, name in LANGUAGE_NAMES.items()}

# The call's outcome as the dashboard words it (calls.disposition)
OUTCOME_LABELS = {
    "PROMISE-TO-PAY": "PTP given",
    "ALREADY-PAID": "Already paid",
    "DISPUTE": "Payment dispute",
    "CALLBACK": "Callback requested",
    "REQUEST": "Request raised",
    "REFUSED": "Refused to pay",
    "WRONG-PERSON": "Wrong number",
    "OPT-OUT": "Do not call",
    "NO-ANSWER": "Call not lifted",
    "BUSY": "Line busy",
    "FAILED": "Call failed",
    "DISCONNECTED": "Disconnected",
}
# Ticket types the agent records (ria/outcomes.py) -> ticket category and severity
TICKETS = {
    "payment_refusal": ("Payment refusal", "High"),
    "invoice_dispute": ("Dispute raised", "High"),
    "customer_complaint": ("Customer complaint", "High"),
    "payment_verification": ("Already-paid claim", "Medium"),
    "part_payment_request": ("Part payment request", "Medium"),
    "payment_arrangement_request": ("Payment arrangement request", "Medium"),
    "credit_note_request": ("Credit note request", "Low"),
    "account_adjustment": ("Account adjustment", "Low"),
    "account_statement_or_ledger": ("Ledger / statement request", "Low"),
    "accounts_callback": ("Asked for person", "Medium"),
    "master_data_correction": ("Wrong number — update contact", "Low"),
}
TICKET_RE = re.compile(r"\|\s*ticket:\s*([a-z_]+)")
# Outcomes that mean nobody took the call: retried after the tenant's cooldown
UNANSWERED = ("NO-ANSWER", "BUSY")
# The old outbound_calls column names the agent and dialer still use
FIELD_NAMES = {"invoice_no": "invoice_number", "business": "business_name"}
CALL_FIELDS = frozenset((
    "status", "outcome", "promised_date", "promised_amount", "notes", "language",
    "answered_at", "ended_at", "phone", "scheduled_for", "caller_id",
))


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def language_code(value: str | None, default: str = "") -> str:
    value = (value or "").strip()
    return value if value in LANGUAGE_NAMES else LANGUAGE_CODES.get(value.lower(), default)


def duration_display(seconds: int) -> str:
    return f"{seconds // 60}m {seconds % 60}s"


# A clock time in the agent's callback notes ("after 4 PM", "11:30 am")
CLOCK_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\b", re.I)


# A "payment date unknown" outcome is saved as a callback with this label in its notes
OUTCOME_LABELS_DATE_UNKNOWN = "Payment date unknown"
DATE_UNKNOWN_FOLLOW_UP_DAYS = 3


def noted_time(notes: str | None) -> str | None:
    """'16:00' for "Call after 4 PM", or None."""
    m = CLOCK_RE.search(notes or "")
    if not m:
        return None
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    return f"{hour:02d}:{int(m.group(2) or 0):02d}"


def ist_time(day: date, hhmm: str) -> datetime:
    hour, minute = (int(x) for x in (hhmm or "10:00").split(":")[:2])
    return datetime.combine(day, time(hour, minute), IST)


class DatabaseDriver:
    """One pool per process: the agent runs each call in its own process, so the
    pool is opened on first use rather than at import (a pool can't cross a fork)."""

    def __init__(self, url: str | None = None):
        self.url = url or os.getenv("DATABASE_URL", "").strip()
        if not self.url:
            raise RuntimeError("DATABASE_URL is missing from backend/.env (see sample.env)")
        self._pool: ConnectionPool | None = None
        self._pid = 0
        self._lock = threading.Lock()

    def close(self) -> None:
        if self._pool is not None and self._pid == os.getpid():
            self._pool.close()
            self._pool = None

    @contextmanager
    def connection(self):
        with self._lock:
            if self._pool is None or self._pid != os.getpid():
                self._pool = ConnectionPool(
                    self.url, min_size=1, max_size=int(os.getenv("DB_POOL_SIZE", "10")),
                    kwargs={"row_factory": dict_row, "autocommit": True}, open=True,
                )
                self._pid = os.getpid()
                atexit.register(self.close)
        with self._pool.connection() as conn:
            yield conn

    # -- a single call, as the agent and dialer see it ----------------------------

    CALL_SELECT = """
        SELECT o.id AS call_id, o.*, o.invoice_number AS invoice_no, o.business_name AS business,
               t.name AS company, t.config AS tenant_config,
               call_invoice.amount AS invoice_amount, call_retailer.last_ptp_date AS previous_promised_date,
               call_retailer.code AS customer_code
        FROM outbound_calls o JOIN tenants t ON t.id = o.tenant_id
        LEFT JOIN invoices call_invoice ON call_invoice.id = o.invoice_id
        LEFT JOIN retailers call_retailer ON call_retailer.id = o.retailer_id
    """

    @staticmethod
    def _call_row(row: dict | None) -> dict | None:
        if not row:
            return None
        row = dict(row)
        row["amount"] = float(row["amount"])
        row["due_date"] = row["due_date"].isoformat()
        if row.get("invoice_amount") is not None:
            row["invoice_amount"] = float(row["invoice_amount"])
        if row.get("previous_promised_date") is not None:
            row["previous_promised_date"] = row["previous_promised_date"].isoformat()
        if row.get("promised_amount") is not None:
            row["promised_amount"] = float(row["promised_amount"])
        if row.get("promised_date") is not None:
            row["promised_date"] = row["promised_date"].isoformat()
        return row

    def get_collection_call(self, call_id: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute(self.CALL_SELECT + " WHERE o.id = %s", (call_id,)).fetchone()
        return self._call_row(row)

    def save_collection_call(self, call_id: str, **fields) -> None:
        """Updates a call; only the given fields change."""
        fields = {FIELD_NAMES.get(k, k): v for k, v in fields.items()}
        unknown = set(fields) - CALL_FIELDS
        if unknown:
            raise ValueError(f"unknown outbound_calls fields: {sorted(unknown)}")
        if not fields:
            return
        sets = ", ".join(f"{column} = %s" for column in fields)
        with self.connection() as conn:
            conn.execute(f"UPDATE outbound_calls SET {sets} WHERE id = %s", (*fields.values(), call_id))

    def end_collection_call(self, call_id: str, turns: list[dict] | None = None, recording: str | None = None) -> None:
        """Marks the call done (DISCONNECTED if no outcome was saved) and records it."""
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE outbound_calls SET status = 'done',
                    ended_at = COALESCE(ended_at, CURRENT_TIMESTAMP),
                    outcome = COALESCE(outcome, CASE WHEN answered_at IS NULL THEN 'NO-ANSWER' ELSE 'DISCONNECTED' END)
                WHERE id = %s AND status NOT IN ('done', 'cancelled')
                """,
                (call_id,),
            )
        self.finalize_call(call_id, turns, recording)

    def latest_call_for_phone(self, phone: str) -> dict | None:
        """The most recent invoice discussed with this number (for inbound callbacks)."""
        with self.connection() as conn:
            row = conn.execute(
                self.CALL_SELECT + " WHERE o.phone = %s ORDER BY o.created_at DESC LIMIT 1", (phone,)
            ).fetchone()
        return self._call_row(row)

    def start_inbound_call(self, latest: dict) -> str:
        """A new call row for a customer calling back about the invoice in `latest`."""
        call_id = secrets.token_hex(16)
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO outbound_calls (id, tenant_id, batch_id, retailer_id, invoice_id, customer_name,
                    business_name, phone, language, invoice_number, amount, due_date, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'dialing', 'Inbound call')
                """,
                (call_id, latest["tenant_id"], latest["batch_id"], latest["retailer_id"], latest["invoice_id"],
                 latest["customer_name"], latest["business"], latest["phone"], latest["language"],
                 latest["invoice_no"], latest["amount"], latest["due_date"]),
            )
        return call_id

    # -- the dialer -----------------------------------------------------------------

    def promote_due_callbacks(self, limit: int = 20) -> int:
        """Turns retries and callbacks that are due into calls to dial.

        SKIP LOCKED, so two dialers never take the same item.
        """
        with self.connection() as conn, conn.transaction():
            items = conn.execute(
                """
                SELECT q.* FROM call_reschedule_queue q
                JOIN retailers r ON r.id = q.retailer_id
                WHERE q.status = 'Queued' AND q.scheduled_for <= CURRENT_TIMESTAMP AND NOT r.do_not_call
                ORDER BY q.priority = 'High' DESC, q.scheduled_for
                LIMIT %s FOR UPDATE OF q SKIP LOCKED
                """,
                (limit,),
            ).fetchall()
            for item in items:
                # What the call is about: the dial it follows up, else the oldest unpaid invoice
                source = conn.execute(
                    """
                    SELECT o.* FROM outbound_calls o JOIN calls c ON c.outbound_call_id = o.id
                    WHERE c.id = %s LIMIT 1
                    """,
                    (item["source_call_id"],),
                ).fetchone() if item["source_call_id"] else None
                if source is None:
                    source = conn.execute(
                        """
                        SELECT i.id AS invoice_id, i.invoice_number, i.due_amount AS amount, i.due_date,
                               r.business_name, r.preferred_lang AS language
                        FROM invoices i JOIN retailers r ON r.id = i.retailer_id
                        WHERE i.retailer_id = %s AND i.status IN ('unpaid', 'partially_paid')
                        ORDER BY i.due_date LIMIT 1
                        """,
                        (item["retailer_id"],),
                    ).fetchone()
                if source is None:
                    conn.execute(
                        "UPDATE call_reschedule_queue SET status = 'Cancelled', last_outcome = %s WHERE id = %s",
                        ("No unpaid invoice left to call about", item["id"]),
                    )
                    continue
                conn.execute(
                    """
                    INSERT INTO outbound_calls (id, tenant_id, batch_id, retailer_id, invoice_id, queue_id,
                        customer_name, business_name, phone, language, invoice_number, amount, due_date, attempt)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (secrets.token_hex(16), item["tenant_id"], item["batch_id"], item["retailer_id"],
                     source["invoice_id"], item["id"], item["customer_name"], source["business_name"],
                     item["phone"], language_code(source["language"]), source["invoice_number"],
                     source["amount"], source["due_date"], item["attempt_number"]),
                )
                conn.execute(
                    "UPDATE call_reschedule_queue SET status = 'Dialing', dialed_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (item["id"],),
                )
        return len(items)

    # A queued call the dialer may place: not in a batch, a retry or callback, a
    # "Call now", or part of a batch someone started on the Call Campaign screen
    READY_TO_DIAL = """
        o.status = 'queued' AND o.scheduled_for <= CURRENT_TIMESTAMP AND NOT r.do_not_call
        AND (o.batch_id IS NULL OR o.queue_id IS NOT NULL OR o.dial_now OR b.dialing)
    """
    # "Call now" first, then in the order of the call sheet
    DIAL_ORDER = "o.dial_now DESC, o.scheduled_for, o.seq"

    def queued_calls(self, limit: int) -> list[dict]:
        """Calls to dial now, in order, skipping customers who said "don't call"."""
        with self.connection() as conn:
            rows = conn.execute(
                self.CALL_SELECT + f"""
                JOIN retailers r ON r.id = o.retailer_id
                LEFT JOIN call_batches b ON b.id = o.batch_id
                WHERE {self.READY_TO_DIAL}
                ORDER BY {self.DIAL_ORDER} LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [self._call_row(r) for r in rows]

    def claim_call(self, call_id: str) -> bool:
        """Moves a queued call to dialing; False if someone else got it first."""
        with self.connection() as conn:
            cur = conn.execute(
                "UPDATE outbound_calls SET status = 'dialing', dialed_at = CURRENT_TIMESTAMP "
                "WHERE id = %s AND status = 'queued'", (call_id,)
            )
            if cur.rowcount and (batch := conn.execute(
                "SELECT batch_id FROM outbound_calls WHERE id = %s", (call_id,)
            ).fetchone()["batch_id"]):
                conn.execute(
                    "UPDATE call_batches SET status = 'In Progress' WHERE id = %s AND status = 'Scheduled'", (batch,)
                )
            return cur.rowcount > 0

    def recover_stale_calls(self, max_minutes: int) -> None:
        """Closes calls a previous dialer left behind (server restarted mid-call)."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                UPDATE outbound_calls SET status = 'done', ended_at = CURRENT_TIMESTAMP,
                    outcome = COALESCE(outcome, 'FAILED'),
                    notes = COALESCE(notes, 'dialer restarted during the call')
                WHERE status = 'dialing'
                    OR (status = 'live' AND answered_at < CURRENT_TIMESTAMP - make_interval(mins => %s))
                RETURNING id
                """,
                (max_minutes + 5,),
            ).fetchall()
        for row in rows:
            self.finalize_call(row["id"])

    # -- recording a finished call --------------------------------------------------

    def finalize_call(self, call_id: str, turns: list[dict] | None = None, recording: str | None = None) -> None:
        """Records a finished dial for the dashboard (once; later calls do nothing).
        `recording`: the call's audio file name in backend/recordings."""
        with self.connection() as conn, conn.transaction():
            o = conn.execute(
                "SELECT o.*, t.config FROM outbound_calls o JOIN tenants t ON t.id = o.tenant_id "
                "WHERE o.id = %s AND o.status = 'done' AND o.call_record_id IS NULL FOR UPDATE OF o",
                (call_id,),
            ).fetchone()
            if o is None:
                return
            rules = (o["config"] or {}).get("rules", {})
            outcome = o["outcome"] or "DISCONNECTED"
            answered = o["answered_at"] is not None
            seconds = int((o["ended_at"] - o["answered_at"]).total_seconds()) if answered and o["ended_at"] else 0
            label = OUTCOME_LABELS.get(outcome, outcome.title())
            notes = o["notes"] or ""
            ticket = (m.group(1) if (m := TICKET_RE.search(notes)) else "")
            clean_notes = TICKET_RE.split(notes)[0].strip(" |") or None
            promised_amount = o["promised_amount"] or (o["amount"] if outcome == "PROMISE-TO-PAY" else None)

            record_id = new_id("CL")
            conn.execute(
                """
                INSERT INTO calls (id, created_at, batch_id, retailer_id, customer_name, phone, language,
                    duration_seconds, duration_display, disposition, ptp_committed_date, ptp_amount,
                    turns, ai_summary, tenant_id, outbound_call_id, invoice_number, outcome, notes,
                    audio_recording_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (record_id, o["answered_at"] or o["created_at"], o["batch_id"], o["retailer_id"],
                 o["customer_name"], o["phone"], LANGUAGE_NAMES.get(o["language"], "Telugu"), seconds,
                 duration_display(seconds), label, o["promised_date"] if outcome == "PROMISE-TO-PAY" else None,
                 promised_amount if outcome == "PROMISE-TO-PAY" else None, Json(turns or []),
                 clean_notes, o["tenant_id"], o["id"], o["invoice_number"], outcome, notes or None,
                 recording),
            )
            conn.execute("UPDATE outbound_calls SET call_record_id = %s WHERE id = %s", (record_id, o["id"]))

            # The retailer's 360 view: last contact, promise and "don't call" flag
            conn.execute(
                """
                UPDATE retailers SET last_call_at = %s, last_disposition = %s,
                    last_ptp_date = COALESCE(%s, last_ptp_date),
                    do_not_call = do_not_call OR %s,
                    do_not_call_at = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE do_not_call_at END
                WHERE id = %s
                """,
                (o["ended_at"], self._retailer_disposition(conn, o, label, outcome),
                 o["promised_date"] if outcome == "PROMISE-TO-PAY" else None,
                 outcome == "OPT-OUT", outcome == "OPT-OUT", o["retailer_id"]),
            )
            if outcome == "PROMISE-TO-PAY" and o["promised_date"]:
                conn.execute(
                    """
                    INSERT INTO ptp_commitments (id, retailer_id, source_call_id, customer_name, phone,
                        amount, due_date, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (new_id("PTP"), o["retailer_id"], record_id, o["customer_name"], o["phone"],
                     promised_amount, o["promised_date"],
                     "due" if o["promised_date"] <= datetime.now(IST).date() else "upcoming"),
                )
            if ticket in TICKETS:
                category, severity = TICKETS[ticket]
                conn.execute(
                    """
                    INSERT INTO tickets (id, tenant_id, retailer_id, source_call_id, customer_name,
                        category, severity, resolution_note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (new_id("E"), o["tenant_id"], o["retailer_id"], record_id, o["customer_name"],
                     category, severity, clean_notes),
                )
            self._follow_up(conn, o, outcome, record_id, rules, clean_notes)
            if o["batch_id"]:
                self._update_batch(conn, o["batch_id"])

            # Deduct calling credits: exactly ₹3.00/min (5 paise/sec) for spoken time only.
            # Ringing time is NOT counted; unanswered calls (BUSY, NO-ANSWER, FAILED) cost ₹0.
            if answered and seconds > 0 and o.get("tenant_id"):
                cost_paise = int(seconds * 5)
                w_row = conn.execute(
                    """
                    UPDATE tenant_wallets
                    SET balance_paise = GREATEST(0, balance_paise - %s), updated_at = CURRENT_TIMESTAMP
                    WHERE tenant_id = %s
                    RETURNING balance_paise
                    """,
                    (cost_paise, o["tenant_id"]),
                ).fetchone()
                balance_after = int(w_row["balance_paise"]) if w_row and w_row.get("balance_paise") is not None else 0
                ledger_id = f"led_{secrets.token_hex(8)}"
                cust_desc = o.get("customer_name") or o.get("phone") or "Customer"
                desc = f"Call to {cust_desc} ({duration_display(seconds)} @ ₹3/min)"
                conn.execute(
                    """
                    INSERT INTO wallet_ledger (id, tenant_id, type, amount_paise, balance_after_paise, description)
                    VALUES (%s, %s, 'call_burn', %s, %s, %s)
                    """,
                    (ledger_id, o["tenant_id"], -cost_paise, balance_after, desc),
                )

    @staticmethod
    def _retailer_disposition(conn, o: dict, label: str, outcome: str) -> str:
        if outcome not in UNANSWERED:
            return label
        tries = conn.execute(
            "SELECT COUNT(*) AS n FROM outbound_calls WHERE retailer_id = %s AND invoice_id IS NOT DISTINCT FROM %s "
            "AND outcome IN ('NO-ANSWER', 'BUSY') AND created_at >= CURRENT_DATE - 1",
            (o["retailer_id"], o["invoice_id"]),
        ).fetchone()["n"]
        return f"{label} ({tries} attempts)"

    @staticmethod
    def _follow_up(conn, o: dict, outcome: str, record_id: str, rules: dict, notes: str | None) -> None:
        """Retries an unanswered call after the cooldown, books a requested callback,
        and closes the queue item a retry or callback came from."""
        cap = int(rules.get("cap", 3))
        cooldown = int(rules.get("cooldown_minutes", 5))
        now = datetime.now(IST)
        if outcome == "CALLBACK":
            # No day from the customer: RIA picks one (a date-unknown follow-up waits a few days)
            unknown_date = (notes or "").startswith(OUTCOME_LABELS_DATE_UNKNOWN)
            day = o["promised_date"] or (now + timedelta(days=DATE_UNKNOWN_FOLLOW_UP_DAYS if unknown_date else 1)).date()
            # The time the customer asked for, inside calling hours: too late a time goes to
            # the next day's first hour, never earlier than asked (8 PM was booked at 7 PM)
            start, end = rules.get("starthour", "00:00"), rules.get("endhour", "23:59")
            hhmm = noted_time(notes) or rules.get("starthour", "10:00")
            if hhmm >= end:
                day, hhmm = day + timedelta(days=1), start
            hhmm = max(hhmm, start)
            when = max(ist_time(day, hhmm), now + timedelta(minutes=cooldown))
            kind, attempt, priority = "customer_requested", 1, "High"
            if unknown_date:
                note = f"No payment date yet; RIA follows up. {notes or ''}".strip()
                last = f"Follow-up scheduled for {when:%d %b %I:%M %p} (no payment date given)"
            elif not o["promised_date"] and not noted_time(notes):
                note = f"Customer asked to be called back. {notes or ''}".strip()
                last = f"Callback scheduled for {when:%d %b %I:%M %p} (customer gave no time)"
            else:
                note = f"Customer asked to be called back. {notes or ''}".strip()
                last = f"Callback requested for {when:%d %b %I:%M %p}"
        elif outcome in UNANSWERED:
            attempt = o["attempt"] + 1
            when, priority = now + timedelta(minutes=cooldown), "High" if o["attempt"] == 1 else "Medium"
            kind = "busy_retry" if outcome == "BUSY" else "no_lift_retry"
            note = f"{OUTCOME_LABELS[outcome]} at {now:%I:%M %p}. Retry #{attempt - 1} in {cooldown} mins."
            last = f"{OUTCOME_LABELS[outcome]} (Attempt #{o['attempt']})"
        else:
            kind = None

        if o["queue_id"]:
            if kind is None:
                conn.execute(
                    "UPDATE call_reschedule_queue SET status = 'Completed', last_outcome = %s, source_call_id = %s "
                    "WHERE id = %s",
                    (OUTCOME_LABELS.get(outcome, outcome), record_id, o["queue_id"]),
                )
                return
            exhausted = kind != "customer_requested" and o["attempt"] >= cap
            conn.execute(
                """
                UPDATE call_reschedule_queue SET status = %s, type = %s, scheduled_for = %s,
                    attempt_number = %s, ai_note = %s, last_outcome = %s, source_call_id = %s, priority = %s
                WHERE id = %s
                """,
                ("Exhausted" if exhausted else "Queued", kind, when, attempt,
                 f"No answer after {cap} attempts. Recommend a field visit." if exhausted else note,
                 f"Max retries exceeded ({cap} attempts)" if exhausted else last, record_id, priority,
                 o["queue_id"]),
            )
            return
        if kind is None or (kind != "customer_requested" and o["attempt"] >= cap):
            return
        pending = conn.execute(
            "SELECT id FROM call_reschedule_queue WHERE tenant_id = %s AND retailer_id = %s "
            "AND type = 'customer_requested' AND status = 'Queued' ORDER BY created_at DESC",
            (o["tenant_id"], o["retailer_id"]),
        ).fetchall() if kind == "customer_requested" else []
        if pending:
            # One callback per customer: the latest time asked for moves the pending one (two
            # test calls left two callbacks at the same 8 AM), and any extra is cancelled
            conn.execute(
                """
                UPDATE call_reschedule_queue SET scheduled_for = %s, source_call_id = %s, ai_note = %s,
                    last_outcome = %s, priority = %s, batch_id = COALESCE(%s, batch_id)
                WHERE id = %s
                """,
                (when, record_id, note, last, priority, o["batch_id"], pending[0]["id"]),
            )
            if len(pending) > 1:
                conn.execute(
                    "UPDATE call_reschedule_queue SET status = 'Cancelled', ai_note = 'Replaced by a later callback' "
                    "WHERE id = ANY(%s)", ([row["id"] for row in pending[1:]],),
                )
            return
        conn.execute(
            """
            INSERT INTO call_reschedule_queue (id, tenant_id, retailer_id, batch_id, source_call_id,
                customer_name, phone, outstanding_amount, type, priority, scheduled_for, attempt_number,
                max_attempts, ai_note, last_outcome)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (new_id("SCH"), o["tenant_id"], o["retailer_id"], o["batch_id"], record_id, o["customer_name"],
             o["phone"], o["amount"], kind, priority, when, attempt, cap, note, last),
        )

    @staticmethod
    def _update_batch(conn, batch_id: str) -> None:
        """Batch totals from its calls, so they stay right however often this runs."""
        conn.execute(
            """
            WITH last_call AS (
                SELECT DISTINCT ON (o.retailer_id, o.invoice_id) o.outcome
                FROM outbound_calls o WHERE o.batch_id = %(b)s AND o.status = 'done'
                ORDER BY o.retailer_id, o.invoice_id, o.created_at DESC
            ), totals AS (
                SELECT
                    (SELECT COUNT(*) FROM outbound_calls WHERE batch_id = %(b)s AND attempt = 1
                        AND queue_id IS NULL AND status IN ('done', 'cancelled')) AS completed,
                    (SELECT COUNT(DISTINCT retailer_id) FROM calls WHERE batch_id = %(b)s AND duration_seconds > 0) AS connected,
                    (SELECT COUNT(*) FROM calls WHERE batch_id = %(b)s AND outcome = 'PROMISE-TO-PAY') AS ptps,
                    (SELECT COALESCE(SUM(ptp_amount), 0) FROM calls WHERE batch_id = %(b)s AND outcome = 'PROMISE-TO-PAY') AS ptp_amount,
                    (SELECT COUNT(*) FROM calls WHERE batch_id = %(b)s AND outcome = 'DISPUTE') AS disputes,
                    (SELECT COUNT(*) FROM last_call WHERE outcome IN ('NO-ANSWER', 'BUSY')) AS no_lift,
                    EXISTS (SELECT 1 FROM outbound_calls WHERE batch_id = %(b)s AND status IN ('queued', 'dialing', 'live'))
                        OR EXISTS (SELECT 1 FROM call_reschedule_queue WHERE batch_id = %(b)s AND status IN ('Queued', 'Dialing'))
                        AS busy
            )
            UPDATE call_batches SET completed_calls = completed, connected_calls = connected, ptp_count = ptps,
                ptp_amount = totals.ptp_amount, dispute_count = disputes, no_lift_count = no_lift,
                status = CASE WHEN busy THEN 'In Progress' ELSE 'Completed' END::batch_status_enum,
                completed_at = CASE WHEN busy THEN NULL ELSE COALESCE(completed_at, CURRENT_TIMESTAMP) END
            FROM totals WHERE id = %(b)s
            """,
            {"b": batch_id},
        )

    # -- checks before queueing -----------------------------------------------------

    def has_opted_out(self, tenant_id: str, phone: str) -> bool:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM retailers WHERE tenant_id = %s AND phone = %s AND do_not_call LIMIT 1",
                (tenant_id, phone),
            ).fetchone()
        return row is not None

    def call_waiting(self, tenant_id: str, phone: str, invoice_no: str) -> bool:
        """True if a call about this invoice is waiting to be dialled or on the line."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM outbound_calls WHERE tenant_id = %s AND phone = %s AND invoice_number = %s "
                "AND status IN ('queued', 'dialing', 'live') LIMIT 1",
                (tenant_id, phone, invoice_no),
            ).fetchone()
        return row is not None

    def last_discussed(self, tenant_id: str, phone: str, invoice_no: str, hours: int = 20) -> dict | None:
        """The latest answered call about this invoice in the last `hours`, if any."""
        with self.connection() as conn:
            return conn.execute(
                """
                SELECT answered_at, outcome FROM outbound_calls
                WHERE tenant_id = %s AND phone = %s AND invoice_number = %s AND answered_at IS NOT NULL
                    AND created_at >= CURRENT_TIMESTAMP - make_interval(hours => %s)
                ORDER BY answered_at DESC LIMIT 1
                """,
                (tenant_id, phone, invoice_no, hours),
            ).fetchone()

    def called_recently(self, tenant_id: str, phone: str, invoice_no: str, hours: int = 20) -> bool:
        """True if this invoice is queued, on a call, or was discussed recently."""
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM outbound_calls
                WHERE tenant_id = %s AND phone = %s AND invoice_number = %s AND (
                    status IN ('queued', 'dialing', 'live')
                    OR (answered_at IS NOT NULL AND created_at >= CURRENT_TIMESTAMP - make_interval(hours => %s))
                )
                LIMIT 1
                """,
                (tenant_id, phone, invoice_no, hours),
            ).fetchone()
        return row is not None

    # -- system state & daemon heartbeats ------------------------------------------

    def set_system_state(self, key: str, value: dict) -> None:
        """Saves a daemon heartbeat or cluster-wide setting (upsert)."""
        try:
            with self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO system_state (key, value, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                    """,
                    (key, Json(value)),
                )
        except Exception:
            # Safe failover if migration has not run yet
            pass

    def get_system_state(self, key: str, max_age_seconds: int = 30) -> dict | None:
        """Fetches system state for `key`. Checks freshness against `max_age_seconds`."""
        try:
            with self.connection() as conn:
                row = conn.execute(
                    "SELECT value, updated_at FROM system_state WHERE key = %s",
                    (key,),
                ).fetchone()
                if not row:
                    return None
                val = dict(row["value"]) if isinstance(row["value"], dict) else {}
                if row.get("updated_at"):
                    val["updated_at"] = row["updated_at"].isoformat()
                    age = (datetime.now(timezone.utc) - row["updated_at"].astimezone(timezone.utc)).total_seconds()
                    val["is_stale"] = age > max_age_seconds if max_age_seconds > 0 else False
                    val["age_seconds"] = round(age, 1)
                return val
        except Exception:
            return None

    # -- dynamic telephony numbers pool --------------------------------------------

    def ensure_telephony_tables(self) -> None:
        """Ensures telephony_numbers table and caller_id column exist, seeded with default lines."""
        with self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS telephony_numbers (
                    id VARCHAR(50) PRIMARY KEY,
                    phone_number VARCHAR(30) UNIQUE NOT NULL,
                    label VARCHAR(100) DEFAULT '',
                    status VARCHAR(20) DEFAULT 'active',
                    daily_limit INT DEFAULT 250,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_telephony_status ON telephony_numbers (status);
                ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS caller_id VARCHAR(30);
                CREATE INDEX IF NOT EXISTS idx_outbound_caller_id ON outbound_calls (caller_id, created_at);
                """
            )
            # Seed default 5 Vobiz numbers if empty
            count = conn.execute("SELECT COUNT(*) AS n FROM telephony_numbers").fetchone()["n"]
            if count == 0:
                conn.execute(
                    """
                    INSERT INTO telephony_numbers (id, phone_number, label, status, daily_limit)
                    VALUES 
                        ('num_8064269997', '+918064269997', 'Bangalore Line 1', 'active', 250),
                        ('num_8064269994', '+918064269994', 'Bangalore Line 2', 'active', 250),
                        ('num_8064269993', '+918064269993', 'Bangalore Line 3', 'active', 250),
                        ('num_8064269991', '+918064269991', 'Bangalore Line 4', 'active', 250),
                        ('num_8065382786', '+918065382786', 'Bangalore Line 5', 'active', 250)
                    ON CONFLICT (phone_number) DO NOTHING;
                    """
                )

    def get_active_telephony_numbers(self) -> list[str]:
        """Returns list of active phone number strings."""
        self.ensure_telephony_tables()
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT phone_number FROM telephony_numbers WHERE status = 'active' ORDER BY created_at ASC"
            ).fetchall()
        return [r["phone_number"] for r in rows]

    def get_active_telephony_pool(self) -> list[dict]:
        """Returns active numbers with their calls today and daily limits."""
        self.ensure_telephony_tables()
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT tn.phone_number, tn.daily_limit, COALESCE(daily.calls_today, 0) AS calls_today
                FROM telephony_numbers tn
                LEFT JOIN (
                    SELECT caller_id, COUNT(*) AS calls_today
                    FROM outbound_calls
                    WHERE created_at >= CURRENT_DATE
                    GROUP BY caller_id
                ) daily ON daily.caller_id = tn.phone_number
                WHERE tn.status = 'active'
                ORDER BY tn.created_at ASC
                """
            ).fetchall()
        return [
            {
                "phone_number": r["phone_number"],
                "daily_limit": int(r["daily_limit"] or 250),
                "calls_today": int(r["calls_today"] or 0),
            }
            for r in rows
        ]

    # -- billing, plans, and wallet credits ----------------------------------------

    def ensure_billing_tables(self) -> None:
        """Ensures billing status, plans, wallet balances, and transaction logs exist."""
        with self.connection() as conn:
            conn.execute(
                """
                ALTER TABLE tenants ADD COLUMN IF NOT EXISTS billing_status VARCHAR(30) DEFAULT 'pending_platform_fee';
                ALTER TABLE tenants ADD COLUMN IF NOT EXISTS plan VARCHAR(30) DEFAULT 'starter';
                ALTER TABLE tenants ADD COLUMN IF NOT EXISTS platform_fee_paid_at TIMESTAMPTZ;

                -- Ensure existing tenants already in database prior to migration remain active
                UPDATE tenants SET billing_status = 'active' WHERE billing_status IS NULL;

                CREATE TABLE IF NOT EXISTS tenant_wallets (
                    tenant_id VARCHAR(50) PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
                    balance_paise BIGINT DEFAULT 0 CHECK (balance_paise >= 0),
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );

                -- Initialize default ₹300 welcome credits (30,000 paise) for any active tenants lacking a wallet entry
                INSERT INTO tenant_wallets (tenant_id, balance_paise, updated_at)
                SELECT id, 30000, CURRENT_TIMESTAMP FROM tenants
                ON CONFLICT (tenant_id) DO NOTHING;

                CREATE TABLE IF NOT EXISTS billing_transactions (
                    id VARCHAR(50) PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    type VARCHAR(30) NOT NULL,
                    plan VARCHAR(30),
                    amount_paise BIGINT NOT NULL,
                    currency VARCHAR(10) DEFAULT 'INR',
                    status VARCHAR(20) NOT NULL,
                    razorpay_order_id VARCHAR(100),
                    razorpay_payment_id VARCHAR(100),
                    razorpay_signature VARCHAR(200),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_billing_tenant ON billing_transactions(tenant_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_billing_order ON billing_transactions(razorpay_order_id);

                CREATE TABLE IF NOT EXISTS wallet_ledger (
                    id VARCHAR(50) PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    type VARCHAR(30) NOT NULL,
                    amount_paise BIGINT NOT NULL,
                    balance_after_paise BIGINT NOT NULL,
                    description VARCHAR(255) DEFAULT '',
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_wallet_ledger_tenant ON wallet_ledger(tenant_id, created_at);
                """
            )

    def get_tenant_billing(self, tenant_id: str) -> dict:
        self.ensure_billing_tables()
        with self.connection() as conn:
            tenant = conn.execute(
                "SELECT billing_status, plan, platform_fee_paid_at FROM tenants WHERE id = %s",
                (tenant_id,),
            ).fetchone()
            wallet = conn.execute(
                "SELECT balance_paise FROM tenant_wallets WHERE tenant_id = %s",
                (tenant_id,),
            ).fetchone()
            balance_paise = int(wallet["balance_paise"]) if wallet and wallet.get("balance_paise") is not None else 0
            return {
                "billing_status": tenant["billing_status"] if tenant and tenant.get("billing_status") else "active",
                "plan": tenant["plan"] if tenant and tenant.get("plan") else "starter",
                "platform_fee_paid_at": tenant["platform_fee_paid_at"].isoformat() if tenant and tenant.get("platform_fee_paid_at") else None,
                "balance_paise": balance_paise,
                "balance_inr": balance_paise / 100.0,
            }

    def record_billing_order(self, tenant_id: str, plan_id: str, amount_paise: int, razorpay_order_id: str) -> str:
        self.ensure_billing_tables()
        tx_id = f"txn_{secrets.token_hex(8)}"
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO billing_transactions (id, tenant_id, type, plan, amount_paise, currency, status, razorpay_order_id)
                VALUES (%s, %s, 'platform_fee', %s, %s, 'INR', 'created', %s)
                """,
                (tx_id, tenant_id, plan_id, amount_paise, razorpay_order_id),
            )
        return tx_id

    def verify_and_activate_platform(
        self, tenant_id: str, plan_id: str, amount_paise: int, order_id: str,
        payment_id: str, signature: str, welcome_bonus_paise: int = 30000
    ) -> dict:
        self.ensure_billing_tables()
        with self.connection() as conn:
            with conn.transaction():
                # 1. Update billing transaction to captured
                conn.execute(
                    """
                    UPDATE billing_transactions
                    SET status = 'captured', razorpay_payment_id = %s, razorpay_signature = %s
                    WHERE razorpay_order_id = %s
                    """,
                    (payment_id, signature, order_id),
                )
                # 2. Activate tenant and assign plan
                conn.execute(
                    """
                    UPDATE tenants
                    SET billing_status = 'active', plan = %s, platform_fee_paid_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (plan_id, tenant_id),
                )
                # 3. Credit wallet balance with welcome credits (default ₹300 = 30,000 paise)
                conn.execute(
                    """
                    INSERT INTO tenant_wallets (tenant_id, balance_paise, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (tenant_id) DO UPDATE
                    SET balance_paise = tenant_wallets.balance_paise + %s, updated_at = CURRENT_TIMESTAMP
                    """,
                    (tenant_id, welcome_bonus_paise, welcome_bonus_paise),
                )
                # Fetch new balance
                w_row = conn.execute("SELECT balance_paise FROM tenant_wallets WHERE tenant_id = %s", (tenant_id,)).fetchone()
                balance_after = int(w_row["balance_paise"]) if w_row else welcome_bonus_paise

                # 4. Record ledger entry
                ledger_id = f"led_{secrets.token_hex(8)}"
                conn.execute(
                    """
                    INSERT INTO wallet_ledger (id, tenant_id, type, amount_paise, balance_after_paise, description)
                    VALUES (%s, %s, 'welcome_bonus', %s, %s, 'Welcome bonus calling credits (₹300)')
                    """,
                    (ledger_id, tenant_id, welcome_bonus_paise, balance_after),
                )

        return {
            "success": True,
            "billing_status": "active",
            "plan": plan_id,
            "balance_inr": balance_after / 100.0,
        }

    def tenant_has_calling_credits(self, tenant_id: str, min_paise: int = 150) -> bool:
        """Returns True if tenant has at least min_paise (default 150 paise = ₹1.50 = 30 seconds talk time)."""
        try:
            self.ensure_billing_tables()
            with self.connection() as conn:
                row = conn.execute(
                    "SELECT balance_paise FROM tenant_wallets WHERE tenant_id = %s",
                    (tenant_id,),
                ).fetchone()
                if not row or row.get("balance_paise") is None:
                    return False
                return int(row["balance_paise"]) >= min_paise
        except Exception:
            return True

    def record_topup_order(self, tenant_id: str, amount_paise: int, razorpay_order_id: str) -> str:
        self.ensure_billing_tables()
        tx_id = f"top_{secrets.token_hex(8)}"
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO billing_transactions (id, tenant_id, type, plan, amount_paise, currency, status, razorpay_order_id)
                VALUES (%s, %s, 'wallet_topup', NULL, %s, 'INR', 'created', %s)
                """,
                (tx_id, tenant_id, amount_paise, razorpay_order_id),
            )
        return tx_id

    def verify_and_topup_wallet(
        self, tenant_id: str, amount_paise: int, order_id: str, payment_id: str, signature: str
    ) -> dict:
        self.ensure_billing_tables()
        with self.connection() as conn:
            with conn.transaction():
                # 1. Update billing transaction
                conn.execute(
                    """
                    UPDATE billing_transactions
                    SET status = 'captured', razorpay_payment_id = %s, razorpay_signature = %s
                    WHERE razorpay_order_id = %s
                    """,
                    (payment_id, signature, order_id),
                )
                # 2. Add credits to wallet
                conn.execute(
                    """
                    INSERT INTO tenant_wallets (tenant_id, balance_paise, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (tenant_id) DO UPDATE
                    SET balance_paise = tenant_wallets.balance_paise + %s, updated_at = CURRENT_TIMESTAMP
                    """,
                    (tenant_id, amount_paise, amount_paise),
                )
                # 3. Fetch new balance
                w_row = conn.execute(
                    "SELECT balance_paise FROM tenant_wallets WHERE tenant_id = %s",
                    (tenant_id,),
                ).fetchone()
                balance_after = int(w_row["balance_paise"]) if w_row else amount_paise

                # 4. Record ledger entry
                ledger_id = f"led_{secrets.token_hex(8)}"
                conn.execute(
                    """
                    INSERT INTO wallet_ledger (id, tenant_id, type, amount_paise, balance_after_paise, description)
                    VALUES (%s, %s, 'topup', %s, %s, %s)
                    """,
                    (ledger_id, tenant_id, amount_paise, balance_after, f"Wallet top-up (₹{amount_paise / 100.0:.2f})"),
                )

        return {
            "success": True,
            "balance_paise": balance_after,
            "balance_inr": balance_after / 100.0,
        }

    def get_wallet_ledger(self, tenant_id: str, limit: int = 50) -> list[dict]:
        self.ensure_billing_tables()
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, type, amount_paise, balance_after_paise, description, created_at
                FROM wallet_ledger
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (tenant_id, limit),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "type": r["type"],
                    "amount_paise": int(r["amount_paise"]),
                    "amount_inr": r["amount_paise"] / 100.0,
                    "balance_after_paise": int(r["balance_after_paise"]),
                    "balance_after_inr": r["balance_after_paise"] / 100.0,
                    "description": r["description"] or "",
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]

    def get_billing_transactions(self, tenant_id: str, limit: int = 20) -> list[dict]:
        self.ensure_billing_tables()
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, type, plan, amount_paise, currency, status, razorpay_order_id, razorpay_payment_id, created_at
                FROM billing_transactions
                WHERE tenant_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (tenant_id, limit),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    "type": r["type"],
                    "plan": r["plan"],
                    "amount_paise": int(r["amount_paise"]),
                    "amount_inr": r["amount_paise"] / 100.0,
                    "currency": r["currency"] or "INR",
                    "status": r["status"],
                    "order_id": r["razorpay_order_id"],
                    "payment_id": r["razorpay_payment_id"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
