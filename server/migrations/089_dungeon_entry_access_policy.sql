-- Entrance-only prerequisite policy. Internal progression remains authoritative.
-- Existing operator configuration is preserved when migrations are reapplied.
INSERT INTO settings(name,value) VALUES (
    'dungeon_entry_access_policy',
    '{"version":1,"bypass_mission_prerequisites":true,"bypass_state_prerequisites":true}'::jsonb
) ON CONFLICT(name) DO NOTHING;
