"""API for the ria-ui dashboard (../frontend, a Next.js app that forwards /api
here), and the dialer that places queued calls through Vobiz.

Users sign in with their email and password (the `users` table) and see only
their own company's data. What a role may change follows the dashboard's
permission table (PERM below, same as frontend/src/data/mockData.ts).
"""
import asyncio
import functools
import hashlib
import hmac
import logging
import os
import re
import secrets
import threading
import time

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, session

load_dotenv()

import email_service  # noqa: E402
from dashboard_db import Dashboard  # noqa: E402
from dialer import Dialer  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ria-server")

MAX_IMPORT_ROWS = 100

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
    wallet = DB.get_tenant_billing(user["tenant_id"]) if user and user.get("tenant_id") else {}
    return jsonify({"signed_in": bool(user), "user": {
        "id": user["id"], "n": user["name"], "e": user["email"], "role": user["role"], "company": user["company"],
        "is_superadmin": DB.is_superadmin(user["email"]),
        "billing_status": user.get("billing_status") or "active",
        "plan": user.get("plan") or "starter",
        "wallet_balance_inr": wallet.get("balance_inr", 0.0),
        "wallet_balance_paise": wallet.get("balance_paise", 0),
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
    wallet = DB.get_tenant_billing(user["tenant_id"]) if user.get("tenant_id") else {}
    return jsonify({"signed_in": True, "user": {
        "id": user["id"], "n": user["name"], "e": user["email"], "role": user["role"], "company": user["company"],
        "is_superadmin": DB.is_superadmin(user["email"]),
        "billing_status": user.get("billing_status") or "active",
        "plan": user.get("plan") or "starter",
        "wallet_balance_inr": wallet.get("balance_inr", 0.0),
        "wallet_balance_paise": wallet.get("balance_paise", 0),
    }})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"signed_in": False})


# -- self-service sign-up & password reset --------------------------------------------

def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


def _is_valid_password(password: str) -> bool:
    return len(password) >= 8 and any(c.isalpha() for c in password) and any(c.isdigit() for c in password)


@app.post("/api/auth/register/request")
def register_request():
    data = body()
    company_name = str(data.get("companyName", "")).strip()
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))

    if not company_name or not name or not email or not password:
        return jsonify({"error": "Company name, full name, email, and password are required."}), 400
    if not _is_valid_email(email):
        return jsonify({"error": "Please enter a valid email address."}), 400
    if not _is_valid_password(password):
        return jsonify({"error": "Password must be at least 8 characters long and contain both letters and numbers."}), 400
    if DB.email_exists(email):
        return jsonify({"error": "An account with this email already exists. Please sign in."}), 400

    code = f"{secrets.randbelow(900000) + 100000}"
    payload = {
        "companyName": company_name,
        "name": name,
        "email": email,
        "phone": phone,
        "password": password,
    }
    DB.create_auth_verification(email, "signup", code, payload, ttl_minutes=15)
    sent = email_service.send_signup_otp(email, name, code)
    if not sent:
        logger.warning("Failed to send signup OTP email to %s", email)
    return jsonify({"ok": True, "message": f"Verification code sent to {email}"})


@app.post("/api/auth/register/confirm")
def register_confirm():
    data = body()
    email = str(data.get("email", "")).strip().lower()
    code = str(data.get("code", "")).strip()

    if not email or not code:
        return jsonify({"error": "Email and verification code are required."}), 400

    valid, payload, err = DB.verify_auth_code(email, "signup", code)
    if not valid or not payload:
        return jsonify({"error": err or "Invalid verification code"}), 400

    try:
        user = DB.complete_registration(payload)
    except Exception as exc:
        logger.exception("Failed to complete registration for %s: %s", email, exc)
        return jsonify({"error": str(exc)}), 400

    session.clear()
    session["user_id"] = user["id"]
    return jsonify({
        "signed_in": True,
        "user": {
            "id": user["id"],
            "n": user["name"],
            "e": user["email"],
            "role": user["role"],
            "company": user["company"],
            "is_superadmin": DB.is_superadmin(user["email"]),
            "billing_status": user.get("billing_status") or "pending_platform_fee",
            "plan": user.get("plan") or "starter",
        }
    })


@app.post("/api/auth/forgot-password/request")
def forgot_password_request():
    data = body()
    email = str(data.get("email", "")).strip().lower()
    if not email or not _is_valid_email(email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    user = DB.get_user_by_email(email)
    if not user:
        # Prevent email enumeration: return standard success message
        return jsonify({"ok": True, "message": "If an account exists with this email, a reset code has been sent."})

    code = f"{secrets.randbelow(900000) + 100000}"
    DB.create_auth_verification(email, "password_reset", code, ttl_minutes=15)
    sent = email_service.send_password_reset_otp(email, user["name"], code)
    if not sent:
        logger.warning("Failed to send password reset OTP email to %s", email)
    return jsonify({"ok": True, "message": "If an account exists with this email, a reset code has been sent."})


@app.post("/api/auth/forgot-password/confirm")
def forgot_password_confirm():
    data = body()
    email = str(data.get("email", "")).strip().lower()
    code = str(data.get("code", "")).strip()
    new_password = str(data.get("newPassword", ""))

    if not email or not code or not new_password:
        return jsonify({"error": "Email, reset code, and new password are required."}), 400
    if not _is_valid_password(new_password):
        return jsonify({"error": "Password must be at least 8 characters long and contain both letters and numbers."}), 400

    valid, _, err = DB.verify_auth_code(email, "password_reset", code)
    if not valid:
        return jsonify({"error": err or "Invalid reset code"}), 400

    updated = DB.reset_password(email, new_password)
    if not updated:
        return jsonify({"error": "User account not found."}), 404

    return jsonify({"ok": True, "message": "Password updated successfully. You can now sign in."})


# -- everything the dashboard shows ----------------------------------------------------

@app.get("/api/state")
@signed_in()
def state():
    data = DB.state(g.user["tenant_id"], g.user)
    data["dialer"] = get_dialer_status()
    try:
        billing = DB.get_tenant_billing(g.user["tenant_id"])
        if "me" in data and isinstance(data["me"], dict):
            data["me"]["billing_status"] = billing.get("billing_status", "active")
            data["me"]["plan"] = billing.get("plan", "starter")
            data["me"]["wallet_balance_inr"] = billing.get("balance_inr", 0.0)
            data["me"]["wallet_balance_paise"] = billing.get("balance_paise", 0)
        data["wallet"] = billing
    except Exception as exc:
        logger.warning("Could not append billing to state: %s", exc)
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
        return jsonify({"error": f"At most {MAX_IMPORT_ROWS} contacts per import"}), 400
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


# -- Super Admin Endpoints ----------------------------------------------------

def superadmin_only(view):
    @functools.wraps(view)
    def inner(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "Sign in first"}), 401
        if not DB.is_superadmin(user["email"]):
            return jsonify({"error": "Platform superadmin access required"}), 403
        g.user = user
        return view(*args, **kwargs)
    return inner


def _sync_livekit_trunk():
    """Background helper to sync active numbers with LiveKit SIP Outbound Trunk if configured."""
    trunk_id = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID", "").strip()
    if not trunk_id or not os.getenv("LIVEKIT_URL"):
        return

    def _worker():
        try:
            from livekit import api as lk_api
            active_numbers = DB.get_active_telephony_numbers()
            async def _run():
                lk = lk_api.LiveKitAPI()
                try:
                    trunks = (await lk.sip.list_outbound_trunk(lk_api.ListSIPOutboundTrunkRequest())).items
                    found = next((t for t in trunks if t.sip_trunk_id == trunk_id), None)
                    if found:
                        found.numbers = active_numbers
                        await lk.sip.update_outbound_trunk(found.sip_trunk_id, found)
                        logger.info("Synced LiveKit trunk %s with %d numbers", trunk_id, len(active_numbers))
                finally:
                    await lk.aclose()
            asyncio.run(_run())
        except Exception as exc:
            logger.warning("Could not sync LiveKit trunk numbers: %s", exc)

    threading.Thread(target=_worker, name="sync-livekit-trunk", daemon=True).start()


@app.get("/api/admin/overview")
@superadmin_only
def admin_overview():
    data = DB.get_admin_overview()
    data["dialer"] = dialer.status()
    return jsonify(data)


@app.get("/api/admin/numbers")
@superadmin_only
def admin_get_numbers():
    numbers = DB.get_telephony_numbers()
    active_per_number = dialer.active_per_number
    for n in numbers:
        n["active_calls"] = active_per_number.get(n["phone_number"], 0)
    return jsonify({"numbers": numbers})


@app.post("/api/admin/numbers")
@superadmin_only
def admin_add_number():
    data = body()
    phone = str(data.get("phone_number", "")).strip()
    label = str(data.get("label", "")).strip()
    daily_limit = int(data.get("daily_limit") or 250)
    if not phone or len(phone) < 10:
        return jsonify({"error": "Valid phone number in E.164 format (e.g. +918064269997) is required"}), 400
    try:
        record = DB.add_telephony_number(phone, label=label, daily_limit=daily_limit)
        _sync_livekit_trunk()
        return jsonify({"success": True, "number": record})
    except Exception as exc:
        logger.exception("Failed to add telephony number")
        return jsonify({"error": str(exc)}), 500


@app.patch("/api/admin/numbers/<num_id>")
@superadmin_only
def admin_update_number(num_id: str):
    data = body()
    try:
        updated = DB.update_telephony_number(num_id, data)
        if not updated:
            return jsonify({"error": "Number not found"}), 404
        _sync_livekit_trunk()
        return jsonify({"success": True, "number": updated})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.delete("/api/admin/numbers/<num_id>")
@superadmin_only
def admin_delete_number(num_id: str):
    try:
        DB.delete_telephony_number(num_id)
        _sync_livekit_trunk()
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/api/admin/tenants")
@superadmin_only
def admin_get_tenants():
    tenants = DB.get_admin_tenants()
    return jsonify({"tenants": tenants})


@app.post("/api/admin/tenants")
@superadmin_only
def admin_create_tenant():
    data = body()
    name = str(data.get("name", "")).strip()
    admin_name = str(data.get("admin_name", "")).strip()
    admin_email = str(data.get("admin_email", "")).strip()
    password = str(data.get("password", "")).strip()
    rules = data.get("rules") or {}
    if not name or not admin_email or not password:
        return jsonify({"error": "Company name, admin email, and password are required"}), 400
    if not _is_valid_email(admin_email):
        return jsonify({"error": "Enter a valid email address"}), 400
    if not _is_valid_password(password):
        return jsonify({"error": "Password must be at least 8 characters with a letter and a number"}), 400
    if DB.email_exists(admin_email):
        return jsonify({"error": "A user with this email already exists"}), 409
    try:
        tenant = DB.create_tenant_with_admin(name, admin_name or name, admin_email, password, rules=rules)
        return jsonify({"success": True, "tenant": tenant})
    except Exception as exc:
        logger.exception("Failed to create tenant")
        return jsonify({"error": str(exc)}), 500


@app.get("/api/admin/team")
@superadmin_only
def admin_get_team():
    emails = sorted(list(DB.DEFAULT_SUPERADMINS | {e.strip().lower() for e in os.getenv("SUPERADMIN_EMAILS", "").split(",") if e.strip()}))
    return jsonify({"admins": emails})


# -- razorpay billing & platform activation -----------------------------------

PLAN_PRICES = {
    "starter": 499900,  # ₹4,999 in paise
    "pro": 799900,      # ₹7,999 in paise
}


@app.get("/api/billing/status")
def billing_status():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    status = DB.get_tenant_billing(user["tenant_id"])
    return jsonify({
        "tenant_id": user["tenant_id"],
        "is_superadmin": DB.is_superadmin(user["email"]),
        **status,
    })


@app.post("/api/create-order")
@app.post("/api/billing/create-order")
def create_order():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = body()
    plan_id = str(data.get("plan_id", "starter")).lower().strip()
    if plan_id not in PLAN_PRICES and "amount" not in data:
        return jsonify({"error": f"Invalid plan '{plan_id}'. Choose 'starter' or 'pro'"}), 400

    amount_paise = data.get("amount")
    if amount_paise is not None:
        try:
            amount_paise = int(amount_paise)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid amount"}), 400
    else:
        amount_paise = PLAN_PRICES.get(plan_id, 499900)

    if amount_paise < 100:
        return jsonify({"error": "Amount must be at least 100 paise (₹1.00)"}), 400

    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_id or not key_secret:
        return jsonify({"error": "Razorpay credentials not configured on server"}), 500

    receipt = f"rcpt_{user['tenant_id']}_{secrets.token_hex(4)}"
    try:
        import razorpay
        client = razorpay.Client(auth=(key_id, key_secret))
        order_params = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": {
                "tenant_id": user["tenant_id"],
                "user_id": user["id"],
                "plan_id": plan_id,
                "company": user.get("company", ""),
            },
        }
        order = client.order.create(data=order_params)
        order_id = order["id"]
        DB.record_billing_order(user["tenant_id"], plan_id, amount_paise, order_id)
        return jsonify({
            "order_id": order_id,
            "amount": amount_paise,
            "currency": "INR",
            "key_id": key_id,
            "plan_id": plan_id,
        })
    except Exception as exc:
        logger.exception("Failed to create Razorpay order: %s", exc)
        return jsonify({"error": f"Failed to create order: {str(exc)}"}), 500


@app.post("/api/verify-payment")
@app.post("/api/billing/verify-payment")
def verify_payment():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = body()
    order_id = str(data.get("razorpay_order_id") or data.get("order_id", "")).strip()
    payment_id = str(data.get("razorpay_payment_id") or data.get("payment_id", "")).strip()
    signature = str(data.get("razorpay_signature") or data.get("signature", "")).strip()
    plan_id = str(data.get("plan_id", "starter")).lower().strip()
    amount_paise = int(data.get("amount", PLAN_PRICES.get(plan_id, 499900)))

    if not order_id or not payment_id or not signature:
        return jsonify({"error": "Missing razorpay_order_id, razorpay_payment_id, or razorpay_signature"}), 400

    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_secret:
        return jsonify({"error": "Razorpay secret not configured on server"}), 500

    # Algorithm: HMAC-SHA256(order_id + "|" + payment_id, KEY_SECRET)
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    expected_signature = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        logger.warning("Signature mismatch for order %s: expected %s, got %s", order_id, expected_signature, signature)
        return jsonify({"error": "Payment signature verification failed. Unauthorized signature."}), 400

    try:
        result = DB.verify_and_activate_platform(
            tenant_id=user["tenant_id"],
            plan_id=plan_id,
            amount_paise=amount_paise,
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
            welcome_bonus_paise=30000,  # ₹300.00 calling credits
        )
        return jsonify({
            "success": True,
            "message": "Payment verified! Workspace activated and ₹300 welcome credits added.",
            "data": result,
        })
    except Exception as exc:
        logger.exception("Failed to activate workspace after payment verification: %s", exc)
        return jsonify({"error": f"Failed to activate workspace: {str(exc)}"}), 500


@app.get("/api/billing/wallet")
def billing_wallet():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    billing = DB.get_tenant_billing(user["tenant_id"])
    ledger = DB.get_wallet_ledger(user["tenant_id"], limit=50)
    transactions = DB.get_billing_transactions(user["tenant_id"], limit=20)
    return jsonify({
        "tenant_id": user["tenant_id"],
        "balance_paise": billing.get("balance_paise", 0),
        "balance_inr": billing.get("balance_inr", 0.0),
        "rate_per_minute_inr": 3.0,
        "plan": billing.get("plan", "starter"),
        "billing_status": billing.get("billing_status", "active"),
        "platform_fee_paid_at": billing.get("platform_fee_paid_at"),
        "ledger": ledger,
        "transactions": transactions,
    })


@app.post("/api/topup-order")
@app.post("/api/billing/topup-order")
@app.post("/api/billing/topup/order")
def topup_order():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = body()
    amount_inr = data.get("amount_inr")
    amount_paise = data.get("amount_paise")
    if amount_inr is not None:
        try:
            amount_paise = int(round(float(amount_inr) * 100))
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid amount"}), 400
    elif amount_paise is not None:
        try:
            amount_paise = int(amount_paise)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid amount"}), 400
    else:
        return jsonify({"error": "Missing amount_inr or amount_paise"}), 400

    if amount_paise < 10000:  # Minimum ₹100
        return jsonify({"error": "Minimum top-up amount is ₹100"}), 400

    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_id or not key_secret:
        return jsonify({"error": "Razorpay credentials not configured on server"}), 500

    receipt = f"top_{user['tenant_id'][:8]}_{secrets.token_hex(4)}"
    try:
        import razorpay
        client = razorpay.Client(auth=(key_id, key_secret))
        order_params = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "notes": {
                "type": "wallet_topup",
                "tenant_id": user["tenant_id"],
                "user_id": user["id"],
                "company": user.get("company", ""),
            },
        }
        order = client.order.create(data=order_params)
        order_id = order["id"]
        DB.record_topup_order(user["tenant_id"], amount_paise, order_id)
        return jsonify({
            "order_id": order_id,
            "amount": amount_paise,
            "currency": "INR",
            "key_id": key_id,
        })
    except Exception as exc:
        logger.exception("Failed to create Razorpay top-up order: %s", exc)
        return jsonify({"error": f"Failed to create order: {str(exc)}"}), 500


@app.post("/api/verify-topup")
@app.post("/api/billing/verify-topup")
@app.post("/api/billing/topup/verify")
def topup_verify():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    data = body()
    order_id = str(data.get("razorpay_order_id") or data.get("order_id", "")).strip()
    payment_id = str(data.get("razorpay_payment_id") or data.get("payment_id", "")).strip()
    signature = str(data.get("razorpay_signature") or data.get("signature", "")).strip()
    amount_paise = data.get("amount")
    try:
        amount_paise = int(amount_paise) if amount_paise is not None else 0
    except (ValueError, TypeError):
        amount_paise = 0

    if not order_id or not payment_id or not signature:
        return jsonify({"error": "Missing razorpay_order_id, razorpay_payment_id, or razorpay_signature"}), 400

    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_secret:
        return jsonify({"error": "Razorpay secret not configured on server"}), 500

    msg = f"{order_id}|{payment_id}".encode("utf-8")
    expected_signature = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        logger.warning("Topup signature mismatch for order %s: expected %s, got %s", order_id, expected_signature, signature)
        return jsonify({"error": "Payment signature verification failed. Unauthorized signature."}), 400

    try:
        result = DB.verify_and_topup_wallet(
            tenant_id=user["tenant_id"],
            amount_paise=amount_paise,
            order_id=order_id,
            payment_id=payment_id,
            signature=signature,
        )
        return jsonify({
            "success": True,
            "message": f"Successfully recharged ₹{result['balance_inr']:.2f} calling credits!",
            "data": result,
        })
    except Exception as exc:
        logger.exception("Failed to top up wallet after payment verification: %s", exc)
        return jsonify({"error": f"Failed to top up wallet: {str(exc)}"}), 500


def start_dialer() -> None:
    if os.getenv("DIALER_STANDALONE", "0") == "1":
        logger.info("DIALER_STANDALONE=1: Dialer managed as a separate daemon; skipping in-process thread.")
        return
    threading.Thread(target=lambda: asyncio.run(dialer.run()), name="dialer", daemon=True).start()


if __name__ == "__main__":
    start_dialer()
    app.run(host=os.getenv("API_HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5001")), debug=False)
