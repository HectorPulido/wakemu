-- Expand default map/instance population budgets tenfold. Regional chief
-- wishes remain equilibrium indicators, never automatic population caps.
-- Preserve operator-customized budgets independently and all other settings.
UPDATE settings
SET value=jsonb_set(value,'{max_zone_members}','5000'::jsonb)
WHERE name='monster_reproduction' AND value->'max_zone_members'='500'::jsonb;

UPDATE settings
SET value=jsonb_set(value,'{max_zone_groups}','1000'::jsonb)
WHERE name='monster_reproduction' AND value->'max_zone_groups'='100'::jsonb;
