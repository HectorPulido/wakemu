-- Preserve native sidekick eWO raw current and per-source inverse receipts.
ALTER TABLE account_companions ADD COLUMN equipment_hp_projection jsonb;
ALTER TABLE account_companions ADD CONSTRAINT companion_hp_projection_object
    CHECK (equipment_hp_projection IS NULL OR jsonb_typeof(equipment_hp_projection) = 'object');
