-- ============================================================================
-- RIA (Roxy Intelligent AI) Telecalling Agent — Production Database Schema
-- Target Engine: PostgreSQL 15+ / 16 (Google Cloud SQL & Local pgAdmin)
-- Optimization: Sub-millisecond indexed queries, JSONB transcripts,
--               Monthly Table Partitioning, Lock-free Worker Queue.
-- ============================================================================

-- Enable essential extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ----------------------------------------------------------------------------
-- 1. CUSTOM ENUMS & TYPES
-- ----------------------------------------------------------------------------
CREATE TYPE user_role_enum AS ENUM ('OW', 'CM', 'CE', 'AC', 'PA', 'TA');
CREATE TYPE user_status_enum AS ENUM ('Active', 'Inactive', 'Suspended');
CREATE TYPE autonomy_level_enum AS ENUM ('L0', 'L1', 'L2');
CREATE TYPE batch_status_enum AS ENUM ('Scheduled', 'In Progress', 'Completed', 'Failed');
CREATE TYPE reschedule_type_enum AS ENUM ('customer_requested', 'no_lift_retry', 'busy_retry');
CREATE TYPE reschedule_priority_enum AS ENUM ('High', 'Medium', 'Normal', 'Low');
CREATE TYPE reschedule_status_enum AS ENUM ('Queued', 'Dialing', 'Completed', 'Exhausted', 'Cancelled');
CREATE TYPE ptp_status_enum AS ENUM ('due', 'upcoming', 'kept', 'broken');
CREATE TYPE ticket_severity_enum AS ENUM ('High', 'Medium', 'Low');
CREATE TYPE ticket_status_enum AS ENUM ('Open', 'In Progress', 'Resolved', 'Closed');
CREATE TYPE invoice_status_enum AS ENUM ('unpaid', 'partially_paid', 'paid', 'disputed');

-- ----------------------------------------------------------------------------
-- 2. AUTOMATIC UPDATED_AT TRIGGER FUNCTION
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ----------------------------------------------------------------------------
-- 3. TENANTS (Distributor / Organization Configuration)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    gstin VARCHAR(20) UNIQUE NOT NULL,
    caller_id VARCHAR(50) DEFAULT 'ROXY-HYD',
    config JSONB NOT NULL DEFAULT '{
        "provider": "Smallest.ai / OpenAI Voice",
        "voice": {
            "voice": "Ananya (Warm South Indian Professional)",
            "speed": 1.02,
            "pitch": 0.0,
            "punct": true,
            "noise": true,
            "lang": "Telugu"
        },
        "rules": {
            "cap": 3,
            "starthour": "09:00",
            "endhour": "19:30",
            "cooldown_minutes": 5,
            "ptpwindow_days": 7,
            "escalate_broken_threshold": 2,
            "blockdispute": true,
            "blockholiday": true
        },
        "general": {
            "audiodays": 90,
            "auditdays": 365,
            "webhook": "https://api.roxyindustries.in/ria/webhook",
            "escalateemail": "credit@roxyindustries.in",
            "escalatesms": "+919849010002"
        }
    }'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_tenants_updated_at
BEFORE UPDATE ON tenants
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 4. USERS & ACCESS CONTROL (OW, CM, CE, AC, PA, TA)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(50) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role_enum NOT NULL DEFAULT 'CE',
    phone VARCHAR(30),
    status user_status_enum NOT NULL DEFAULT 'Active',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_tenant_role ON users(tenant_id, role);
CREATE INDEX idx_users_email ON users(email);

-- ----------------------------------------------------------------------------
-- 5. RETAILERS / CUSTOMER 360 MASTER
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS retailers (
    id VARCHAR(50) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    owner_name VARCHAR(255),
    business_name VARCHAR(255),
    phone VARCHAR(30) NOT NULL,
    city VARCHAR(100) DEFAULT 'Hyderabad',
    preferred_lang VARCHAR(50) DEFAULT 'Telugu',
    aging_bucket VARCHAR(30) DEFAULT '1-30d',
    total_outstanding NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    overdue_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    credit_limit NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    credit_period VARCHAR(50) DEFAULT '30 Days',
    last_call_at TIMESTAMPTZ,
    last_ptp_date DATE,
    last_disposition VARCHAR(100),
    sentiment_score INT DEFAULT 80 CHECK (sentiment_score BETWEEN 0 AND 100),
    autonomy_level autonomy_level_enum DEFAULT 'L2',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_tenant_retailer_code UNIQUE(tenant_id, code)
);

CREATE INDEX idx_retailers_phone ON retailers(phone);
CREATE INDEX idx_retailers_bucket ON retailers(aging_bucket);
CREATE INDEX idx_retailers_overdue ON retailers(overdue_amount DESC);
CREATE INDEX idx_retailers_tenant ON retailers(tenant_id);

CREATE TRIGGER trg_retailers_updated_at
BEFORE UPDATE ON retailers
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 6. INVOICES
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    retailer_id VARCHAR(50) NOT NULL REFERENCES retailers(id) ON DELETE CASCADE,
    invoice_number VARCHAR(100) NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    due_amount NUMERIC(14, 2) NOT NULL,
    due_date DATE NOT NULL,
    status invoice_status_enum NOT NULL DEFAULT 'unpaid',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_retailer_invoice UNIQUE(retailer_id, invoice_number)
);

CREATE INDEX idx_invoices_retailer ON invoices(retailer_id);
CREATE INDEX idx_invoices_due_date ON invoices(due_date);
CREATE INDEX idx_invoices_status ON invoices(status);

-- ----------------------------------------------------------------------------
-- 7. CAMPAIGN BATCHES (Imported CSV Runs)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS call_batches (
    id VARCHAR(50) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    imported_by_user_id VARCHAR(50) REFERENCES users(id) ON DELETE SET NULL,
    imported_by_name VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    total_calls INT NOT NULL DEFAULT 0,
    completed_calls INT NOT NULL DEFAULT 0,
    connected_calls INT NOT NULL DEFAULT 0,
    ptp_count INT NOT NULL DEFAULT 0,
    ptp_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    dispute_count INT NOT NULL DEFAULT 0,
    no_lift_count INT NOT NULL DEFAULT 0,
    status batch_status_enum NOT NULL DEFAULT 'Scheduled',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_batches_tenant_created ON call_batches(tenant_id, created_at DESC);
CREATE INDEX idx_batches_status ON call_batches(status);

-- ----------------------------------------------------------------------------
-- 8. CALLS MASTER (Partitioned by Month for Long-Term Scale)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calls (
    id VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    batch_id VARCHAR(50) REFERENCES call_batches(id) ON DELETE SET NULL,
    retailer_id VARCHAR(50) NOT NULL REFERENCES retailers(id) ON DELETE CASCADE,
    customer_name VARCHAR(255) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    language VARCHAR(50) NOT NULL DEFAULT 'Telugu',
    duration_seconds INT NOT NULL DEFAULT 0,
    duration_display VARCHAR(30) NOT NULL DEFAULT '0m 0s',
    disposition VARCHAR(150) NOT NULL,
    ptp_committed_date DATE,
    ptp_amount NUMERIC(14, 2),
    sentiment_score INT DEFAULT 80 CHECK (sentiment_score BETWEEN 0 AND 100),
    autonomy_level autonomy_level_enum NOT NULL DEFAULT 'L2',
    audio_recording_url VARCHAR(500),
    turns JSONB NOT NULL DEFAULT '[]'::jsonb,
    ai_summary TEXT,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Partitions for 2026 (Monthly)
CREATE TABLE IF NOT EXISTS calls_2026_03 PARTITION OF calls
    FOR VALUES FROM ('2026-03-01 00:00:00+00') TO ('2026-04-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS calls_2026_04 PARTITION OF calls
    FOR VALUES FROM ('2026-04-01 00:00:00+00') TO ('2026-05-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS calls_2026_05 PARTITION OF calls
    FOR VALUES FROM ('2026-05-01 00:00:00+00') TO ('2026-06-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS calls_default PARTITION OF calls DEFAULT;

-- Indices on Partitioned Calls Table
CREATE INDEX idx_calls_retailer ON calls(retailer_id, created_at DESC);
CREATE INDEX idx_calls_batch ON calls(batch_id);
CREATE INDEX idx_calls_phone ON calls(phone);
CREATE INDEX idx_calls_disposition ON calls(disposition);
CREATE INDEX idx_calls_turns_gin ON calls USING GIN (turns);

-- ----------------------------------------------------------------------------
-- 9. AUTONOMOUS RESCHEDULE & CALLBACK QUEUE (Fast 5-Min Retries & User Slots)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS call_reschedule_queue (
    id VARCHAR(50) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    retailer_id VARCHAR(50) NOT NULL REFERENCES retailers(id) ON DELETE CASCADE,
    batch_id VARCHAR(50) REFERENCES call_batches(id) ON DELETE SET NULL,
    source_call_id VARCHAR(50),
    customer_name VARCHAR(255) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    outstanding_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    type reschedule_type_enum NOT NULL DEFAULT 'no_lift_retry',
    priority reschedule_priority_enum NOT NULL DEFAULT 'High',
    scheduled_for TIMESTAMPTZ NOT NULL,
    attempt_number INT NOT NULL DEFAULT 1,
    max_attempts INT NOT NULL DEFAULT 3,
    ai_note TEXT,
    last_outcome VARCHAR(150),
    status reschedule_status_enum NOT NULL DEFAULT 'Queued',
    dialed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Ultra-fast partial index for the background autonomous dialer daemon
CREATE INDEX idx_queue_pending_due ON call_reschedule_queue (scheduled_for ASC)
WHERE status = 'Queued';

CREATE INDEX idx_queue_retailer ON call_reschedule_queue (retailer_id);
CREATE INDEX idx_queue_status ON call_reschedule_queue (status);

CREATE TRIGGER trg_queue_updated_at
BEFORE UPDATE ON call_reschedule_queue
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 10. PROMISES TO PAY (PTP) PIPELINE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ptp_commitments (
    id VARCHAR(50) PRIMARY KEY,
    retailer_id VARCHAR(50) NOT NULL REFERENCES retailers(id) ON DELETE CASCADE,
    source_call_id VARCHAR(50),
    customer_name VARCHAR(255) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    amount NUMERIC(14, 2) NOT NULL,
    due_date DATE NOT NULL,
    status ptp_status_enum NOT NULL DEFAULT 'upcoming',
    autonomy_level autonomy_level_enum DEFAULT 'L2',
    payment_link_sent BOOLEAN DEFAULT FALSE,
    payment_link_url VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ptp_due_date ON ptp_commitments(due_date ASC);
CREATE INDEX idx_ptp_status ON ptp_commitments(status);
CREATE INDEX idx_ptp_retailer ON ptp_commitments(retailer_id);

CREATE TRIGGER trg_ptp_updated_at
BEFORE UPDATE ON ptp_commitments
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 11. TICKETS / ESCALATIONS & DISPUTES
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tickets (
    id VARCHAR(50) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    retailer_id VARCHAR(50) REFERENCES retailers(id) ON DELETE SET NULL,
    source_call_id VARCHAR(50),
    customer_name VARCHAR(255) NOT NULL,
    category VARCHAR(150) NOT NULL,
    severity ticket_severity_enum NOT NULL DEFAULT 'Medium',
    assigned_to_user_id VARCHAR(50) REFERENCES users(id) ON DELETE SET NULL,
    assigned_to_name VARCHAR(255) DEFAULT 'Unassigned',
    status ticket_status_enum NOT NULL DEFAULT 'Open',
    resolution_note TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tickets_tenant_status ON tickets(tenant_id, status);
CREATE INDEX idx_tickets_assigned ON tickets(assigned_to_user_id);
CREATE INDEX idx_tickets_created ON tickets(created_at DESC);

CREATE TRIGGER trg_tickets_updated_at
BEFORE UPDATE ON tickets
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- 12. CAMPAIGN & CUSTOMER CARE CONTACTS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campaign_contacts (
    id VARCHAR(50) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    retailer_id VARCHAR(50) REFERENCES retailers(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    credit_period VARCHAR(50) DEFAULT '30 Days',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_contacts_tenant_phone ON campaign_contacts(tenant_id, phone);

CREATE TABLE IF NOT EXISTS customer_care_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(50) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    role_title VARCHAR(150) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    available_hours VARCHAR(150) NOT NULL,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 13. AUDIT LOG (Immutable Compliance & Action Trail)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(50),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(100) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_tenant_date ON audit_logs(tenant_id, created_at DESC);

-- ----------------------------------------------------------------------------
-- 14. PERFORMANCE VIEWS FOR DASHBOARD & RECOVERY ANALYTICS
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_dashboard_kpis AS
SELECT
    t.id AS tenant_id,
    COUNT(DISTINCT r.id) AS total_retailers,
    COALESCE(SUM(r.total_outstanding), 0) AS total_outstanding,
    COALESCE(SUM(r.overdue_amount), 0) AS total_overdue,
    (SELECT COUNT(*) FROM calls c WHERE c.created_at >= CURRENT_DATE) AS calls_placed_today,
    (SELECT COUNT(*) FROM calls c WHERE c.created_at >= CURRENT_DATE AND c.duration_seconds > 0) AS calls_connected_today,
    (SELECT COALESCE(SUM(p.amount), 0) FROM ptp_commitments p WHERE p.created_at >= CURRENT_DATE) AS ptp_recovered_today,
    (SELECT COUNT(*) FROM call_reschedule_queue q WHERE q.status = 'Queued') AS pending_reschedules_count,
    (SELECT COUNT(*) FROM tickets tk WHERE tk.status = 'Open') AS open_tickets_count
FROM tenants t
LEFT JOIN retailers r ON r.tenant_id = t.id
GROUP BY t.id;

-- ----------------------------------------------------------------------------
-- 15. STORED PROCEDURE: LOCK-FREE WORKER QUEUE FETCH
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fetch_next_reschedule_batch(
    p_tenant_id VARCHAR,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    queue_id VARCHAR,
    ret_id VARCHAR,
    cust_name VARCHAR,
    cust_phone VARCHAR,
    due_amt NUMERIC,
    req_type reschedule_type_enum,
    note TEXT,
    attempt INT
) AS $$
BEGIN
    RETURN QUERY
    WITH due_items AS (
        SELECT q.id
        FROM call_reschedule_queue q
        WHERE q.tenant_id = p_tenant_id
          AND q.status = 'Queued'
          AND q.scheduled_for <= CURRENT_TIMESTAMP
        ORDER BY q.priority = 'High' DESC, q.scheduled_for ASC
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    )
    UPDATE call_reschedule_queue target
    SET status = 'Dialing',
        dialed_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    FROM due_items
    WHERE target.id = due_items.id
    RETURNING
        target.id,
        target.retailer_id,
        target.customer_name,
        target.phone,
        target.outstanding_amount,
        target.type,
        target.ai_note,
        target.attempt_number;
END;
$$ LANGUAGE plpgsql;
