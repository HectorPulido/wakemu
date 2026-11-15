-- Public exploration cells permit overlapping characters. Each player's
-- return receipt remains owner-scoped; only private staging destinations
-- require a unique reservation across concurrent lessons.
ALTER TABLE rii_training_transits
    DROP CONSTRAINT IF EXISTS
        rii_training_transits_source_map_source_instance_source_x_s_key;
