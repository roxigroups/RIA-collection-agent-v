-- ============================================================================
-- RIA agent additions to the ria-ui schema (schema.sql is kept as delivered).
--
-- schema.sql records finished calls (`calls`) and retries (`call_reschedule_queue`)
-- but has no place for the dials themselves. The agent and dialer need one:
-- every dial — a batch's first call, a retry or a callback — is a row in
-- `outbound_calls`, which the dialer works through and the agent fills in.
-- When it ends, it becomes a `calls` record (plus PTP, ticket or retry rows).
-- ============================================================================

CREATE TYPE outbound_status_enum AS ENUM ('queued', 'dialing', 'live', 'done', 'cancelled');

CREATE TABLE IF NOT EXISTS outbound_calls (
    -- Sent to the agent in the SIP participant metadata; the agent loads the call by it
    id VARCHAR(50) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    batch_id VARCHAR(50) REFERENCES call_batches(id) ON DELETE SET NULL,
    retailer_id VARCHAR(50) NOT NULL REFERENCES retailers(id) ON DELETE CASCADE,
    invoice_id UUID REFERENCES invoices(id) ON DELETE SET NULL,
    -- Set when the dial came from the retry/callback queue
    queue_id VARCHAR(50) REFERENCES call_reschedule_queue(id) ON DELETE SET NULL,
    -- What RIA says on the call, as it was when the call was queued
    customer_name VARCHAR(255) NOT NULL,
    business_name VARCHAR(255),
    phone VARCHAR(30) NOT NULL,
    language VARCHAR(10) NOT NULL DEFAULT '',  -- te / hi / en ... ('' = the tenant's default)
    invoice_number VARCHAR(100) NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    due_date DATE NOT NULL,
    attempt INT NOT NULL DEFAULT 1,
    status outbound_status_enum NOT NULL DEFAULT 'queued',
    scheduled_for TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Filled in by the agent (or the dialer for unanswered calls)
    outcome VARCHAR(40),
    promised_date DATE,
    promised_amount NUMERIC(14, 2),
    notes TEXT,
    -- calls.id once the finished call has been recorded
    call_record_id VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    answered_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ
);

-- The dialer's "what is due now" lookup
CREATE INDEX IF NOT EXISTS idx_outbound_due ON outbound_calls (scheduled_for) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS idx_outbound_status ON outbound_calls (status);
CREATE INDEX IF NOT EXISTS idx_outbound_phone ON outbound_calls (phone, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outbound_batch ON outbound_calls (batch_id);
CREATE INDEX IF NOT EXISTS idx_outbound_tenant_created ON outbound_calls (tenant_id, created_at DESC);

-- "Don't call me": the customer is never dialed again (RBI fair-practice code)
ALTER TABLE retailers ADD COLUMN IF NOT EXISTS do_not_call BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE retailers ADD COLUMN IF NOT EXISTS do_not_call_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_retailers_tenant_phone ON retailers (tenant_id, phone);

-- What the call was about and how it ended, in RIA's own terms
ALTER TABLE calls ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(50);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS outbound_call_id VARCHAR(50);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS invoice_number VARCHAR(100);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS outcome VARCHAR(40);
ALTER TABLE calls ADD COLUMN IF NOT EXISTS notes TEXT;
CREATE INDEX IF NOT EXISTS idx_calls_tenant_created ON calls (tenant_id, created_at DESC);

-- Monthly partitions from 2026-06 on (schema.sql stops at 2026-05). Rows outside
-- them land in calls_default, which must stay empty for a month's range before
-- that month's partition can be added, so they are created well ahead.
DO $$
DECLARE
    month DATE := DATE '2026-06-01';
BEGIN
    WHILE month < DATE '2028-01-01' LOOP
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF calls FOR VALUES FROM (%L) TO (%L)',
            'calls_' || to_char(month, 'YYYY_MM'),
            -- UTC month boundaries, like schema.sql's partitions
            to_char(month, 'YYYY-MM-DD') || ' 00:00:00+00',
            to_char(month + INTERVAL '1 month', 'YYYY-MM-DD') || ' 00:00:00+00'
        );
        month := month + INTERVAL '1 month';
    END LOOP;
END $$;
