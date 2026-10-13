# RIA database (PostgreSQL)

`schema.sql` is the ria-ui schema, unchanged. `migrations/` holds what the voice
agent adds on top (applied in name order, each once):

- `001_ria_agent.sql` — `outbound_calls` (every dial: queued → dialing → live →
  done), a do-not-call flag on `retailers`, outcome/notes columns on `calls`,
  and monthly `calls` partitions through 2027.

## Set up

```bash
# PostgreSQL 16 locally (macOS): brew install postgresql@16 && brew services start postgresql@16
createdb ria_db                      # or Cloud SQL on GCP
# backend/.env: DATABASE_URL="postgresql://USER:PASS@HOST:5432/ria_db"
python setup_db.py                   # loads schema.sql + migrations (safe to re-run)
python setup_db.py --company "Roxy Group" --admin-name "Vishal T." --admin-email you@example.com
```

The last command prints the owner's password. Add more people to the same
company with `--role CM` (or CE, AC, PA, TA) and their own `--admin-email`;
Team & Permissions on the dashboard edits them afterwards.

## How a call flows through the tables

1. Call sheet import (dashboard) → `call_batches`, `retailers`, `invoices`,
   `campaign_contacts`, and one `outbound_calls` row per invoice.
2. The dialer (`dialer.py`) places due `outbound_calls`, and turns due
   `call_reschedule_queue` items (retries, callbacks) into new ones.
3. The agent (`agent.py`) saves the outcome on its `outbound_calls` row.
4. `db_driver.finalize_call` records the finished call: a `calls` row with the
   transcript, plus `ptp_commitments`, `tickets` or `call_reschedule_queue`
   as the outcome needs, and updated batch totals.

New tables or columns go in a new `migrations/NNN_name.sql`; never edit an
applied file.
