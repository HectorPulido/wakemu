INSERT INTO settings(name, value) VALUES ('pet_feeding_daily_limit_enabled', 'true'::jsonb) ON CONFLICT(name) DO NOTHING;
