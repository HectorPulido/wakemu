-- Persist the deadline fixed at completion, so changing policy only affects
-- future harvests and reconnect/native action gates share the same authority.
ALTER TABLE monster_harvest_receipts ADD COLUMN regenerates_until timestamptz;
UPDATE monster_harvest_receipts SET regenerates_until = completed_at +
    make_interval(secs => (SELECT (value->>'cooldown_seconds')::double precision
                           FROM settings WHERE name='monster_harvest'));
ALTER TABLE monster_harvest_receipts ALTER COLUMN regenerates_until SET NOT NULL;
ALTER TABLE monster_harvest_receipts ADD CONSTRAINT valid_harvest_regeneration
    CHECK (regenerates_until > completed_at);
CREATE INDEX monster_harvest_regeneration
    ON monster_harvest_receipts(map_id,instance_id,regenerates_until);
DROP INDEX monster_harvest_cooldown;
CREATE INDEX monster_harvest_cooldown
    ON monster_harvest_receipts(map_id,instance_id,monster_id,action_id,regenerates_until DESC);
