-- Preserve deployed migration 106; apply the native compartment limit additively.
ALTER TABLE guild_chests DROP CONSTRAINT guild_chests_capacity_check;
ALTER TABLE guild_chests ADD CONSTRAINT guild_chests_capacity_check
    CHECK (capacity = 40);
