-- Native client configuration key eEL.IS_NEO_SERVER
-- (`server.group.isneo`) defaults to false. Keep the emulator's selected
-- server mode explicit and editable by operators; this is not a client rule
-- evaluator and does not authorize any transport by itself.
INSERT INTO settings(name, value) VALUES (
    'dungeon_server_mode',
    '{"version":1,"is_neo_server":false}'::jsonb
) ON CONFLICT(name) DO NOTHING;
