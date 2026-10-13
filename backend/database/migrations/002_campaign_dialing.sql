-- ============================================================================
-- Call Campaign controls
-- An imported batch waits until someone presses "Start calling" on the Call
-- Campaign screen; its calls are then dialed one after another, in the order of
-- the call sheet. "Call now" on one customer dials them next.
-- ============================================================================

-- TRUE while the batch is being called; "Pause" sets it back to FALSE
ALTER TABLE call_batches ADD COLUMN IF NOT EXISTS dialing BOOLEAN NOT NULL DEFAULT FALSE;

-- "Call now" on one customer: dialed next, even if their batch hasn't been started
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS dial_now BOOLEAN NOT NULL DEFAULT FALSE;

-- When the dialer picked the call up, for the "ringing" timer on screen
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS dialed_at TIMESTAMPTZ;

-- The order of the call sheet: calls imported together share one created_at
ALTER TABLE outbound_calls ADD COLUMN IF NOT EXISTS seq BIGSERIAL;

-- Batches imported before this change were dialed straight away: keep any
-- calls they still have queued going
UPDATE call_batches b SET dialing = TRUE
WHERE EXISTS (SELECT 1 FROM outbound_calls o WHERE o.batch_id = b.id AND o.status = 'queued');
