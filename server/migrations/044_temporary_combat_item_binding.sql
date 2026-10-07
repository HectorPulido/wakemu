-- Preserve pickup-bound state while successful drops are held in temporary
-- inventory. Existing rows are interpreted through their native template by
-- the service, so this default does not erase historical template binding.
ALTER TABLE temporary_combat_items
    ADD COLUMN bound boolean NOT NULL DEFAULT false;
