-- Enable the three catalogued ultimate rifts for clean installations as well
-- as upgrades. Native gameplay remains explicitly scoped away from classics.
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM settings WHERE name='rift_native_gameplay_policy'
    AND value->>'policy'='wakemu.rift.native-gameplay.v1'
    AND value->'enabled_types'='["ULTIMATE_INFINITE_WAVE"]'::jsonb
  ) THEN
    RAISE EXCEPTION 'Missing reviewed ultimate-only native policy';
  END IF;
END $$;

UPDATE settings SET value=jsonb_set(value,'{ultimate_enabled}','true')
WHERE name='rift_policy';

UPDATE settings SET value=jsonb_set(
  jsonb_set(value,'{enabled}','true'),'{artifacts,enabled}','true')
WHERE name='rift_native_gameplay_policy';
