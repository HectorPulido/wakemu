-- User policy: Rift companies keep their ordinary character statistics.
-- Existing runs retain their frozen admission policy; future runs get no6808.
UPDATE settings
SET value = jsonb_set(
    jsonb_set(value, '{compensation,classic_grade_by_company_size}',
        '{"1":0,"2":0,"3":0,"4":0,"5":0,"6":0}'::jsonb),
    '{compensation,ultimate_grade_by_company_size}',
    '{"1":0,"2":0,"3":0,"4":0,"5":0,"6":0}'::jsonb)
WHERE name = 'rift_native_gameplay_policy'
  AND value->>'policy' = 'wakemu.rift.native-gameplay.v1';
