-- Native bWS tooltip values: unsatisfied -1 HP, partial +1 HP, full +2 HP.
-- Contributions are temporary and follow the current region's satisfaction.
INSERT INTO settings(name,value) VALUES (
    'territory_control_health_policy',
    '{"schema_version":1,"states":{"1915":1,"1916":2,"1917":-1}}'::jsonb
) ON CONFLICT(name) DO NOTHING;
