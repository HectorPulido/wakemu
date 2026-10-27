-- Install shared producer policy without enabling native rift gameplay.
-- Activation is a coordinated release step; existing runs keep frozen policies.
-- These defaults describe Wakemu reconstruction, not recovered server scripts.
UPDATE settings
SET value = value || jsonb_build_object(
    'enabled_types', jsonb_build_array('ULTIMATE_INFINITE_WAVE'),
    'encounter_roles',
        '{"policy":"wakemu.rift.ultimate-encounter-roles.v1","player_team":1,"npc_team":0}'::jsonb,
    'artifacts', (value->'artifacts') ||
        '{"rarity_weights":{"wakfu":1,"shushu":1,"stasis":1,"legendary":0},"legendary_cadence":5,"legendary_anchor":"displayed_wave_multiple","legendary_mode":"whole_choice_group","selection":"weighted_tier_uniform_reference_without_replacement","placement_policy":"uniform_free_native_reachable_cells_without_replacement","reconstruction":{"policy":"wakemu.rift.artifact-producer.v1","rarity_weights":"declared_equal_ordinary_tiers","legendary_anchor":"declared_displayed_wave","placement":"declared_seeded_native_free_cells"}}'::jsonb,
    'compensation', (value->'compensation') ||
        '{"grade_policy":"wakemu.company-compensation-1-to-4-v1","classic_grade_by_company_size":{"1":3,"2":2,"3":1,"4":0,"5":0,"6":0},"ultimate_grade_by_company_size":{"1":4,"2":3,"3":2,"4":1,"5":0,"6":0}}'::jsonb
)
WHERE name = 'rift_native_gameplay_policy'
  AND value->>'policy' = 'wakemu.rift.native-gameplay.v1'
  AND value->'schema_version' = '1'::jsonb
  AND NOT (value ? 'enabled_types');

-- The missing producer uses one authentic native 315 template with its native
-- eVt context override. Area identifiers are never substituted for effect IDs.
-- Original area definitions/effects remain authoritative; no nonexistent 315
-- effect references are manufactured for the 25 legendary area definitions.
-- Original template 147120 has indefinite duration (-1), unlike the temporary
-- 315925 candidate. Its descriptor/timing are consumed without modification.
UPDATE settings SET value=jsonb_set(value,'{artifacts,producer}',
  '{"policy":"wakemu.rift.native-context-area-reference.v1","source_kind":"native_context_area_ref","source_document":"combat-state-definitions.json","template_effect_reference":147120,"native_contract":"faM","level_policy":"owner_effective_level","context_policy":"eVt_mb_false_SQ_area_reference"}'::jsonb)
WHERE name='rift_native_gameplay_policy'
  AND value->>'policy'='wakemu.rift.native-gameplay.v1'
  AND NOT (value->'artifacts' ? 'producer');

-- Original displayed/content levels remain intact. Only minimum entry gates
-- use this shared admission policy; unrelated criteria remain authoritative.
INSERT INTO settings(name, value)
VALUES ('instance_entry_level_policy',
        '{"version":1,"enforce_minimum_level":false}'::jsonb)
ON CONFLICT(name) DO NOTHING;

-- Ultimate equipment uses recovered native monster drop sources. Every other
-- reward parameter is inherited from the existing explicit DEV policy, while
-- classic rifts keep reading that global policy unchanged.
INSERT INTO settings(name,value)
SELECT 'rift_reward_type_overrides', jsonb_build_object(
    'ULTIMATE_INFINITE_WAVE', jsonb_set(base.value,'{pools}',
      (SELECT jsonb_agg(CASE
          WHEN pool->>'name'='equipment' AND pool->>'category'='item'
          THEN pool || '{"source":"native_rift_monsters","references":[]}'::jsonb
          ELSE pool END ORDER BY ordinal)
       FROM jsonb_array_elements(base.value->'pools')
            WITH ORDINALITY AS pools(pool,ordinal))))
FROM settings base WHERE base.name='rift_reward_policy'
ON CONFLICT(name) DO NOTHING;
