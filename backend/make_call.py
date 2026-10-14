import asyncio
import json
import logging
import os
import sys
import time

# Ensure backend directory is in path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

# Allow calling outside 8-19 IST calling hours
os.environ["RIA_TEST_ANY_HOUR"] = "1"

from dashboard_db import Dashboard
from dialer import Dialer
from livekit import api

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("make-call")

async def main():
    db = Dashboard()
    dialer = Dialer(db)

    phone = sys.argv[1] if len(sys.argv) > 1 else "+919618580574"
    lang = sys.argv[2] if len(sys.argv) > 2 else "te"
    customer_name = sys.argv[3] if len(sys.argv) > 3 else "Test Customer"
    amount = sys.argv[4] if len(sys.argv) > 4 else "15000"

    # Normalize phone: keep digits and ensure +91 prefix
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) == 10:
        phone = f"+91{digits}"
    elif not phone.startswith("+"):
        phone = f"+{digits}"

    # Get first tenant and user from database
    with db.connection() as conn:
        tenant_row = conn.execute("SELECT id FROM tenants ORDER BY id LIMIT 1").fetchone()
        tenant_id = (tenant_row.get("id") if isinstance(tenant_row, dict) else tenant_row[0]) if tenant_row else "TENANT-001"
        user_row = conn.execute("SELECT id, name FROM users WHERE tenant_id = %s LIMIT 1", (tenant_id,)).fetchone()
        if user_row:
            u_id = user_row.get("id") if isinstance(user_row, dict) else user_row[0]
            u_name = user_row.get("name") if isinstance(user_row, dict) else user_row[1]
            user_info = {"id": u_id, "name": u_name}
        else:
            user_info = {"id": "U-ADMIN", "name": "Admin"}

    print(f"Step 1: Queuing test call for {customer_name} ({phone}) in '{lang}' for ₹{amount}...")
    result = db.import_batch(
        tenant_id=tenant_id,
        user=user_info,
        file_name="cli_test_call.csv",
        name=f"Test Call - {customer_name}",
        rows=[{
            "businessName": customer_name,
            "name": customer_name,
            "phone": phone,
            "invoiceNumber": f"INV-TEST-{int(time.time()) % 10000}",
            "invoiceAmount": amount,
            "invoiceDate": "2026-10-15",
            "lang": lang,
        }],
        status="queued",
        start=True,
        recent="call",
    )
    print(f"Batch imported: {result}")

    # Find the queued call
    with db.connection() as conn:
        call_row = conn.execute(
            """
            SELECT id FROM outbound_calls 
            WHERE phone = %s AND status = 'queued' 
            ORDER BY created_at DESC LIMIT 1
            """,
            (phone,),
        ).fetchone()

    if not call_row:
        print("ERROR: Queued call row not found!")
        sys.exit(1)

    call_id = call_row["id"]
    print(f"Call queued with ID: {call_id}")

    call = db.get_collection_call(call_id)
    if not call:
        print(f"ERROR: Could not fetch collection call for ID {call_id}")
        sys.exit(1)

    print(f"Customer: {call['customer_name']} | Phone: {call['phone']} | Invoice: {call['invoice_no']} | Amount: ₹{call['amount']}")

    # Claim call
    if not db.claim_call(call_id):
        print(f"ERROR: Could not claim call {call_id}")
        sys.exit(1)

    print(f"Call {call_id} claimed. Placing call via LiveKit SIP trunk {dialer.trunk_id}...")

    lk = api.LiveKitAPI()
    try:
        await dialer._place_call(lk, call)
        print("Call session finished.")
    finally:
        await lk.aclose()

    # Check outcome from DB
    res = db.get_collection_call(call_id)
    if res:
        print(f"Final Call Status: {res.get('status')} | Outcome: {res.get('outcome')} | Notes: {res.get('notes')}")

if __name__ == "__main__":
    asyncio.run(main())
