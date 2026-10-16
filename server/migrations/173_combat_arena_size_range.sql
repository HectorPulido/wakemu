-- Normal encounters draw a full square rectangle size; duels keep their policy.
INSERT INTO settings(name, value)
VALUES ('combat_arena_size_range', '{"minimum":7,"maximum":20}'::jsonb)
ON CONFLICT (name) DO NOTHING;
