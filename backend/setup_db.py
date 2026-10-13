"""Set up the PostgreSQL database (safe to re-run).

Loads database/schema.sql and then database/migrations/*.sql, each exactly once
(schema.sql can't run twice: its types and triggers have no IF NOT EXISTS), and
optionally adds a company (tenant) with its first owner login.

Usage:
  python setup_db.py
  python setup_db.py --company "Roxy Group" --gstin 36AAAAA0000A1Z5 \
      --admin-name "Vishal T." --admin-email vishal@example.com [--admin-password ...]
  # another user of that company
  python setup_db.py --company "Roxy Group" --admin-name "Suresh" --admin-email s@example.com --role CM

Needs DATABASE_URL in backend/.env, e.g. postgresql://ria:secret@localhost:5432/ria_db
"""
import argparse
import os
import secrets
import sys

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Json

load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "database", "schema.sql")
MIGRATIONS = os.path.join(HERE, "database", "migrations")

# Calling rules for a new company: RBI fair-practice hours, 3 tries per number,
# unanswered calls retried after 5 minutes (read by the dialer)
DEFAULT_RULES = {
    "cap": 3,
    "starthour": "08:00",
    "endhour": "19:00",
    "cooldown_minutes": 5,
    "ptpwindow_days": 7,
    "escalate_broken_threshold": 2,
    "blockdispute": True,
    "blockholiday": True,
}


def apply_sql_files(conn: psycopg.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP)"
    )
    done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
    files = [("schema.sql", SCHEMA)] + [
        (name, os.path.join(MIGRATIONS, name))
        for name in sorted(os.listdir(MIGRATIONS)) if name.endswith(".sql")
    ]
    for name, path in files:
        if name in done:
            continue
        with open(path, encoding="utf-8") as f:
            sql = f.read()
        # One transaction per file: a failed file leaves nothing half-applied
        with conn.transaction():
            conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (name,))
        print(f"Applied {name}")


def add_tenant(conn: psycopg.Connection, args: argparse.Namespace) -> None:
    password = args.admin_password or secrets.token_urlsafe(12)
    existing = conn.execute("SELECT id FROM tenants WHERE name = %s", (args.company,)).fetchone()
    if existing:
        # An existing company: add this person as another user
        if conn.execute("SELECT 1 FROM users WHERE lower(email) = lower(%s)", (args.admin_email,)).fetchone():
            sys.exit(f"{args.admin_email} already has a login")
        conn.execute(
            "INSERT INTO users (id, tenant_id, name, email, password_hash, role, phone) "
            "VALUES (%s, %s, %s, %s, crypt(%s, gen_salt('bf')), %s, %s)",
            (f"U-{secrets.token_hex(4)}", existing[0], args.admin_name, args.admin_email.lower(),
             password, args.role, args.admin_phone),
        )
        print(f"Added {args.role} user to {args.company!r}")
        print(f"Login: {args.admin_email.lower()} / {password}")
        return
    count = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
    tenant_id = f"TENANT-{count + 1:03d}"
    with conn.transaction():
        # The schema's default config (voice, rules, general), with our calling rules on top
        conn.execute(
            "INSERT INTO tenants (id, name, gstin, caller_id) VALUES (%s, %s, %s, %s)",
            (tenant_id, args.company, args.gstin or f"PENDING-{tenant_id}", args.caller_id),
        )
        conn.execute(
            "UPDATE tenants SET config = jsonb_set(config, '{rules}', (config->'rules') || %s::jsonb) WHERE id = %s",
            (Json(DEFAULT_RULES), tenant_id),
        )
        conn.execute(
            "INSERT INTO users (id, tenant_id, name, email, password_hash, role, phone) "
            "VALUES (%s, %s, %s, %s, crypt(%s, gen_salt('bf')), 'OW', %s)",
            (f"U-{secrets.token_hex(4)}", tenant_id, args.admin_name, args.admin_email.lower(),
             password, args.admin_phone),
        )
    print(f"Added company {args.company!r} as {tenant_id}")
    print(f"Owner login: {args.admin_email.lower()} / {password}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up the RIA PostgreSQL database")
    parser.add_argument("--company", help="company (tenant) name RIA calls on behalf of")
    parser.add_argument("--gstin", default="", help="the company's GSTIN (editable later in Settings)")
    parser.add_argument("--caller-id", default="RIA")
    parser.add_argument("--admin-name", default="Owner")
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-password", help="generated and printed if left out")
    parser.add_argument("--admin-phone", default="")
    parser.add_argument("--role", default="OW", choices=("OW", "CM", "CE", "AC", "PA", "TA"),
                        help="for another user of an existing company (a new company's first user is OW)")
    args = parser.parse_args()

    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        sys.exit("DATABASE_URL is missing from backend/.env (see sample.env)")
    with psycopg.connect(url, autocommit=True) as conn:
        apply_sql_files(conn)
        if args.company:
            if not args.admin_email:
                sys.exit("--admin-email is needed with --company")
            add_tenant(conn, args)


if __name__ == "__main__":
    main()
