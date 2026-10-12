-- Keep explicit custom policies; shorten only the original idle-wander defaults.
UPDATE settings
SET value = jsonb_set(
    jsonb_set(value, '{interval_seconds}', '2'::jsonb),
    '{move_probability}', '0.6'::jsonb
)
WHERE name = 'monster_wander'
  AND value->'interval_seconds' = '5'::jsonb
  AND value->'move_probability' = '0.25'::jsonb;
