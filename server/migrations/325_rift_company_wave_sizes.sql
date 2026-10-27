-- Freeze the user-requested wave population from each new admitted company.
-- Both Rift types use the same counts; existing runs retain their own policy.
UPDATE settings
SET value = value || '{"wave_size_by_company_size":{"1":4,"2":5,"3":5,"4":6,"5":7,"6":8},"elite_wave_interval":5,"selection":"shuffled_species_cycles"}'::jsonb
WHERE name = 'rift_policy'
  AND value->>'policy_kind' = 'local_dev_not_official';
