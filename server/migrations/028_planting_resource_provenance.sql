-- The world resource keeps its planting provenance after it becomes a monster.
-- Generated identity cannot diverge from the immutable planting receipt payload.
ALTER TABLE planting_receipts ADD COLUMN resource_uid bigint
    GENERATED ALWAYS AS ((resource->>'resource_uid')::bigint) STORED;
ALTER TABLE planting_receipts ADD CONSTRAINT planting_receipt_resource_identity
    CHECK ((success AND resource_uid IS NOT NULL AND resource_uid > 0)
        OR (NOT success AND resource_uid IS NULL));
CREATE UNIQUE INDEX planting_receipts_resource_uid ON planting_receipts(resource_uid)
    WHERE resource_uid IS NOT NULL;
