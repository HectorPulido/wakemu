-- Retain every destination of one atomic harvest, including split stacks.
-- Historical completed operations remain completed; [] never authorizes replay.
ALTER TABLE monster_harvest_receipts
    ADD COLUMN item_grants jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(item_grants)='array');
ALTER TABLE environment_interaction_tickets
    ADD COLUMN item_grants jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(item_grants)='array');
