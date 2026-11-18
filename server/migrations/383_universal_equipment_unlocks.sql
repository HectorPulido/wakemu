-- Explicit server-wide entitlement policy requested by Hector. Earned levels
-- and experience remain unchanged. The application applies canonical quest
-- progress through achievement storage, without reward outbox entries.
INSERT INTO settings(name,value)
VALUES('universal_equipment_unlocks',
       '{"version":1,"enabled":true,"minimum_company_rank":12,"completed_achievement_ids":[1509]}'::jsonb)
ON CONFLICT(name) DO NOTHING;
