-- ============================================================================
-- 003_system_state.sql: Background Daemons & Cluster State
--
-- Enables decoupled background workers (like the standalone dialer daemon)
-- to report heartbeats and shared state across multiple API server workers.
-- ============================================================================

CREATE TABLE IF NOT EXISTS system_state (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_state_updated ON system_state(updated_at);
