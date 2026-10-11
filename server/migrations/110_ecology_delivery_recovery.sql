-- Upgrade already-deployed ecology envelopes without rewriting migration history.
ALTER TABLE ecology_service_proposals
    ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP;
CREATE INDEX ecology_proposals_completed ON ecology_service_proposals(delivered_at DESC,id)
    WHERE delivered_at IS NOT NULL;
