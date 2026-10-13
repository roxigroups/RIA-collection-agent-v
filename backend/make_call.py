import asyncio
import json
import logging
import os
import sys

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

    print("Step 1: Queuing call from template for raheman automobiles (+919618580574)...")
    result = db.import_batch(
        tenant_id="TENANT-001",
        user={"id": "U-1dad3bb6", "name": "Admin"},
        file_name="ria_call_sheet_template.csv",
        name="Raheman Automobiles Test Call",
        rows=[{
            "businessName": "raheman automobiles",
            "name": "raheman automobiles",
            "phone": "9618580574",
            "invoiceNumber": "INV-2026-001",
            "invoiceAmount": "18000",
            "invoiceDate": "2026-10-15",
            "lang": "te",
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
            WHERE phone = '+919618580574' AND status = 'queued' 
            ORDER BY created_at DESC LIMIT 1
            """
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
