-- Apply the recovered shared Current Wave graph to newly admitted classic
-- Rifts as well as Ultimate Rifts. Native arithmetic/criteria are unchanged.
-- Existing runs retain their frozen policy and constructor affiliations.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM settings WHERE name='rift_native_gameplay_policy'
      AND value->>'policy'='wakemu.rift.native-gameplay.v1'
      AND value->>'authority'='native_consumers_with_reconstructed_producers'
      AND value->>'wave_state'='6807'
      AND value->>'wave_grade'='current_wave_number_clamped_to_native_state_maximum'
      AND value->'encounter_roles'=
        '{"policy":"wakemu.rift.ultimate-encounter-roles.v1","player_team":1,"npc_team":0}'::jsonb
      AND value->'enabled_types' IN (
        '["ULTIMATE_INFINITE_WAVE"]'::jsonb,
        '["INFINITE_WAVE","ULTIMATE_INFINITE_WAVE"]'::jsonb
      )
  ) THEN
    RAISE EXCEPTION 'Missing reviewed native Rift wave and constructor policy';
  END IF;
END $$;

UPDATE settings SET value=jsonb_set(
  value, '{enabled_types}', '["INFINITE_WAVE","ULTIMATE_INFINITE_WAVE"]'::jsonb
)
WHERE name='rift_native_gameplay_policy';
