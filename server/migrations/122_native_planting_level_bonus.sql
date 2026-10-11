-- Native-compatible emulator policy, staged until its client carrier is accepted.
-- The existing open profile remains independent and does not consume this bonus.
INSERT INTO settings(name,value) VALUES (
 'planting_level_bonus',
 '{"version":1,"levels_per_point":2,"maximum_level_bonus":100}'::jsonb
) ON CONFLICT(name) DO NOTHING;
