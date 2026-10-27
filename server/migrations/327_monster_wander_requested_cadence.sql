-- Persist the requested cadence across environments instead of a local SQL edit.
-- Preserve explicitly customized policies outside the previous default profile.
UPDATE settings
SET value = jsonb_set(
    jsonb_set(value, '{interval_seconds}', '1'::jsonb),
    '{max_steps}', '8'::jsonb
)
WHERE name = 'monster_wander'
  AND value = '{"interval_seconds":2,"move_probability":0.6,"min_steps":1,"max_steps":3,"radius":20}'::jsonb;
