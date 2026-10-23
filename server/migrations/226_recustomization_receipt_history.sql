-- A reusable source stack can fund multiple completed dressing-room visits.
-- Keep each completion and only deduplicate the currently pending request.
ALTER TABLE character_recustomization_receipts
    DROP CONSTRAINT character_recustomization_receipts_pkey,
    ADD COLUMN receipt_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY;

CREATE UNIQUE INDEX character_recustomization_pending_source
    ON character_recustomization_receipts(account_id,source_uid)
    WHERE completed_at IS NULL;
