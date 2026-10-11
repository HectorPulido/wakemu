-- Keep the existing realm label until an operator chooses a custom name.
INSERT INTO settings(name,value) VALUES ('server_name','"Rubilax"'::jsonb)
ON CONFLICT (name) DO NOTHING;
