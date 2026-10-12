-- Apply to newly created fights; preserve existing configured values.
INSERT INTO settings(name, value)
VALUES ('combat_arena_cell_budget', '1500'::jsonb)
ON CONFLICT (name) DO NOTHING;
