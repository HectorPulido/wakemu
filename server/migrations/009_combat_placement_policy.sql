-- Local combat phase policy; the published timer and server deadline agree.
INSERT INTO settings(name,value) VALUES
    ('combat_placement_duration_ms','60000'::jsonb);
