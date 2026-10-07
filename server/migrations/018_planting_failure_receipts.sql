-- A failed authoritative roll consumes a seed, never creates a world resource.
ALTER TABLE planting_receipts
    ADD COLUMN success boolean NOT NULL DEFAULT true,
    ALTER COLUMN resource DROP NOT NULL;
ALTER TABLE planting_receipts ADD CONSTRAINT planting_receipt_outcome
    CHECK ((success AND resource IS NOT NULL)
        OR (NOT success AND resource IS NULL AND group_payload IS NULL));
ALTER TABLE planting_receipts ADD COLUMN probability double precision
    CHECK (probability >= 0 AND probability <= 1);
