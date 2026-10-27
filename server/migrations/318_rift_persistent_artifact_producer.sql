-- Repair only the known temporary producer from the initial Rift release.
-- The original 147120 descriptor has native duration -1; no effect definition,
-- parameter, probability, criterion or native timing is modified here.
-- Exact producer comparison preserves custom operator policies and replay safety.
UPDATE settings SET value=jsonb_set(value,'{artifacts,producer}',
  '{"policy":"wakemu.rift.native-context-area-reference.v1","source_kind":"native_context_area_ref","source_document":"combat-state-definitions.json","template_effect_reference":147120,"native_contract":"faM","level_policy":"owner_effective_level","context_policy":"eVt_mb_false_SQ_area_reference"}'::jsonb)
WHERE name='rift_native_gameplay_policy'
  AND value->>'policy'='wakemu.rift.native-gameplay.v1'
  AND value->'schema_version'='1'::jsonb
  AND value#>'{artifacts,producer}' IN (
    '{"policy":"wakemu.rift.native-context-area-reference.v1","source_kind":"native_context_area_ref","template_effect_reference":315925,"native_contract":"faM","level_policy":"owner_effective_level","context_policy":"eVt_mb_false_SQ_area_reference"}'::jsonb,
    '{"policy":"wakemu.rift.native-context-area-reference.v1","source_kind":"native_context_area_ref","source_document":"weapon-combat-effects.json","template_effect_reference":315925,"native_contract":"faM","level_policy":"owner_effective_level","context_policy":"eVt_mb_false_SQ_area_reference"}'::jsonb
  );
