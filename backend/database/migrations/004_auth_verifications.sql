-- ============================================================================
-- 004_auth_verifications.sql: Email Verification & Password Reset OTPs
--
-- Enables secure, time-limited OTP tokens for self-service sign-up and
-- password resets with attempt limiting and encrypted/hashed storage.
-- ============================================================================

CREATE TABLE IF NOT EXISTS auth_verifications (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    purpose VARCHAR(50) NOT NULL, -- 'signup' or 'password_reset'
    code_hash VARCHAR(128) NOT NULL,
    payload JSONB, -- stores pending sign-up details (company, name, phone, etc.)
    expires_at TIMESTAMPTZ NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_auth_verifications_email_purpose 
    ON auth_verifications(lower(email), purpose);
