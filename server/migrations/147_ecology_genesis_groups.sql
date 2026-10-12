-- Preserve reproduction timing/probabilities while raising public map budgets.
UPDATE settings SET value=jsonb_set(jsonb_set(value,'{max_zone_members}','500'::jsonb),'{max_zone_groups}','100'::jsonb)
 WHERE name='monster_reproduction';
INSERT INTO settings(name,value) VALUES
 ('monster_genesis','{"groups_per_region":10,"min_members":2,"max_members":5}'::jsonb);
