"""Outcome codes RIA records, and how each is saved for the dashboard."""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

# Code -> dashboard outcome, the ticket the team acts on, and a label kept in the
# notes when the dashboard outcome is broader than the code
OUTCOME_CODES = {
    "PROMISE_TO_PAY": ("PROMISE-TO-PAY", "", ""),
    "PARTIAL_PAYMENT_PROMISE": ("PROMISE-TO-PAY", "", "Part payment"),
    # The customer says it's paid: accounts match it to the bank either way
    "PAYMENT_MADE": ("ALREADY-PAID", "payment_verification", "Payment made"),
    "PAYMENT_VERIFICATION_REQUIRED": ("ALREADY-PAID", "payment_verification", "Verify payment"),
    "PAYMENT_DATE_UNKNOWN": ("CALLBACK", "", "Payment date unknown"),
    "INVOICE_DISPUTE": ("DISPUTE", "invoice_dispute", ""),
    "DELIVERY_ISSUE": ("DISPUTE", "invoice_dispute", "Delivery issue"),
    "INVOICE_COPY_REQUESTED": ("REQUEST", "account_statement_or_ledger", "Invoice copy requested"),
    "CALLBACK_REQUESTED": ("CALLBACK", "", ""),
    "PAYMENT_REFUSED": ("REFUSED", "payment_refusal", ""),
    "CUSTOMER_UPSET": ("REQUEST", "customer_complaint", "Customer upset"),
    "WRONG_NUMBER": ("WRONG-PERSON", "master_data_correction", ""),
    "DO_NOT_CALL": ("OPT-OUT", "", ""),
    # Wants to pay after the latest allowed date: the team decides
    "EXTENSION_REQUESTED": ("REQUEST", "payment_arrangement_request", "Extension requested"),
    "OTHER": ("CALLBACK", "", "Other"),
}
OutcomeCode = Literal[
    "PROMISE_TO_PAY", "PARTIAL_PAYMENT_PROMISE", "PAYMENT_MADE", "PAYMENT_VERIFICATION_REQUIRED",
    "PAYMENT_DATE_UNKNOWN", "INVOICE_DISPUTE", "DELIVERY_ISSUE", "INVOICE_COPY_REQUESTED",
    "CALLBACK_REQUESTED", "PAYMENT_REFUSED", "CUSTOMER_UPSET", "WRONG_NUMBER", "DO_NOT_CALL",
    "EXTENSION_REQUESTED", "OTHER",
]
# Codes that can be saved before the customer has been verified
SAVE_UNVERIFIED = {"CALLBACK_REQUESTED", "WRONG_NUMBER", "DO_NOT_CALL", "CUSTOMER_UPSET", "OTHER"}


def notes_for(code: str, notes: str, promised: date | None) -> str:
    """The notes as saved: the label, the model's line, and the ticket marker the
    dashboard turns into a ticket."""
    _, ticket, label = OUTCOME_CODES[code]
    # The ticket follows from the code; a model once wrote its own "ticket: ..."
    notes = re.sub(r"[,;|.\s-]*\bticket\b\s*:?.*$", "", (notes or "").strip(), flags=re.I)
    if promised and code in ("PROMISE_TO_PAY", "PARTIAL_PAYMENT_PROMISE"):
        # Notes naming another day than the one saved are replaced (the balance of a part
        # payment is due another day, so its words aren't checked)
        promise, balance = (re.split(r"\s*Balance:", notes, maxsplit=1) + [""])[:2]
        noted = {int(d) for d in re.findall(r"(?<![\d,₹.:-])(\d{1,2})(?:st|nd|rd|th)?(?!\d|,\d|:)", promise)}
        noted |= {int(d) for d in re.findall(r"\d{4}-\d{2}-(\d{2})", promise)}
        if noted - {promised.day}:
            notes = f"Customer confirmed payment on {promised.isoformat()}." + (f" Balance:{balance}" if balance else "")
    if label:
        notes = f"{label}: {notes}" if notes else label
    if ticket:
        notes = f"{notes} | ticket: {ticket}{', high' if ticket == 'payment_refusal' else ''}".lstrip(" |")
    return notes[:300]
