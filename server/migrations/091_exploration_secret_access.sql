-- Exploration-only access while quest progression is unavailable. This grants
-- native artifact authority, not quest completion, XP, loot, or combat effects.
INSERT INTO settings(name,value) VALUES (
    'exploration_secret_access_policy',
    '{"version":1,"unlock_all":true}'::jsonb
) ON CONFLICT(name) DO NOTHING;
