-- Migration 005: Dynamic Telephony Numbers Pool & Caller ID Tracking

CREATE TABLE IF NOT EXISTS telephony_numbers (
    id VARCHAR(50) PRIMARY KEY,
    phone_number VARCHAR(30) UNIQUE NOT NULL,
    label VARCHAR(100) DEFAULT '',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    daily_limit INT NOT NULL DEFAULT 250,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telephony_status ON telephony_numbers (status);

-- Seed initial 5 numbers if not already present
INSERT INTO telephony_numbers (id, phone_number, label, status, daily_limit)
VALUES 
    ('num_8064269997', '+918064269997', 'Bangalore Line 1', 'active', 250),
    ('num_8064269994', '+918064269994', 'Bangalore Line 2', 'active', 250),
    ('num_8064269993', '+918064269993', 'Bangalore Line 3', 'active', 250),
    ('num_8064269991', '+918064269991', 'Bangalore Line 4', 'active', 250),
    ('num_8065382786', '+918065382786', 'Bangalore Line 5', 'active', 250)
ON CONFLICT (phone_number) DO NOTHING;

-- Add caller_id column to outbound_calls if missing
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS caller_id VARCHAR(30);
CREATE INDEX IF NOT EXISTS idx_outbound_caller_id ON outbound_calls (caller_id, created_at);

