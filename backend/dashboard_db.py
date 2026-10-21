"""What the ria-ui dashboard reads and changes, in the shapes its screens use
(frontend/src/types/index.ts). server.py exposes these over /api.

Everything is scoped to one tenant (the signed-in user's company).
"""
import hashlib
import math
import re
import secrets
from datetime import date, datetime, timedelta, timezone

from psycopg.types.json import Json

from db_driver import IST, LANGUAGE_NAMES, OUTCOME_LABELS, DatabaseDriver, language_code, new_id
from dialer import parse_invoice

# How each response is shown (Collections tiles, dashboard bars)
RESPONSES = [
    ("ptp", "PTP given", "var(--green)", "Retailer committed to a specific date & amount"),
    ("dispute", "Payment dispute", "var(--red)", "Claims damaged goods, rate difference or short delivery"),
    ("already_paid", "Already paid", "var(--blue)", "Claims payment done via cash/cheque/UPI"),
    ("nolift", "Call not lifted", "var(--gold)", "Ringing, busy or switched off across attempts"),
    ("wrong_number", "Wrong / dead number", "#8593AD", "Number invalid, not reachable or wrong person"),
    ("human_escalate", "Asked for person", "var(--teal)", "Explicitly asked to talk to credit manager/salesman"),
    ("broken_ptp", "Broken PTP", "var(--red)", "Missed committed date without payment"),
]
RESPONSE_OF_OUTCOME = {
    "PROMISE-TO-PAY": "ptp", "DISPUTE": "dispute", "ALREADY-PAID": "already_paid",
    "NO-ANSWER": "nolift", "BUSY": "nolift", "WRONG-PERSON": "wrong_number",
}
# Colour of a response in the "All responses" list
OTHER_COLORS = {
    "DISPUTE": "var(--red)", "REFUSED": "var(--red)", "ALREADY-PAID": "var(--blue)",
    "WRONG-PERSON": "#8593AD", "CALLBACK": "var(--teal)", "REQUEST": "var(--teal)", "OPT-OUT": "#8593AD",
}
PTP_LABELS = {"due": ("Due today", "c-gold"), "upcoming": ("Upcoming", "c-blue"),
              "kept": ("Kept", "c-green"), "broken": ("Broken", "c-red")}


# -- formatting -----------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(IST)


def when(ts: datetime | None) -> str:
    """'Today 10:42 AM', 'Yesterday 04:10 PM' or '12 Oct 09:30 AM'."""
    if ts is None:
        return "—"
    ts = ts.astimezone(IST)
    days = (_now().date() - ts.date()).days
    day = "Today" if days == 0 else "Yesterday" if days == 1 else f"{ts:%d %b}"
    return f"{day} {ts:%I:%M %p}"


def relative(ts: datetime) -> tuple[str, bool]:
    """('In 24 mins', False), ('Due now', True) ..."""
    minutes = math.ceil((ts - _now()).total_seconds() / 60)
    if minutes <= 0:
        return "Due now", True
    if minutes < 60:
        return f"In {minutes} mins", minutes <= 10
    if minutes < 24 * 60:
        return f"In {minutes // 60}h {minutes % 60}m", False
    return f"In {minutes // (24 * 60)} days", False


def inr(amount) -> str:
    """₹ with Indian digit grouping: 1234567 -> ₹12,34,567"""
    digits = str(int(round(float(amount or 0))))
    if len(digits) > 3:
        head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", digits[:-3])
        digits = f"{head},{digits[-3:]}"
    return f"₹{digits}"


def overdue_days(due: date) -> int:
    return (_now().date() - due).days


def aging_bucket(days: int) -> str:
    if days <= 0:
        return "Current"
    return "1–30d" if days <= 30 else "31–60d" if days <= 60 else "61–90d" if days <= 90 else ">90d"


def parse_when(text: str) -> datetime:
    """The reschedule screen's choices: 'Today, in +15 mins', 'Today, 05:00 PM (...)',
    'Tomorrow, 10:00 AM (...)' or '2026-10-09 at 16:30'."""
    now = _now()
    text = (text or "").strip()
    if m := re.search(r"\+(\d+)\s*min", text):
        return now + timedelta(minutes=int(m.group(1)))
    if m := re.match(r"(\d{4}-\d{2}-\d{2})\s*(?:at)?\s*(\d{1,2}):(\d{2})", text):
        day = date.fromisoformat(m.group(1))
        return datetime(day.year, day.month, day.day, int(m.group(2)), int(m.group(3)), tzinfo=IST)
    if m := re.search(r"(\d{1,2}):(\d{2})\s*([AP]M)", text, re.I):
        hour = int(m.group(1)) % 12 + (12 if m.group(3).upper() == "PM" else 0)
        day = now.date() + timedelta(days=1 if text.lower().startswith("tomorrow") else 0)
        return datetime(day.year, day.month, day.day, hour, int(m.group(2)), tzinfo=IST)
    raise ValueError(f"Can't read the time {text!r}")


def phone_display(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return f"+91 {digits[2:7]} {digits[7:]}" if len(digits) == 12 and digits.startswith("91") else phone


class Dashboard(DatabaseDriver):

    # -- sign-in --------------------------------------------------------------------

    def authenticate(self, email: str, password: str) -> dict | None:
        with self.connection() as conn:
            user = conn.execute(
                """
                SELECT u.id, u.tenant_id, u.name, u.email, u.role, t.name AS company
                FROM users u JOIN tenants t ON t.id = u.tenant_id
                WHERE lower(u.email) = lower(%s) AND u.status = 'Active'
                    AND u.password_hash = crypt(%s, u.password_hash)
                """,
                (email.strip(), password),
            ).fetchone()
            if user:
                conn.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = %s", (user["id"],))
        return user

    def get_user(self, user_id: str) -> dict | None:
        with self.connection() as conn:
            return conn.execute(
                "SELECT u.id, u.tenant_id, u.name, u.email, u.role, t.name AS company "
                "FROM users u JOIN tenants t ON t.id = u.tenant_id WHERE u.id = %s AND u.status = 'Active'",
                (user_id,),
            ).fetchone()

    def email_exists(self, email: str) -> bool:
        with self.connection() as conn:
            row = conn.execute("SELECT 1 FROM users WHERE lower(email) = lower(%s)", (email.strip(),)).fetchone()
            return bool(row)

    def get_user_by_email(self, email: str) -> dict | None:
        with self.connection() as conn:
            return conn.execute(
                "SELECT u.id, u.tenant_id, u.name, u.email, u.role, t.name AS company "
                "FROM users u JOIN tenants t ON t.id = u.tenant_id "
                "WHERE lower(u.email) = lower(%s) AND u.status = 'Active'",
                (email.strip(),),
            ).fetchone()

    def create_auth_verification(self, email: str, purpose: str, code: str, payload: dict | None = None, ttl_minutes: int = 15) -> None:
        code_hash = hashlib.sha256(code.strip().encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        with self.connection() as conn:
            conn.execute(
                "DELETE FROM auth_verifications WHERE lower(email) = lower(%s) AND purpose = %s",
                (email.strip(), purpose),
            )
            conn.execute(
                """
                INSERT INTO auth_verifications (email, purpose, code_hash, payload, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (email.strip().lower(), purpose, code_hash, Json(payload or {}), expires_at),
            )

    def verify_auth_code(self, email: str, purpose: str, code: str) -> tuple[bool, dict | None, str | None]:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT id, code_hash, payload, expires_at, attempts
                FROM auth_verifications
                WHERE lower(email) = lower(%s) AND purpose = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (email.strip(), purpose),
            ).fetchone()
            if not row:
                return False, None, "No active verification code found. Please request a new one."
            if row["attempts"] >= 5:
                conn.execute("DELETE FROM auth_verifications WHERE id = %s", (row["id"],))
                return False, None, "Too many failed attempts. Please request a new code."
            if datetime.now(timezone.utc) > row["expires_at"]:
                conn.execute("DELETE FROM auth_verifications WHERE id = %s", (row["id"],))
                return False, None, "Verification code has expired. Please request a new one."

            code_hash = hashlib.sha256(code.strip().encode()).hexdigest()
            if code_hash != row["code_hash"]:
                conn.execute("UPDATE auth_verifications SET attempts = attempts + 1 WHERE id = %s", (row["id"],))
                return False, None, "Invalid verification code. Please check and try again."

            conn.execute("DELETE FROM auth_verifications WHERE id = %s", (row["id"],))
            return True, row["payload"], None

    def complete_registration(self, payload: dict) -> dict:
        company_name = str(payload.get("companyName", "My Company")).strip()[:200]
        full_name = str(payload.get("name", "Owner")).strip()[:100]
        email = str(payload.get("email", "")).strip().lower()[:200]
        phone = str(payload.get("phone", "")).strip()[:30]
        password = str(payload.get("password", ""))

        default_rules = {
            "cap": 3, "starthour": "08:00", "endhour": "19:00", "cooldown_minutes": 5,
            "ptpwindow_days": 7, "escalate_broken_threshold": 2, "blockdispute": True, "blockholiday": True,
        }

        with self.connection() as conn:
            existing = conn.execute("SELECT 1 FROM users WHERE lower(email) = lower(%s)", (email,)).fetchone()
            if existing:
                raise ValueError("An account with this email already exists.")

            count = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()
            c_val = count["count"] if isinstance(count, dict) else count[0]
            tenant_id = f"TENANT-{c_val + 1:03d}"
            user_id = f"U-{secrets.token_hex(4)}"

            with conn.transaction():
                conn.execute(
                    "INSERT INTO tenants (id, name, gstin, caller_id) VALUES (%s, %s, %s, %s)",
                    (tenant_id, company_name, f"PENDING-{tenant_id}", "RIA"),
                )
                conn.execute(
                    "UPDATE tenants SET config = jsonb_set(config, '{rules}', (config->'rules') || %s::jsonb) WHERE id = %s",
                    (Json(default_rules), tenant_id),
                )
                conn.execute(
                    "INSERT INTO users (id, tenant_id, name, email, password_hash, role, phone) "
                    "VALUES (%s, %s, %s, %s, crypt(%s, gen_salt('bf')), 'OW', %s)",
                    (user_id, tenant_id, full_name, email, password, phone),
                )

            return {
                "id": user_id,
                "tenant_id": tenant_id,
                "name": full_name,
                "email": email,
                "role": "OW",
                "company": company_name,
            }

    def reset_password(self, email: str, new_password: str) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                "UPDATE users SET password_hash = crypt(%s, gen_salt('bf')) WHERE lower(email) = lower(%s)",
                (new_password, email.strip()),
            )
            return cursor.rowcount > 0

    def audit(self, tenant_id: str, user_id: str | None, action: str, resource: str, resource_id: str,
              details: dict | None = None) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO audit_logs (tenant_id, user_id, action, resource_type, resource_id, details) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (tenant_id, user_id, action, resource, resource_id, Json(details or {})),
            )

    # -- everything a screen shows ----------------------------------------------------

    def state(self, tenant_id: str, user: dict) -> dict:
        with self.connection() as conn:
            self._refresh_retailer_totals(conn, tenant_id=tenant_id)
            self._purge_old_reschedules(conn, tenant_id)
            calls = self._calls(conn, tenant_id)
            ptps = self._ptps(conn, tenant_id)
            queue = self._queue(conn, tenant_id)
            nolift = self._nolift(queue)
            return {
                "me": {"id": user["id"], "n": user["name"], "e": user["email"], "role": user["role"]},
                "retailers": self._retailers(conn, tenant_id),
                "calls": calls,
                "batches": self._batches(conn, tenant_id, calls),
                "scheduledCallbacks": queue,
                "escalations": self._tickets(conn, tenant_id),
                "campaignContacts": self._campaign_contacts(conn, tenant_id),
                "users": self._users(conn, tenant_id),
                "config": self._config(conn, tenant_id),
                "ptps": ptps,
                "nolift": nolift,
                "allResp": self._all_responses(conn, tenant_id, ptps, nolift),
                "resp": self._response_stats(conn, tenant_id, ptps),
                "trend": self._trend(conn, tenant_id),
                "recovery": self._recovery(conn, tenant_id),
                "summary": self._summary(conn, tenant_id, ptps),
                "auditLog": self._audit_log(conn, tenant_id),
                "dialer": {},
            }

    def _retailers(self, conn, tenant_id: str) -> list[dict]:
        retailers = conn.execute(
            "SELECT * FROM retailers WHERE tenant_id = %s ORDER BY overdue_amount DESC, name LIMIT 2000",
            (tenant_id,),
        ).fetchall()
        invoices: dict[str, list] = {}
        for i in conn.execute(
            "SELECT i.* FROM invoices i JOIN retailers r ON r.id = i.retailer_id WHERE r.tenant_id = %s "
            "ORDER BY i.due_date",
            (tenant_id,),
        ):
            days = overdue_days(i["due_date"])
            status = ("Paid" if i["status"] == "paid" else "Disputed" if i["status"] == "disputed"
                      else f"Overdue {days}d" if days > 0 else "Current")
            invoices.setdefault(i["retailer_id"], []).append(
                {"inv": i["invoice_number"], "amt": float(i["due_amount"]), "due": i["due_date"].isoformat(), "st": status}
            )
        history: dict[str, list] = {}
        for c in conn.execute(
            """
            SELECT * FROM (
                SELECT c.*, row_number() OVER (PARTITION BY retailer_id ORDER BY created_at DESC) AS n
                FROM calls c WHERE c.tenant_id = %s
            ) x WHERE n <= 10 ORDER BY created_at DESC
            """,
            (tenant_id,),
        ):
            detail = c["disposition"] + (f" — {c['ai_summary']}" if c["ai_summary"] else "")
            history.setdefault(c["retailer_id"], []).append(
                {"d": when(c["created_at"]), "typ": "Collection", "dur": c["duration_display"],
                 "disp": detail}
            )
        open_ptps = {
            p["retailer_id"]: p for p in conn.execute(
                "SELECT DISTINCT ON (p.retailer_id) p.* FROM ptp_commitments p JOIN retailers r ON r.id = p.retailer_id "
                "WHERE r.tenant_id = %s AND p.status IN ('due', 'upcoming') ORDER BY p.retailer_id, p.due_date",
                (tenant_id,),
            )
        }
        out = []
        for r in retailers:
            ptp = open_ptps.get(r["id"])
            out.append({
                "id": r["id"], "name": r["name"], "code": r["code"], "city": r["city"] or "",
                "owner": r["owner_name"] or "", "phone": phone_display(r["phone"]), "lang": r["preferred_lang"],
                "bucket": r["aging_bucket"], "os": float(r["total_outstanding"]), "od": float(r["overdue_amount"]),
                "lim": float(r["credit_limit"]), "lastCall": when(r["last_call_at"]),
                "ptp": f"{ptp['due_date'].isoformat()} ({inr(ptp['amount'])})" if ptp else "None",
                "disp": ("Do not call" if r["do_not_call"] else r["last_disposition"] or "Not called yet"),
                "score": r["sentiment_score"], "auto": r["autonomy_level"], "creditPeriod": r["credit_period"],
                "history": history.get(r["id"], []), "invoices": invoices.get(r["id"], []),
            })
        return out

    @staticmethod
    def _call_item(c: dict) -> dict:
        return {
            "id": c["id"], "ret": c["retailer_id"], "name": c["customer_name"], "ph": phone_display(c["phone"]),
            "time": when(c["created_at"]), "lang": c["language"], "dur": c["duration_display"],
            "disp": c["disposition"], "ptp": c["ptp_committed_date"].isoformat() if c["ptp_committed_date"] else "None",
            "auto": c["autonomy_level"], "score": c["sentiment_score"],
            "turns": c.get("turns") or [], "batchId": c["batch_id"], "summary": c["ai_summary"] or "",
        }

    def _calls(self, conn, tenant_id: str) -> list[dict]:
        # Calls still to come first, then the latest finished ones with their transcripts
        pending = conn.execute(
            """
            SELECT o.* FROM outbound_calls o
            WHERE o.tenant_id = %s AND o.status IN ('queued', 'dialing', 'live')
            ORDER BY o.created_at DESC LIMIT 500
            """,
            (tenant_id,),
        ).fetchall()
        state = {"queued": "Queued for dialing", "dialing": "Dialing…", "live": "On call now"}
        items = [{
            "id": f"Q-{o['id'][:10]}", "ret": o["retailer_id"], "name": o["customer_name"],
            "ph": phone_display(o["phone"]), "time": "Queued" if o["status"] == "queued" else when(o["created_at"]),
            "lang": LANGUAGE_NAMES.get(o["language"], "Telugu"), "dur": "—", "disp": state[o["status"]],
            "ptp": "—", "auto": "L2", "score": 80, "turns": [], "batchId": o["batch_id"],
            "callId": o["id"], "callState": o["status"], "dialNow": o["dial_now"],
        } for o in pending]
        finished = conn.execute(
            "SELECT * FROM calls WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 300", (tenant_id,)
        ).fetchall()
        return items + [self._call_item(c) for c in finished]

    def _batches(self, conn, tenant_id: str, calls: list[dict]) -> list[dict]:
        batches = conn.execute(
            "SELECT * FROM call_batches WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 50", (tenant_id,)
        ).fetchall()
        by_batch: dict[str, list] = {}
        for c in calls:
            if c["batchId"]:
                by_batch.setdefault(c["batchId"], []).append(c)
        # Calls of older batches beyond the latest 300 (without transcripts: the report doesn't need them)
        shown = {c["id"] for c in calls}
        if batches:
            for c in conn.execute(
                "SELECT * FROM calls WHERE batch_id = ANY(%s) ORDER BY created_at DESC LIMIT 5000",
                ([b["id"] for b in batches],),
            ):
                if c["id"] not in shown:
                    item = self._call_item(c)
                    item["turns"] = []
                    by_batch.setdefault(c["batch_id"], []).append(item)
        counts = {
            row["batch_id"]: row for row in conn.execute(
                """
                SELECT batch_id, COUNT(*) FILTER (WHERE status = 'queued') AS queued,
                    COUNT(*) FILTER (WHERE status IN ('dialing', 'live')) AS live,
                    COUNT(*) FILTER (WHERE status = 'done') AS done
                FROM outbound_calls WHERE batch_id = ANY(%s) GROUP BY batch_id
                """,
                ([b["id"] for b in batches],),
            )
        } if batches else {}

        def dial_state(b: dict) -> str:
            c = counts.get(b["id"]) or {"queued": 0, "live": 0, "done": 0}
            if not c["queued"] and not c["live"]:
                return "done"
            if b["dialing"]:
                return "running"
            return "paused" if c["done"] or c["live"] else "ready"

        return [{
            "dialState": dial_state(b),
            "queuedCalls": (counts.get(b["id"]) or {}).get("queued", 0),
            "liveCalls": (counts.get(b["id"]) or {}).get("live", 0),
            "id": b["id"], "name": b["name"], "createdAt": when(b["created_at"]), "importedBy": b["imported_by_name"],
            "fileName": b["file_name"], "totalCalls": b["total_calls"], "completedCalls": b["completed_calls"],
            "connectedCalls": b["connected_calls"], "ptpCount": b["ptp_count"], "ptpAmount": float(b["ptp_amount"]),
            "disputeCount": b["dispute_count"], "noLiftCount": b["no_lift_count"],
            "status": "Scheduled" if b["status"] == "Scheduled" else b["status"] if b["status"] != "Failed" else "Completed",
            "calls": by_batch.get(b["id"], []),
        } for b in batches]

    @staticmethod
    def _purge_old_reschedules(conn, tenant_id: str) -> None:
        """The reschedule queue keeps one week: entries neither due nor updated in the last
        7 days are deleted. Future callbacks stay, and a call being dialed is never removed."""
        conn.execute(
            """
            DELETE FROM call_reschedule_queue
            WHERE tenant_id = %s AND status <> 'Dialing'
                AND GREATEST(scheduled_for, COALESCE(updated_at, created_at)) < CURRENT_TIMESTAMP - INTERVAL '7 days'
            """,
            (tenant_id,),
        )

    def _queue(self, conn, tenant_id: str) -> list[dict]:
        rows = conn.execute(
            """
            SELECT * FROM call_reschedule_queue
            WHERE tenant_id = %s AND (status IN ('Queued', 'Dialing', 'Exhausted')
                OR updated_at >= CURRENT_TIMESTAMP - INTERVAL '2 days')
            ORDER BY status = 'Queued' DESC, scheduled_for LIMIT 500
            """,
            (tenant_id,),
        ).fetchall()
        out = []
        for q in rows:
            rel, due_now = relative(q["scheduled_for"])
            if q["status"] == "Dialing":
                rel, due_now = "Dialing now…", False
            elif q["status"] != "Queued":
                rel, due_now = q["last_outcome"] or q["status"], False
            out.append({
                "id": q["id"], "ret": q["retailer_id"], "name": q["customer_name"], "ph": phone_display(q["phone"]),
                "outstanding": float(q["outstanding_amount"]), "type": q["type"],
                "priority": q["priority"] if q["priority"] in ("High", "Medium") else "Normal",
                "scheduledTime": when(q["scheduled_for"]).replace(" ", ", ", 1), "relativeDue": rel,
                "isDueNow": due_now, "attempt": q["attempt_number"], "maxAttempts": q["max_attempts"],
                "aiNote": q["ai_note"] or "", "status": q["status"], "sourceCallId": q["source_call_id"] or "",
                "lastOutcome": q["last_outcome"] or "",
            })
        return out

    @staticmethod
    def _nolift(queue: list[dict]) -> list[dict]:
        return [{
            "ret": q["ret"], "name": q["name"], "att": q["attempt"] - (1 if q["status"] == "Queued" else 0),
            "last": q["lastOutcome"], "next": q["relativeDue"] if q["status"] == "Queued" else "Field visit",
            "auto": "L2", "ph": q["ph"],
        } for q in queue if q["type"] in ("no_lift_retry", "busy_retry") and q["status"] in ("Queued", "Dialing", "Exhausted")]

    def _ptps(self, conn, tenant_id: str) -> list[dict]:
        today = _now().date()
        out = []
        for p in conn.execute(
            "SELECT p.* FROM ptp_commitments p JOIN retailers r ON r.id = p.retailer_id "
            "WHERE r.tenant_id = %s ORDER BY p.due_date DESC LIMIT 500",
            (tenant_id,),
        ):
            status = p["status"]
            if status in ("due", "upcoming"):
                # A promise past its date with no payment recorded counts as broken
                status = "broken" if p["due_date"] < today else "due" if p["due_date"] == today else "upcoming"
            out.append({"id": p["id"], "ret": p["retailer_id"], "name": p["customer_name"],
                        "due": p["due_date"].isoformat(), "amt": float(p["amount"]), "st": status,
                        "auto": p["autonomy_level"] or "L2", "ph": phone_display(p["phone"])})
        return out

    def _all_responses(self, conn, tenant_id: str, ptps: list[dict], nolift: list[dict]) -> list[dict]:
        out = [{"ret": p["ret"], "name": p["name"], "ph": p["ph"],
                "disp": f"PTP — {inr(p['amt'])} on {p['due']}", "st": PTP_LABELS[p["st"]][0],
                "sc": PTP_LABELS[p["st"]][1], "auto": p["auto"]} for p in ptps]
        out += [{"ret": n["ret"], "name": n["name"], "ph": n["ph"], "disp": f"Call not lifted ({n['att']} attempts)",
                 "st": f"Retry {n['next']}", "sc": "c-gold", "auto": n["auto"]} for n in nolift]
        for c in conn.execute(
            "SELECT * FROM calls WHERE tenant_id = %s AND outcome = ANY(%s) AND created_at >= CURRENT_DATE - 7 "
            "ORDER BY created_at DESC LIMIT 200",
            (tenant_id, list(OTHER_COLORS)),
        ):
            red = OTHER_COLORS[c["outcome"]] == "var(--red)"
            out.append({"ret": c["retailer_id"], "name": c["customer_name"], "ph": phone_display(c["phone"]),
                        "disp": c["disposition"] + (f" — {c['ai_summary']}" if c["ai_summary"] else ""),
                        "st": c["disposition"], "sc": "c-red" if red else "c-blue", "auto": c["autonomy_level"]})
        return out

    def _response_stats(self, conn, tenant_id: str, ptps: list[dict]) -> list[dict]:
        counts = dict.fromkeys((k for k, *_ in RESPONSES), 0)
        for row in conn.execute(
            "SELECT outcome, COUNT(*) AS n FROM calls WHERE tenant_id = %s AND created_at >= %s GROUP BY outcome",
            (tenant_id, datetime.combine(_now().date(), datetime.min.time(), IST)),
        ):
            key = RESPONSE_OF_OUTCOME.get(row["outcome"])
            if key:
                counts[key] += row["n"]
        counts["human_escalate"] = conn.execute(
            "SELECT COUNT(*) AS n FROM tickets WHERE tenant_id = %s AND category = 'Asked for person' "
            "AND created_at >= CURRENT_DATE",
            (tenant_id,),
        ).fetchone()["n"]
        counts["broken_ptp"] = sum(1 for p in ptps if p["st"] == "broken")
        return [{"k": k, "l": label, "n": counts[k], "c": color, "d": desc} for k, label, color, desc in RESPONSES]

    def _trend(self, conn, tenant_id: str) -> list[dict]:
        today = _now().date()
        rows = {r["day"]: r for r in conn.execute(
            """
            SELECT (created_at AT TIME ZONE 'Asia/Kolkata')::date AS day, COUNT(*) AS placed,
                   COUNT(*) FILTER (WHERE duration_seconds > 0) AS conn,
                   COUNT(*) FILTER (WHERE outcome = 'PROMISE-TO-PAY') AS ptp
            FROM calls WHERE tenant_id = %s AND created_at >= %s GROUP BY 1
            """,
            (tenant_id, datetime.combine(today - timedelta(days=6), datetime.min.time(), IST)),
        )}
        days = [today - timedelta(days=i) for i in range(6, -1, -1)]
        return [{"d": f"{d:%a}", "placed": rows.get(d, {}).get("placed", 0), "conn": rows.get(d, {}).get("conn", 0),
                 "ptp": rows.get(d, {}).get("ptp", 0)} for d in days]

    def _recovery(self, conn, tenant_id: str) -> list[dict]:
        """Per week: the amount RIA called about (demand) and the amount promised (recovery)."""
        today = _now().date()
        start = today - timedelta(days=today.weekday() + 28)
        demand = {r["wk"]: float(r["amt"]) for r in conn.execute(
            "SELECT date_trunc('week', created_at AT TIME ZONE 'Asia/Kolkata')::date AS wk, "
            "SUM(DISTINCT amount) AS amt FROM outbound_calls WHERE tenant_id = %s AND created_at >= %s GROUP BY 1",
            (tenant_id, start),
        )}
        promised = {r["wk"]: float(r["amt"]) for r in conn.execute(
            "SELECT date_trunc('week', created_at AT TIME ZONE 'Asia/Kolkata')::date AS wk, "
            "COALESCE(SUM(ptp_amount), 0) AS amt FROM calls WHERE tenant_id = %s AND created_at >= %s "
            "AND outcome = 'PROMISE-TO-PAY' GROUP BY 1",
            (tenant_id, start),
        )}
        weeks = [start + timedelta(weeks=i) for i in range(5)]
        return [{"d": f"Wk {w.isocalendar().week}" + (" (curr)" if i == 4 else ""),
                 "dem": demand.get(w, 0), "rec": promised.get(w, 0)} for i, w in enumerate(weeks)]

    def _tickets(self, conn, tenant_id: str) -> list[dict]:
        out = []
        for t in conn.execute(
            "SELECT * FROM tickets WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 500", (tenant_id,)
        ):
            hours = int((_now() - t["created_at"]).total_seconds() // 3600)
            age = "Just now" if hours < 1 else f"{hours}h" if hours < 48 else f"{hours // 24}d"
            out.append({
                "id": t["id"], "category": t["category"], "customer": t["customer_name"], "severity": t["severity"],
                "owner": t["assigned_to_name"] or "Unassigned", "age": age,
                "sourceCallId": t["source_call_id"] or "",
                "status": "Resolved" if t["status"] in ("Resolved", "Closed") else "Open",
                "resolutionNote": t["resolution_note"] or "",
            })
        return out

    @staticmethod
    def _campaign_contacts(conn, tenant_id: str) -> list[dict]:
        return [{"id": c["id"], "name": c["name"], "phno": phone_display(c["phone"]), "creditPeriod": c["credit_period"],
                 "addedAt": c["created_at"].astimezone(IST).date().isoformat()}
                for c in conn.execute(
                    "SELECT * FROM campaign_contacts WHERE tenant_id = %s ORDER BY created_at DESC LIMIT 2000",
                    (tenant_id,),
                )]

    @staticmethod
    def _users(conn, tenant_id: str) -> list[dict]:
        return [{"id": u["id"], "n": u["name"], "e": u["email"], "role": u["role"], "ph": u["phone"] or "",
                 "st": u["status"]}
                for u in conn.execute("SELECT * FROM users WHERE tenant_id = %s ORDER BY created_at", (tenant_id,))]

    @staticmethod
    def _config(conn, tenant_id: str) -> dict:
        t = conn.execute("SELECT * FROM tenants WHERE id = %s", (tenant_id,)).fetchone()
        cfg = t["config"] or {}
        rules = cfg.get("rules", {})
        general = cfg.get("general", {})
        return {
            "provider": cfg.get("provider", ""),
            # Credentials stay on the server; the dashboard never receives them
            "creds": {},
            "numbers": cfg.get("numbers", []),
            "voice": cfg.get("voice", {}),
            "rules": {
                "cap": rules.get("cap", 3), "starthour": rules.get("starthour", "08:00"),
                "endhour": rules.get("endhour", "19:00"), "cooldown": rules.get("cooldown_minutes", 5),
                "ptpwindow": rules.get("ptpwindow_days", 7), "escalate": rules.get("escalate_broken_threshold", 2),
                "blockdispute": rules.get("blockdispute", True), "blockholiday": rules.get("blockholiday", True),
            },
            "general": {
                "tenant": t["name"], "gstin": t["gstin"], "callerid": t["caller_id"] or "",
                "audiodays": general.get("audiodays", 90), "auditdays": general.get("auditdays", 365),
                "webhook": general.get("webhook", ""), "escalateemail": general.get("escalateemail", ""),
                "escalatesms": general.get("escalatesms", ""),
            },
        }

    @staticmethod
    def _summary(conn, tenant_id: str, ptps: list[dict]) -> dict:
        """Dashboard tiles. Payments aren't recorded yet, so recovery is measured
        by what customers promised on RIA's calls."""
        # The tiles count only invoices from CSV batches still on the Calls page, and the
        # promises made on calls about them; deleting a batch drops all of its figures
        batch = conn.execute(
            """
            WITH cur AS (
                SELECT DISTINCT invoice_id FROM outbound_calls
                WHERE tenant_id = %(t)s AND batch_id IS NOT NULL AND invoice_id IS NOT NULL
            ), cur_calls AS (
                SELECT c.id, c.ptp_amount, c.outcome, c.created_at FROM calls c
                JOIN outbound_calls o ON o.id = c.outbound_call_id
                WHERE c.tenant_id = %(t)s AND o.invoice_id IN (SELECT invoice_id FROM cur)
            )
            SELECT (SELECT COALESCE(SUM(amount), 0) FROM invoices WHERE id IN (SELECT invoice_id FROM cur)) AS invoiced,
                   (SELECT COUNT(DISTINCT retailer_id) FROM invoices WHERE id IN (SELECT invoice_id FROM cur)) AS accounts,
                   (SELECT COALESCE(SUM(ptp_amount), 0) FROM cur_calls WHERE outcome = 'PROMISE-TO-PAY'
                        AND created_at >= date_trunc('month', CURRENT_DATE)) AS promised,
                   (SELECT COALESCE(array_agg(p.id), '{}') FROM ptp_commitments p
                        WHERE p.source_call_id IN (SELECT id FROM cur_calls)) AS ptp_ids
            """,
            {"t": tenant_id},
        ).fetchone()
        ptp_ids = set(batch["ptp_ids"])
        return {
            "invoiced": float(batch["invoiced"]), "invoiceAccounts": batch["accounts"],
            "promisedMtd": float(batch["promised"]),
            "pipeline": sum(p["amt"] for p in ptps if p["st"] in ("due", "upcoming") and p["id"] in ptp_ids),
        }

    @staticmethod
    def _audit_log(conn, tenant_id: str) -> list[list]:
        return [[a["created_at"].astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"), a["name"] or "RIA System",
                 a["role"] or "", a["action"], a["resource_id"], ", ".join(f"{k}: {v}" for k, v in a["details"].items())]
                for a in conn.execute(
                    "SELECT a.*, u.name, u.role FROM audit_logs a LEFT JOIN users u ON u.id = a.user_id "
                    "WHERE a.tenant_id = %s AND a.created_at >= CURRENT_DATE - 30 ORDER BY a.created_at DESC LIMIT 2000",
                    (tenant_id,),
                )]

    # -- changes ----------------------------------------------------------------------

    def import_batch(self, tenant_id: str, user: dict, file_name: str, name: str, rows: list[dict],
                     status: str = "queued", start: bool = False, recent: str = "ask") -> dict:
        """One call per valid invoice row; retailers and invoices are created or updated.

        The calls wait until the batch is started ("Start calling"), unless `start`.

        Customers already spoken to about the invoice in the last 20 hours: `recent` "ask"
        imports nothing and lists them (result "recent") so the user can choose; "call"
        calls them again; "skip" leaves them out.

        Rows: {businessName, phone, invoiceNumber, dueDate (or invoiceDate), invoiceAmount, lang}.
        """
        valid, skipped, again = [], [], []
        # A customer listed twice for one invoice would be called twice about it
        seen: dict[tuple[str, str], int] = {}
        for line, row in enumerate(rows, start=1):
            date_field = row.get("dueDate") or row.get("due_date") or row.get("invoiceDate") or row.get("invoice_date")
            invoice, problem = parse_invoice({
                "name": row.get("name") or row.get("businessName"), "phone": row.get("phone"),
                "business": row.get("businessName") or "", "invoice_no": row.get("invoiceNumber"),
                "amount": row.get("invoiceAmount") or row.get("amount"),
                "due_date": date_field,
                # RIA has opening lines in Telugu, Hindi and English; others open in the default
                "language": code if (code := language_code(row.get("lang"))) in ("te", "hi", "en") else "",
            })
            if invoice and row.get("invoiceNumber") and date_field and str(row.get("invoiceNumber", "")).strip() == str(date_field).strip():
                # A mis-mapped column: RIA would read the date out as the invoice number
                invoice, problem = None, "invoice number is the same as the date: check the columns"
            if invoice and (key := (invoice["phone"], invoice["invoice_no"].lower())) in seen:
                invoice, problem = None, f"same phone and invoice as row {seen[key]}"
            elif invoice:
                seen[key] = line
            if invoice and self.has_opted_out(tenant_id, invoice["phone"]):
                problem = "customer asked not to be called"
            elif invoice and self.call_waiting(tenant_id, invoice["phone"], invoice["invoice_no"]):
                problem = "a call about this invoice is already waiting or on the line"
            elif invoice and recent != "call" and (
                    last := self.last_discussed(tenant_id, invoice["phone"], invoice["invoice_no"])):
                problem = "already discussed in the last 20 hours"
                again.append({"row": line, "name": invoice["customer_name"], "phone": invoice["phone"],
                              "invoice": invoice["invoice_no"], "lastCall": when(last["answered_at"]),
                              "outcome": OUTCOME_LABELS.get(last["outcome"], last["outcome"] or "")})
            if problem or not invoice:
                skipped.append({"row": line, "reason": problem})
            else:
                valid.append(invoice)
        if again and recent == "ask":
            return {"batch": None, "queued": 0, "skipped": skipped, "recent": again}
        if not valid:
            return {"batch": None, "queued": 0, "skipped": skipped}

        batch_id = f"BATCH-{_now():%Y-%m-%d}-{secrets.token_hex(2).upper()}"
        with self.connection() as conn, conn.transaction():
            conn.execute(
                "INSERT INTO call_batches (id, tenant_id, name, imported_by_user_id, imported_by_name, file_name, "
                "total_calls, dialing) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (batch_id, tenant_id, name or f"{file_name.rsplit('.', 1)[0]} Run", user["id"], user["name"],
                 file_name, len(valid), start),
            )
            for inv in valid:
                retailer_id = self._upsert_retailer(conn, tenant_id, inv)
                inv_no = inv["invoice_no"] or ""
                inv_amount = float(inv["amount"]) if inv["amount"] is not None else 0.0
                inv_due = inv["due_date"] or _now().date().isoformat()

                invoice_id = None
                if inv.get("has_invoice_no"):
                    invoice_id = conn.execute(
                        """
                        INSERT INTO invoices (retailer_id, invoice_number, amount, due_amount, due_date)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (retailer_id, invoice_number) DO UPDATE
                            SET due_amount = EXCLUDED.due_amount, due_date = EXCLUDED.due_date,
                                amount = GREATEST(invoices.amount, EXCLUDED.amount)
                        RETURNING id
                        """,
                        (retailer_id, inv_no, inv_amount, inv_amount, inv_due),
                    ).fetchone()["id"]
                    self._refresh_retailer_totals(conn, retailer_id)

                conn.execute(
                    """
                    INSERT INTO outbound_calls (id, tenant_id, batch_id, retailer_id, invoice_id, customer_name,
                        business_name, phone, language, invoice_number, amount, due_date, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (secrets.token_hex(16), tenant_id, batch_id, retailer_id, invoice_id, inv["customer_name"],
                     inv["business"], inv["phone"], inv["language"], inv_no, inv_amount,
                     inv_due, status),
                )
                conn.execute(
                    "INSERT INTO campaign_contacts (id, tenant_id, retailer_id, name, phone) "
                    "SELECT %s, %s, %s, %s, %s WHERE NOT EXISTS ("
                    "  SELECT 1 FROM campaign_contacts WHERE tenant_id = %s AND phone = %s)",
                    (new_id("C"), tenant_id, retailer_id, inv["customer_name"], inv["phone"], tenant_id, inv["phone"]),
                )
        return {"batch": batch_id, "queued": len(valid), "skipped": skipped}

    @staticmethod
    def _upsert_retailer(conn, tenant_id: str, inv: dict) -> str:
        existing = conn.execute(
            "SELECT id FROM retailers WHERE tenant_id = %s AND phone = %s ORDER BY created_at LIMIT 1",
            (tenant_id, inv["phone"]),
        ).fetchone()
        lang = LANGUAGE_NAMES.get(inv["language"], "")
        if existing:
            if lang:
                conn.execute("UPDATE retailers SET preferred_lang = %s WHERE id = %s", (lang, existing["id"]))
            return existing["id"]
        retailer_id = new_id("R")
        conn.execute(
            "INSERT INTO retailers (id, tenant_id, code, name, owner_name, business_name, phone, preferred_lang) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (retailer_id, tenant_id, f"RET-{secrets.token_hex(3).upper()}", inv["business"] or inv["customer_name"],
             inv["customer_name"], inv["business"] or inv["customer_name"], inv["phone"], lang or "Telugu"),
        )
        return retailer_id

    @staticmethod
    def _refresh_retailer_totals(conn, retailer_id: str | None = None, tenant_id: str | None = None) -> None:
        """Recomputes outstanding, overdue and aging from unpaid invoices, for one retailer or a
        whole tenant. Invoices turn overdue as their due dates pass, so state() refreshes the
        tenant on every load; only rows whose figures changed are written."""
        conn.execute(
            """
            WITH t AS (
                SELECT i.retailer_id AS id,
                       COALESCE(SUM(i.due_amount) FILTER (WHERE i.status <> 'paid'), 0) AS os,
                       COALESCE(SUM(i.due_amount) FILTER (WHERE i.status <> 'paid' AND i.due_date < CURRENT_DATE), 0) AS od,
                       MIN(i.due_date) FILTER (WHERE i.status <> 'paid' AND i.due_date < CURRENT_DATE) AS oldest
                FROM invoices i JOIN retailers r ON r.id = i.retailer_id
                WHERE r.id = %(r)s OR r.tenant_id = %(t)s
                GROUP BY i.retailer_id
            ), n AS (
                SELECT id, os, od, CASE
                    WHEN oldest IS NULL THEN 'Current'
                    WHEN CURRENT_DATE - oldest <= 30 THEN '1–30d'
                    WHEN CURRENT_DATE - oldest <= 60 THEN '31–60d'
                    WHEN CURRENT_DATE - oldest <= 90 THEN '61–90d'
                    ELSE '>90d' END AS bucket
                FROM t
            )
            UPDATE retailers SET total_outstanding = n.os, overdue_amount = n.od, aging_bucket = n.bucket
            FROM n WHERE retailers.id = n.id
                AND (retailers.total_outstanding, retailers.overdue_amount, retailers.aging_bucket)
                    IS DISTINCT FROM (n.os, n.od, n.bucket)
            """,
            {"r": retailer_id, "t": tenant_id},
        )

    # -- campaign controls ------------------------------------------------------------

    def set_batch_dialing(self, tenant_id: str, batch_id: str, dialing: bool) -> int:
        """Starts (or pauses) calling a batch; returns how many of its calls are waiting."""
        with self.connection() as conn:
            row = conn.execute(
                "UPDATE call_batches SET dialing = %s WHERE tenant_id = %s AND id = %s RETURNING id",
                (dialing, tenant_id, batch_id),
            ).fetchone()
            if not row:
                raise ValueError("Unknown batch")
            waiting = conn.execute(
                "SELECT COUNT(*) AS n FROM outbound_calls WHERE batch_id = %s AND status = 'queued'", (batch_id,)
            ).fetchone()["n"]
        if dialing and not waiting:
            raise ValueError("Every call in this batch has been made")
        return waiting

    def dial_call_now(self, tenant_id: str, call_id: str) -> dict:
        """Puts one waiting call at the front of the line, even if its batch isn't started."""
        with self.connection() as conn:
            row = conn.execute(
                """
                UPDATE outbound_calls SET dial_now = TRUE, scheduled_for = LEAST(scheduled_for, CURRENT_TIMESTAMP)
                WHERE tenant_id = %s AND id = %s AND status = 'queued'
                RETURNING customer_name, phone
                """,
                (tenant_id, call_id),
            ).fetchone()
        if not row:
            raise ValueError("This call is already being made or has finished")
        return {"name": row["customer_name"], "phone": phone_display(row["phone"])}

    def batch_sheet(self, tenant_id: str, batch_id: str) -> list[dict]:
        """Every row of an imported call sheet, in its order, with where its call is:
        the dialer screen shows the whole sheet while the campaign runs."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT o.*, c.disposition, c.duration_display FROM outbound_calls o
                LEFT JOIN calls c ON c.id = o.call_record_id
                WHERE o.tenant_id = %s AND o.batch_id = %s ORDER BY o.seq
                """,
                (tenant_id, batch_id),
            ).fetchall()
        if not rows:
            raise ValueError("Unknown batch")
        now = _now()
        sheet: dict[tuple, dict] = {}
        # One line per customer and invoice: retries and callbacks update their line
        for o in rows:
            key = (o["retailer_id"], o["invoice_id"], o["invoice_number"])
            if key not in sheet and o["queue_id"] is None:
                sheet[key] = {"row": len(sheet) + 1, "attempts": 0}
            line = sheet.get(key)
            # A cancelled duplicate doesn't hide the call that was made
            if line is None or (o["status"] == "cancelled" and "callId" in line):
                continue
            started = o["answered_at"] or o["dialed_at"]
            line.update({
                "callId": o["id"], "name": o["customer_name"], "business": o["business_name"] or "",
                "ph": phone_display(o["phone"]), "invoice": o["invoice_number"], "amount": float(o["amount"]),
                "dueDate": o["due_date"].isoformat(), "state": o["status"], "dialNow": o["dial_now"],
                "outcome": o["disposition"] or (OUTCOME_LABELS.get(o["outcome"], o["outcome"]) if o["outcome"] else ""),
                "promised": o["promised_date"].isoformat() if o["promised_date"] else "",
                "notes": o["notes"] or "", "duration": o["duration_display"] or "", "recordId": o["call_record_id"] or "",
                "seconds": max(0, int((now - started).total_seconds())) if started and o["status"] in ("dialing", "live") else 0,
            })
            line["attempts"] += 0 if o["status"] == "cancelled" else 1
        return list(sheet.values())

    def live(self, tenant_id: str) -> dict:
        """Who RIA is on the phone with right now, and who is next in line."""
        with self.connection() as conn:
            now_calling = conn.execute(
                """
                SELECT o.id, o.customer_name, o.business_name, o.phone, o.invoice_number, o.amount, o.status,
                    o.answered_at, o.dialed_at, o.created_at, o.batch_id, b.name AS batch_name
                FROM outbound_calls o LEFT JOIN call_batches b ON b.id = o.batch_id
                WHERE o.tenant_id = %s AND o.status IN ('dialing', 'live')
                ORDER BY o.answered_at NULLS LAST, o.created_at
                """,
                (tenant_id,),
            ).fetchall()
            up_next = conn.execute(
                f"""
                SELECT o.id, o.customer_name, o.phone, o.invoice_number, o.amount, o.dial_now, o.batch_id,
                    b.name AS batch_name
                FROM outbound_calls o JOIN retailers r ON r.id = o.retailer_id
                LEFT JOIN call_batches b ON b.id = o.batch_id
                WHERE o.tenant_id = %s AND {self.READY_TO_DIAL}
                ORDER BY {self.DIAL_ORDER} LIMIT 5
                """,
                (tenant_id,),
            ).fetchall()
            waiting = conn.execute(
                f"""
                SELECT COUNT(*) AS n FROM outbound_calls o JOIN retailers r ON r.id = o.retailer_id
                LEFT JOIN call_batches b ON b.id = o.batch_id
                WHERE o.tenant_id = %s AND {self.READY_TO_DIAL}
                """,
                (tenant_id,),
            ).fetchone()["n"]
        now = _now()
        return {
            "live": [{
                "callId": c["id"], "name": c["customer_name"], "business": c["business_name"] or "",
                "ph": phone_display(c["phone"]), "invoice": c["invoice_number"], "amount": float(c["amount"]),
                "state": "on_call" if c["status"] == "live" else "ringing",
                # Seconds on the line (or ringing), for the timer on screen
                "seconds": max(0, int((now - (c["answered_at"] or c["dialed_at"] or now)).total_seconds())),
                "batchId": c["batch_id"], "batchName": c["batch_name"] or "",
            } for c in now_calling],
            "next": [{
                "callId": c["id"], "name": c["customer_name"], "ph": phone_display(c["phone"]),
                "invoice": c["invoice_number"], "amount": float(c["amount"]), "dialNow": c["dial_now"],
                "batchId": c["batch_id"], "batchName": c["batch_name"] or "",
            } for c in up_next],
            "waiting": waiting,
        }

    def queue_contact_call(self, tenant_id: str, contact_id: str) -> str:
        """Calls a campaign contact ("add to active campaign")."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT r.id FROM campaign_contacts c JOIN retailers r ON r.tenant_id = c.tenant_id AND r.phone = c.phone "
                "WHERE c.tenant_id = %s AND c.id = %s LIMIT 1",
                (tenant_id, contact_id),
            ).fetchone()
        if not row:
            raise ValueError("This contact has no invoice on record yet: import a call sheet with their invoice")
        return self.queue_retailer_call(tenant_id, row["id"])

    def queue_retailer_call(self, tenant_id: str, retailer_id: str) -> str:
        """Calls a retailer about their oldest unpaid invoice, as soon as calling hours allow."""
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT r.id AS retailer_id, r.name, r.owner_name, r.business_name, r.phone, r.preferred_lang,
                       r.do_not_call, i.id AS invoice_id, i.invoice_number, i.due_amount, i.due_date
                FROM retailers r
                LEFT JOIN LATERAL (
                    SELECT * FROM invoices WHERE retailer_id = r.id AND status IN ('unpaid', 'partially_paid')
                    ORDER BY due_date LIMIT 1
                ) i ON TRUE
                WHERE r.tenant_id = %s AND r.id = %s
                """,
                (tenant_id, retailer_id),
            ).fetchone()
            if not row:
                raise ValueError("Unknown retailer")
            if row["do_not_call"]:
                raise ValueError(f"{row['name']} asked not to be called")
            if not row["invoice_id"]:
                raise ValueError(f"{row['name']} has no unpaid invoice to call about")
            if self.called_recently(tenant_id, row["phone"], row["invoice_number"]):
                raise ValueError("This invoice is already queued or was discussed in the last 20 hours")
            call_id = secrets.token_hex(16)
            conn.execute(
                """
                INSERT INTO outbound_calls (id, tenant_id, retailer_id, invoice_id, customer_name, business_name,
                    phone, language, invoice_number, amount, due_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (call_id, tenant_id, row["retailer_id"], row["invoice_id"], row["owner_name"] or row["name"],
                 row["business_name"], row["phone"], language_code(row["preferred_lang"]), row["invoice_number"],
                 row["due_amount"], row["due_date"]),
            )
        return call_id

    def dial_now(self, tenant_id: str, queue_id: str) -> None:
        with self.connection() as conn:
            cur = conn.execute(
                "UPDATE call_reschedule_queue SET scheduled_for = CURRENT_TIMESTAMP, status = 'Queued' "
                "WHERE tenant_id = %s AND id = %s AND status IN ('Queued', 'Exhausted', 'Cancelled')",
                (tenant_id, queue_id),
            )
        if not cur.rowcount:
            raise ValueError("This call is already being dialed or is finished")

    def reschedule(self, tenant_id: str, queue_id: str, when_text: str, note: str | None) -> None:
        at = parse_when(when_text)
        with self.connection() as conn:
            cur = conn.execute(
                "UPDATE call_reschedule_queue SET scheduled_for = %s, status = 'Queued', "
                "ai_note = COALESCE(NULLIF(%s, ''), ai_note) WHERE tenant_id = %s AND id = %s AND status <> 'Dialing'",
                (at, note, tenant_id, queue_id),
            )
        if not cur.rowcount:
            raise ValueError("This call is being dialed right now")

    def cancel_callback(self, tenant_id: str, queue_id: str, reason: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE call_reschedule_queue SET status = 'Cancelled', last_outcome = %s "
                "WHERE tenant_id = %s AND id = %s AND status IN ('Queued', 'Exhausted')",
                (reason or "Cancelled by user", tenant_id, queue_id),
            )

    def add_ticket(self, tenant_id: str, ticket: dict) -> str:
        ticket_id = new_id("E")
        source = ticket.get("sourceCallId") or ""
        call_id = m.group(0) if (m := re.search(r"CL-[0-9A-F]+", source)) else None
        with self.connection() as conn:
            retailer = conn.execute(
                "SELECT retailer_id FROM calls WHERE id = %s", (call_id,)
            ).fetchone() if call_id else None
            conn.execute(
                "INSERT INTO tickets (id, tenant_id, retailer_id, source_call_id, customer_name, category, severity, "
                "assigned_to_name, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Open')",
                (ticket_id, tenant_id, retailer["retailer_id"] if retailer else None, call_id or source or None,
                 ticket.get("customer") or "Retailer account", ticket.get("category") or "Dispute raised",
                 ticket.get("severity") if ticket.get("severity") in ("High", "Medium", "Low") else "High",
                 ticket.get("owner") or "Unassigned"),
            )
        return ticket_id

    def update_ticket(self, tenant_id: str, ticket_id: str, changes: dict) -> None:
        sets, values = [], []
        if "owner" in changes:
            sets.append("assigned_to_name = %s")
            values.append(changes["owner"])
        if changes.get("status") in ("Open", "Resolved"):
            sets.append("status = %s")
            values.append(changes["status"])
            sets.append("resolved_at = " + ("CURRENT_TIMESTAMP" if changes["status"] == "Resolved" else "NULL"))
        if "resolutionNote" in changes:
            sets.append("resolution_note = %s")
            values.append(changes["resolutionNote"])
        if "severity" in changes and changes["severity"] in ("High", "Medium", "Low"):
            sets.append("severity = %s")
            values.append(changes["severity"])
        if not sets:
            return
        with self.connection() as conn:
            conn.execute(f"UPDATE tickets SET {', '.join(sets)} WHERE tenant_id = %s AND id = %s",
                         (*values, tenant_id, ticket_id))

    # -- deleting and editing ---------------------------------------------------------

    def delete_batch(self, tenant_id: str, batch_id: str) -> dict:
        """Removes a batch from Call Campaign. Its waiting calls and automatic retries
        are cancelled; calls already made (records, promises, tickets) stay in the
        history, and callbacks customers asked for stay in Reschedule."""
        with self.connection() as conn, conn.transaction():
            batch = conn.execute(
                "SELECT id FROM call_batches WHERE tenant_id = %s AND id = %s FOR UPDATE", (tenant_id, batch_id)
            ).fetchone()
            if not batch:
                raise ValueError("Unknown batch")
            if conn.execute(
                "SELECT 1 FROM outbound_calls WHERE batch_id = %s AND status IN ('dialing', 'live') LIMIT 1", (batch_id,)
            ).fetchone():
                raise ValueError("A call from this batch is on the line. Pause the batch and delete it after the call.")
            # Cancelled before the batch goes: a waiting call without a batch would be dialed
            cancelled = conn.execute(
                "UPDATE outbound_calls SET status = 'cancelled', ended_at = CURRENT_TIMESTAMP, "
                "notes = COALESCE(notes, 'Batch deleted') WHERE batch_id = %s AND status = 'queued'",
                (batch_id,),
            ).rowcount
            retries = conn.execute(
                "UPDATE call_reschedule_queue SET status = 'Cancelled', ai_note = 'Batch deleted' "
                "WHERE batch_id = %s AND status = 'Queued' AND type IN ('no_lift_retry', 'busy_retry')",
                (batch_id,),
            ).rowcount
            conn.execute("DELETE FROM call_batches WHERE id = %s", (batch_id,))
        return {"cancelled": cancelled, "retriesCancelled": retries}

    def cancel_call(self, tenant_id: str, call_id: str) -> str:
        """Takes one waiting customer out of their campaign before they are called."""
        with self.connection() as conn, conn.transaction():
            row = conn.execute(
                "UPDATE outbound_calls SET status = 'cancelled', ended_at = CURRENT_TIMESTAMP, "
                "notes = 'Removed from the campaign' WHERE tenant_id = %s AND id = %s AND status = 'queued' "
                "RETURNING customer_name, batch_id",
                (tenant_id, call_id),
            ).fetchone()
            if not row:
                raise ValueError("This call is already being made or has finished")
            if row["batch_id"]:
                self._update_batch(conn, row["batch_id"])
        return row["customer_name"]

    def delete_campaign_contacts(self, tenant_id: str, contact_ids: list[str]) -> list[str]:
        """Removes several contacts at once; returns the ids that were deleted."""
        with self.connection() as conn:
            rows = conn.execute(
                "DELETE FROM campaign_contacts WHERE tenant_id = %s AND id = ANY(%s) RETURNING id",
                (tenant_id, contact_ids),
            ).fetchall()
        return [r["id"] for r in rows]

    def add_campaign_contact(self, tenant_id: str, c: dict) -> str:
        from dialer import phone_e164
        phone = phone_e164(c.get("phno", ""))
        if not phone:
            raise ValueError(f"Not an Indian mobile number: {c.get('phno')}")
        contact_id = new_id("C")
        with self.connection() as conn:
            retailer = conn.execute(
                "SELECT id FROM retailers WHERE tenant_id = %s AND phone = %s LIMIT 1", (tenant_id, phone)
            ).fetchone()
            conn.execute(
                "INSERT INTO campaign_contacts (id, tenant_id, retailer_id, name, phone, credit_period) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (contact_id, tenant_id, retailer["id"] if retailer else None, c.get("name", ""), phone,
                 c.get("creditPeriod") or "30 Days"),
            )
        return contact_id

    def update_user(self, tenant_id: str, user_id: str, changes: dict) -> None:
        columns = {"n": "name", "e": "email", "role": "role", "ph": "phone", "st": "status"}
        valid_roles = frozenset(("OW", "CM", "CE", "AC", "PA", "TA"))
        valid_statuses = frozenset(("Active", "Inactive", "Suspended"))

        sets = {}
        for k, col in columns.items():
            if k in changes:
                val = str(changes[k] or "").strip()
                if col == "role" and val not in valid_roles:
                    raise ValueError(f"Invalid user role: {val}")
                if col == "status" and val not in valid_statuses:
                    raise ValueError(f"Invalid user status: {val}")
                sets[col] = val

        if not sets:
            return
        with self.connection() as conn:
            conn.execute(
                f"UPDATE users SET {', '.join(f'{c} = %s' for c in sets)} WHERE tenant_id = %s AND id = %s",
                (*sets.values(), tenant_id, user_id),
            )
