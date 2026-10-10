-- Keep consumed rows as settlement receipts; never recreate a harvested corpse.
ALTER TABLE monster_corpses ADD COLUMN consumed_at timestamptz;
ALTER TABLE monster_corpses ADD COLUMN harvest_token text UNIQUE;
ALTER TABLE monster_corpses ADD COLUMN harvested_by bigint REFERENCES characters(id);
ALTER TABLE monster_corpses ADD CONSTRAINT monster_corpse_consumption_complete CHECK (
 (consumed_at IS NULL AND harvest_token IS NULL AND harvested_by IS NULL)
 OR (consumed_at IS NOT NULL AND harvest_token IS NOT NULL AND harvested_by IS NOT NULL)
);
