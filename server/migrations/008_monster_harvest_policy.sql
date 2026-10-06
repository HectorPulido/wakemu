-- Explicit local policy, not an asserted official harvest rate.
INSERT INTO settings(name,value) VALUES
    ('monster_harvest','{"quantity":1,"cooldown_seconds":60}'::jsonb);
