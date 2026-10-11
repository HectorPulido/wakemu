-- Explicit local balance policy; not an official automatic-build formula.
INSERT INTO settings(name,value) VALUES (
    'dungeon_automatic_modulation_policy',
    '{"version":1,"hp_per_level":10,"mastery_per_level":4,"resistance_divisor":2,"critical_divisor":10,"initiative_per_level":1,"ap_thresholds":[50,125],"mp_thresholds":[80]}'::jsonb
) ON CONFLICT(name) DO NOTHING;
