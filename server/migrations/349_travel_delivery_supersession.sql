-- Obsolete presentation is distinct from successful native scene delivery.
-- Existing deliveries and item consumption remain historical authority.
ALTER TABLE haven_world_transitions ADD COLUMN superseded_at timestamptz;
ALTER TABLE item_teleport_receipts ADD COLUMN superseded_at timestamptz;
ALTER TABLE haven_world_transitions ADD CONSTRAINT haven_world_delivery_outcome
 CHECK (delivered_at IS NULL OR superseded_at IS NULL);
ALTER TABLE item_teleport_receipts ADD CONSTRAINT item_teleport_delivery_outcome
 CHECK (delivered_at IS NULL OR superseded_at IS NULL);
DROP INDEX haven_world_transition_pending;
CREATE UNIQUE INDEX haven_world_transition_pending ON haven_world_transitions(character_id)
 WHERE delivered_at IS NULL AND superseded_at IS NULL;
DROP INDEX item_teleport_one_pending;
CREATE UNIQUE INDEX item_teleport_one_pending
 ON item_teleport_receipts(account_id,generation,character_id)
 WHERE delivered_at IS NULL AND superseded_at IS NULL;
