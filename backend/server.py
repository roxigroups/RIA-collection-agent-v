"""API for the ria-ui dashboard (../frontend, a Next.js app that forwards /api
here), and the dialer that places queued calls through Vobiz.

Users sign in with their email and password (the `users` table) and see only
their own company's data. What a role may change follows the dashboard's
permission table (PERM below, same as frontend/src/data/mockData.ts).
"""
import asyncio
import functools
import hashlib
import logging
import os
import secrets
import threading
import time

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, session

load_dotenv()

from dashboard_db import Dashboard  # noqa: E402
from dialer import Dialer  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ria-server")

MAX_IMPORT_ROWS = 5000

# F = full, A = act, V = view only, X = no access
PERM = {
    "dashboard":   {"OW": "F", "CM": "F", "CE": "V", "AC": "F", "PA": "V", "TA": "F"},
    "collections": {"OW": "F", "CM": "F", "CE": "F", "AC": "V", "PA": "V", "TA": "V"},
    "calls":       {"OW": "F", "CM": "F", "CE": "V", "AC": "X", "PA": "V", "TA": "F"},
    "reschedule":  {"OW": "F", "CM": "F", "CE": "F", "AC": "V", "PA": "V", "TA": "F"},
    "retailers":   {"OW": "F", "CM": "F", "CE": "F", "AC": "V", "PA": "V", "TA": "F"},
    "tickets":     {"OW": "F", "CM": "F", "CE": "F", "AC": "F", "PA": "V", "TA": "F"},
    "contacts":    {"OW": "F", "CM": "F", "CE": "F", "AC": "F", "PA": "V", "TA": "F"},
}
# Users and company settings: owner and tenant admin only
ADMIN_ROLES = ("OW", "TA")

DB = Dashboard()
dialer = Dialer(DB)

app = Flask(__name__, static_folder=None)
flask_secret = os.getenv("FLASK_SECRET_KEY", "").strip()
if not flask_secret:
    logger.warning(
        "FLASK_SECRET_KEY is not set in environment. Generating a secure ephemeral key in memory. "
        "Define FLASK_SECRET_KEY in production to preserve user sessions across server restarts."
    )
    flask_secret = secrets.token_hex(32)
app.secret_key = flask_secret
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    # Set SESSION_COOKIE_SECURE=1 once the dashboard is served over HTTPS
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
)


def current_user() -> dict | None:
    user_id = session.get("user_id")
    return DB.get_user(user_id) if user_id else None


def signed_in(screen: str | None = None, admin: bool = False):
    """Requires a signed-in user; with `screen`, one allowed to act there (F/A)."""
    def wrap(view):
        @functools.wraps(view)
        def inner(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error": "Sign in first"}), 401
            if admin and user["role"] not in ADMIN_ROLES:
                return jsonify({"error": "Only the owner or tenant admin can change this"}), 403
            if screen and PERM[screen].get(user["role"]) not in ("F", "A"):
                return jsonify({"error": "Your role can only view this"}), 403
            g.user = user
            return view(*args, **kwargs)
        return inner
    return wrap


def body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def audit(action: str, resource: str, resource_id: str, details: dict | None = None) -> None:
    DB.audit(g.user["tenant_id"], g.user["id"], action, resource, resource_id, details)


@app.errorhandler(ValueError)
def bad_request(exc: ValueError):
    return jsonify({"error": str(exc)}), 400


ALLOWED_ORIGINS = {
    f"http://localhost:{os.getenv('FRONTEND_PORT', '3000')}",
    f"http://127.0.0.1:{os.getenv('FRONTEND_PORT', '3000')}",
    f"http://localhost:{os.getenv('PORT', '5001')}",
    f"http://127.0.0.1:{os.getenv('PORT', '5001')}",
}
for env_key in ("APP_URL", "FRONTEND_URL", "ALLOWED_ORIGINS"):
    val = os.getenv(env_key, "").strip()
    if val:
        for item in val.split(","):
            cleaned = item.strip().rstrip("/")
            if cleaned:
                ALLOWED_ORIGINS.add(cleaned)


@app.before_request
def validate_origin():
    # Defend against Cross-Site Request Forgery (CSRF) on state-modifying requests
    if request.method in ("POST", "PATCH", "PUT", "DELETE"):
        origin = request.headers.get("Origin")
        if origin:
            cleaned = origin.rstrip("/")
            if cleaned not in ALLOWED_ORIGINS and not cleaned.endswith(request.host):
                logger.warning("Blocked request from untrusted origin: %s (host: %s)", origin, request.host)
                return jsonify({"error": "Untrusted request origin"}), 403


def get_dialer_status() -> dict:
    """Returns cluster-wide dialer status from system_state, or falls back to
    the in-process dialer instance."""
    state = DB.get_system_state("dialer", max_age_seconds=30)
    if state:
        return state
    return dialer.status()


@app.get("/health")
def health():
    db_ok = False
    db_error = None
    try:
        with DB.connection() as conn:
            conn.execute("SELECT 1")
            db_ok = True
    except Exception as exc:
        db_error = str(exc)

    dialer_state = DB.get_system_state("dialer", max_age_seconds=60)
    is_healthy = db_ok
    return jsonify({
        "status": "healthy" if is_healthy else "degraded",
        "service": "ria-api",
        "database": {"connected": db_ok, "error": db_error},
        "dialer": dialer_state or {"mode": "in_process", **dialer.status()},
    }), 200 if is_healthy else 503


# -- sign-in -------------------------------------------------------------------------

@app.get("/api/session")
def get_session():
    user = current_user()
    return jsonify({"signed_in": bool(user), "user": {
        "id": user["id"], "n": user["name"], "e": user["email"], "role": user["role"], "company": user["company"],
    } if user else None})


@app.post("/api/login")
def login():
    data = body()
    user = DB.authenticate(str(data.get("email", "")), str(data.get("password", "")))
    if not user:
        time.sleep(1)  # slows down password guessing
        return jsonify({"error": "Wrong email or password"}), 401
    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"signed_in": True, "user": {
        "id": user["id"], "n": user["name"], "e": user["email"], "role": user["role"], "company": user["company"],
    }})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"signed_in": False})


# -- everything the dashboard shows ----------------------------------------------------

@app.get("/api/state")
@signed_in()
def state():
    data = DB.state(g.user["tenant_id"], g.user)
    data["dialer"] = get_dialer_status()
    return jsonify(data)


# -- call campaign ---------------------------------------------------------------------

@app.post("/api/batches")
@signed_in("calls")
def import_batch():
    """Imports a call sheet: one call per valid invoice row. The calls wait for
    "Start calling" (POST /api/batches/<id>/start) unless {"start": true}."""
    data = body()
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        return jsonify({"error": "No rows to call"}), 400
    if len(rows) > MAX_IMPORT_ROWS:
        return jsonify({"error": f"At most {MAX_IMPORT_ROWS} rows per import"}), 400
    result = DB.import_batch(
        g.user["tenant_id"], g.user, str(data.get("fileName") or "call_sheet.csv")[:200],
        str(data.get("name") or "")[:200], [r for r in rows if isinstance(r, dict)],
        start=data.get("start") is True,
        recent=data.get("recent") if data.get("recent") in ("call", "skip") else "ask",
    )
    if result["batch"]:
        audit("import_batch", "call_batch", result["batch"], {"queued": result["queued"],
                                                              "skipped": len(result["skipped"])})
    return jsonify(result)


@app.get("/api/batches/<batch_id>/sheet")
@signed_in()
def batch_sheet(batch_id: str):
    """The whole imported sheet with each row's call state (the campaign dialer screen)."""
    if PERM["calls"].get(g.user["role"]) == "X":
        return jsonify({"error": "Your role can't see the call campaign"}), 403
    return jsonify({"rows": DB.batch_sheet(g.user["tenant_id"], batch_id), "dialer": get_dialer_status()})


@app.delete("/api/batches/<batch_id>")
@signed_in("calls")
def delete_batch(batch_id: str):
    result = DB.delete_batch(g.user["tenant_id"], batch_id)
    audit("delete_batch", "call_batch", batch_id, result)
    return jsonify(result)


@app.post("/api/calls/<call_id>/cancel")
@signed_in("calls")
def cancel_call(call_id: str):
    """Takes one waiting customer out of their campaign."""
    name = DB.cancel_call(g.user["tenant_id"], call_id)
    audit("cancel_call", "outbound_call", call_id)
    return jsonify({"name": name})


@app.post("/api/batches/<batch_id>/start")
@signed_in("calls")
def start_batch(batch_id: str):
    """Calls the batch's customers one after another, in the order of the sheet."""
    waiting = DB.set_batch_dialing(g.user["tenant_id"], batch_id, True)
    audit("start_batch", "call_batch", batch_id, {"waiting": waiting})
    return jsonify({"waiting": waiting, "dialer": dialer.status()})


@app.post("/api/batches/<batch_id>/pause")
@signed_in("calls")
def pause_batch(batch_id: str):
    """No new calls from this batch; a call already on the line finishes."""
    waiting = DB.set_batch_dialing(g.user["tenant_id"], batch_id, False)
    audit("pause_batch", "call_batch", batch_id, {"waiting": waiting})
    return jsonify({"waiting": waiting})


@app.post("/api/calls/<call_id>/dial")
@signed_in("calls")
def dial_call(call_id: str):
    """Dials one waiting customer next, even if their batch hasn't been started."""
    who = DB.dial_call_now(g.user["tenant_id"], call_id)
    audit("dial_now", "outbound_call", call_id)
    return jsonify({**who, "dialer": get_dialer_status()})


@app.get("/api/live")
@signed_in()
def live():
    """Who is on a call right now and who is next (the Call Campaign screen polls this)."""
    if PERM["calls"].get(g.user["role"]) == "X":
        return jsonify({"error": "Your role can't see the call campaign"}), 403
    return jsonify({**DB.live(g.user["tenant_id"]), "dialer": get_dialer_status()})


@app.post("/api/contacts/<contact_id>/call")
@signed_in("contacts")
def call_contact(contact_id: str):
    call_id = DB.queue_contact_call(g.user["tenant_id"], contact_id)
    audit("queue_call", "campaign_contact", contact_id, {"call": call_id})
    return jsonify({"queued": 1})


@app.post("/api/retailers/<retailer_id>/call")
@signed_in("retailers")
def call_retailer(retailer_id: str):
    call_id = DB.queue_retailer_call(g.user["tenant_id"], retailer_id)
    audit("queue_call", "retailer", retailer_id, {"call": call_id})
    return jsonify({"queued": 1})


# -- retries and callbacks --------------------------------------------------------------

@app.post("/api/callbacks/<queue_id>/dial")
@signed_in("reschedule")
def dial_now(queue_id: str):
    DB.dial_now(g.user["tenant_id"], queue_id)
    audit("dial_now", "call_reschedule_queue", queue_id)
    return jsonify({"ok": True})


@app.post("/api/callbacks/<queue_id>/reschedule")
@signed_in("reschedule")
def reschedule(queue_id: str):
    data = body()
    DB.reschedule(g.user["tenant_id"], queue_id, str(data.get("time", "")), data.get("note"))
    audit("reschedule", "call_reschedule_queue", queue_id, {"time": data.get("time")})
    return jsonify({"ok": True})


@app.post("/api/callbacks/<queue_id>/cancel")
@signed_in("reschedule")
def cancel_callback(queue_id: str):
    reason = str(body().get("reason") or "Cancelled by user")[:200]
    DB.cancel_callback(g.user["tenant_id"], queue_id, reason)
    audit("cancel", "call_reschedule_queue", queue_id, {"reason": reason})
    return jsonify({"ok": True})


# -- tickets ------------------------------------------------------------------------------

@app.post("/api/tickets")
@signed_in("tickets")
def add_ticket():
    ticket_id = DB.add_ticket(g.user["tenant_id"], body())
    audit("add_ticket", "ticket", ticket_id)
    return jsonify({"id": ticket_id})


@app.patch("/api/tickets/<ticket_id>")
@signed_in("tickets")
def update_ticket(ticket_id: str):
    changes = body()
    DB.update_ticket(g.user["tenant_id"], ticket_id, changes)
    audit("update_ticket", "ticket", ticket_id, changes)
    return jsonify({"ok": True})


# -- contacts -----------------------------------------------------------------------------

@app.post("/api/campaign-contacts")
@signed_in("contacts")
def add_campaign_contact():
    contact_id = DB.add_campaign_contact(g.user["tenant_id"], body())
    return jsonify({"id": contact_id})


@app.post("/api/campaign-contacts/delete")
@signed_in("contacts")
def delete_campaign_contacts():
    ids = [str(i) for i in body().get("ids") or [] if i][:2000]
    if not ids:
        raise ValueError("No contacts selected")
    deleted = DB.delete_campaign_contacts(g.user["tenant_id"], ids)
    for contact_id in deleted:
        audit("delete_contact", "campaign_contact", contact_id)
    return jsonify({"deleted": len(deleted)})


# -- users and settings (owner / tenant admin) ------------------------------------------

@app.patch("/api/users/<user_id>")
@signed_in(admin=True)
def update_user(user_id: str):
    changes = body()
    acting_user = g.user
    target_user = DB.get_user(user_id)
    if not target_user:
        return jsonify({"error": "User not found"}), 404

    # Security check: Only the company Owner ('OW') can assign the Owner role
    if changes.get("role") == "OW" and acting_user["role"] != "OW":
        return jsonify({"error": "Only the company Owner can assign the Owner role"}), 403

    # Security check: Non-Owners cannot demote or alter an Owner's role or status
    if target_user["role"] == "OW" and acting_user["role"] != "OW":
        if any(k in changes for k in ("role", "st", "status")):
            return jsonify({"error": "Only the Owner can modify Owner permissions or status"}), 403

    DB.update_user(acting_user["tenant_id"], user_id, changes)
    audit("update_user", "user", user_id, {k: v for k, v in changes.items() if k != "password"})
    return jsonify({"ok": True})


def start_dialer() -> None:
    if os.getenv("DIALER_STANDALONE", "0") == "1":
        logger.info("DIALER_STANDALONE=1: Dialer managed as a separate daemon; skipping in-process thread.")
        return
    threading.Thread(target=lambda: asyncio.run(dialer.run()), name="dialer", daemon=True).start()


if __name__ == "__main__":
    start_dialer()
    app.run(host=os.getenv("API_HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5001")), debug=False)
