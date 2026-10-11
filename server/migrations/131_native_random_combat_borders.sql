-- Select only executable, original null-owner native border prototypes.
INSERT INTO settings(name,value)
VALUES ('fight_border_policy','{"version":1,"pool":[46,48]}'::jsonb)
ON CONFLICT(name) DO NOTHING;
