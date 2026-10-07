-- Character deletion is a durable tombstone so historical receipts and foreign
-- keys remain valid. Deleted names and account slots can be reused.
ALTER TABLE characters ADD COLUMN deleted_at timestamptz;
ALTER TABLE characters DROP CONSTRAINT characters_name_key_key;
CREATE UNIQUE INDEX characters_live_name_key ON characters(name_key)
    WHERE deleted_at IS NULL;
CREATE INDEX characters_live_account ON characters(account_id,id)
    WHERE deleted_at IS NULL;
