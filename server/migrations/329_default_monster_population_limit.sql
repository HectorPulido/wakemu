-- Bound new installations using the recognized legacy default. Preserve
-- customized limits, the group budget and all reproduction probabilities.
UPDATE settings
SET value=jsonb_set(value,'{max_zone_members}','1500'::jsonb)
WHERE name='monster_reproduction' AND value->'max_zone_members'='5000'::jsonb;
