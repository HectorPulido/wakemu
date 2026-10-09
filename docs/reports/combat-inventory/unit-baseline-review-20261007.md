# Combat unit baseline review — 2026-10-07

The local combat baseline is failing: **1,468 tests, 11 assertion failures, 13 errors, 94 skips**, in **191.124 seconds**. This is an offline/unit baseline, not evidence that the deployed server or the 18 classes work in the graphical client.

## Reproduction

```sh
python3 -m venv /tmp/wakemu-combat-review-venv
/tmp/wakemu-combat-review-venv/bin/pip install -r server/requirements.txt
PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python3 -m unittest discover -s server/tests -p 'test_combat*.py' > /tmp/wakemu-combat-venv-baseline-20261007.log 2>&1
```

The host Python initially failed importing `psycopg`; those incomplete host runs were stopped and excluded. The isolated interpreter has the repository's Redis and psycopg requirements installed. No PostgreSQL test URL was supplied; database integration cases skip rather than exercising persistence. Native Java probe tests also skip when their probe evidence is unavailable. The complete baseline reported 94 skips; no exact per-reason count was collected.

## Failure groups

| Group | Outcomes | Observed evidence |
| --- | --- | --- |
| Cast validation fixtures | 8 errors | `SimpleNamespace` caster lacks `turn_count`, accessed by spell usage validation. These errors do not alone establish a runtime actor defect. |
| Feca glyph delivery | 2 errors | Level 1 and 200: `Missing native delivery owner routing`. |
| Granted spells / summon entry | 2 errors + 1 failure | Missing effect definition during native dispatch; compiled catalog lacks effect `313166`. |
| Self cast validation | 1 error + 1 failure | Missing native casting limit definition; expected range rejection instead sees missing self-cast policy. |
| Sacrier chains and blood healing | 3 failures | Expected innate `9315` absent; Heart of Blood observed `(140, 330)` versus `(60, 250)`; stored-damage healing produced HP `124` versus `48`. |
| Ordinary displacement events | 3 failures | Pull and targetless teleport include extra trailing events; movement listener executed zero times. |
| Ordinary healing delivery | 2 failures | Assertions expect `13497`, actual callback delivery includes `12613`. |
| Diagnostic assertion | 1 failure | Expected `No handler.*949`; actual message is `Native949 requires eZM context authority`. |

These are observed mismatches. Some may reflect stale fixtures or assertions after protocol changes; classification as production defects requires reproduction through the ordinary server authority and current catalogs.

## Failing test names and diagnostics

- `ERROR: test_bare_selector_native_close_branch_and_unknown_states (test_combat_cast.CastValidationTests.test_bare_selector_native_close_branch_and_unknown_states)`
  - `AttributeError: 'types.SimpleNamespace' object has no attribute 'turn_count'`
- `ERROR: test_common_validation_accepts_self_spells_across_classes (test_combat_cast.CastValidationTests.test_common_validation_accepts_self_spells_across_classes)`
  - `AttributeError: 'types.SimpleNamespace' object has no attribute 'turn_count'`
- `ERROR: test_common_validation_keeps_empty_cell_target (test_combat_cast.CastValidationTests.test_common_validation_keeps_empty_cell_target)`
  - `AttributeError: 'types.SimpleNamespace' object has no attribute 'turn_count'`
- `ERROR: test_complete_cast_rejects_omitted_mp_effect (test_combat_cast.CastValidationTests.test_complete_cast_rejects_omitted_mp_effect)`
  - `AttributeError: 'types.SimpleNamespace' object has no attribute 'turn_count'`
- `ERROR: test_conditional_cost_callback_uses_live_state_and_native_modifier_snapshot (test_combat_cast.CastValidationTests.test_conditional_cost_callback_uses_live_state_and_native_modifier_snapshot)`
  - `AttributeError: 'types.SimpleNamespace' object has no attribute 'turn_count'`
- `ERROR: test_own_normal_cast_and_native_profiles (test_combat_cast.CastValidationTests.test_own_normal_cast_and_native_profiles)`
  - `AttributeError: 'types.SimpleNamespace' object has no attribute 'turn_count'`
- `ERROR: test_reject_unknown_branch_los_and_resources (test_combat_cast.CastValidationTests.test_reject_unknown_branch_los_and_resources)`
  - `AttributeError: 'types.SimpleNamespace' object has no attribute 'turn_count'`
- `ERROR: test_simple_spell_ap_modifiers_apply_before_resource_validation (test_combat_cast.CastValidationTests.test_simple_spell_ap_modifiers_apply_before_resource_validation)`
  - `AttributeError: 'types.SimpleNamespace' object has no attribute 'turn_count'`
- `ERROR: test_real_feca_glyph_creation_and_turn_boundary_with_class_initialization (test_combat_effect_area_entry.NativeAreaEntryTests.test_real_feca_glyph_creation_and_turn_boundary_with_class_initialization) (level=1)`
  - `ValueError: Missing native delivery owner routing`
- `ERROR: test_real_feca_glyph_creation_and_turn_boundary_with_class_initialization (test_combat_effect_area_entry.NativeAreaEntryTests.test_real_feca_glyph_creation_and_turn_boundary_with_class_initialization) (level=200)`
  - `ValueError: Missing native delivery owner routing`
- `ERROR: test_native_grant_full_dispatch_cast_wire_and_retirement (test_combat_granted_cast.GrantedCastTests.test_native_grant_full_dispatch_cast_wire_and_retirement)`
  - `wakfu_server.combat_effect_dispatch.UnsupportedEffectExecution: Missing native effect definition`
- `ERROR: test_native_same_xyz_does_not_use_bare_ray_catalog (test_combat_self_cast_los.NativeSelfCastLosTests.test_native_same_xyz_does_not_use_bare_ray_catalog)`
  - `ValueError: Missing native casting limit definition`
- `ERROR: test_native_granted_sphere_common_entry_and_registered_roster (test_combat_summon_entry.NativeSummonEntryTests.test_native_granted_sphere_common_entry_and_registered_roster)`
  - `wakfu_server.combat_effect_dispatch.UnsupportedEffectExecution: Missing native effect definition`
- `FAIL: test_legitimate_berserker_innate_also_hits_on_cast (test_combat_cinetosis_chain.CinetosisChainTests.test_legitimate_berserker_innate_also_hits_on_cast)`
  - `AssertionError: 9315 not found in [4464, 3702, 3231, 9312, 9328, 9314, 9324, 9313]`
- `FAIL: test_failed_effect_identifies_family_target_and_call_chain (test_combat_diagnostics.DiagnosticsTests.test_failed_effect_identifies_family_target_and_call_chain)`
  - `AssertionError: "No handler.*949" does not match "Native949 requires eZM context authority"`
- `FAIL: test_native_pull_phase_order_values_and_actual_position (test_combat_displacement_events.OrdinaryDisplacementEventTests.test_native_pull_phase_order_values_and_actual_position)`
  - `AssertionError: Lists differ: [10, 1, 20, 2, 30, 3, 40, 4, 30, 3] != [10, 1, 20, 2, 30, 3, 40, 4]`
- `FAIL: test_original_movement_listener_activates_and_removal_stops_reaction (test_combat_displacement_events.OrdinaryDisplacementEventTests.test_original_movement_listener_activates_and_removal_stops_reaction)`
  - `AssertionError: 0 not greater than 0`
- `FAIL: test_targetless_teleport_keeps_native_null_target_and_caster_roles (test_combat_displacement_events.OrdinaryDisplacementEventTests.test_targetless_teleport_keeps_native_null_target_and_caster_roles)`
  - `AssertionError: Lists differ: [10, 20, 30, 40, 30, 3] != [10, 20, 30, 40]`
- `FAIL: test_exported_roots_match_class_catalog_and_extras_are_merged (test_combat_granted_cast.GrantedCastTests.test_exported_roots_match_class_catalog_and_extras_are_merged)`
  - `AssertionError: compiled runtime effects do not contain '313166'.`
- `FAIL: test_innate_grant_self_cast_armor_consumption_and_turn_limit (test_combat_heart_blood.NativeHeartBloodTests.test_innate_grant_self_cast_armor_consumption_and_turn_limit)`
  - `AssertionError: Tuples differ: (140, 330) != (60, 250)`
- `FAIL: test_stored_damage_is_created_by_real_blood_cast_then_healed_and_consumed (test_combat_heart_blood.NativeHeartBloodTests.test_stored_damage_is_created_by_real_blood_cast_then_healed_and_consumed)`
  - `AssertionError: 124 != 48`
- `FAIL: test_factory_binds_ordinary_events_without_manual_emitter (test_combat_ordinary_events.OrdinaryHealingEventTests.test_factory_binds_ordinary_events_without_manual_emitter)`
  - `AssertionError: Lists differ: [12613, 12613, 13560] != [12613, 13497, 13560]`
- `FAIL: test_real_healing_executes_listener_and_removes_it_automatically (test_combat_ordinary_events.OrdinaryHealingEventTests.test_real_healing_executes_listener_and_removes_it_automatically)`
  - `AssertionError: Lists differ: [13497, 12613, 12613, 13560] != [13497, 12613, 13497, 13560]`
- `FAIL: test_self_keeps_range_resources_and_free_cell_guards (test_combat_self_cast_los.NativeSelfCastLosTests.test_self_keeps_range_resources_and_free_cell_guards)`
  - `AssertionError: "native range" does not match "Missing native self-cast policy"`

## Coverage limits

The repository contains 258 `test_combat*.py` modules and 1,405 statically declared test methods; unittest executes additional inherited cases and subtests. Many tests exercise production modules with synthetic actors, callbacks, contexts or deliberately restricted effect resolvers. For example, `test_combat_spell_transaction.py` restricts its test resolver to known normal roots; its “native” naming does not imply complete server/client integration.

`server/tools/audit_active_spells.py` does call `server_runtime` and the common cast transaction with exported terrain, legal class resources, native initialization and optional consecutive casts. It remains an offline fixture audit: bare actors, selected monster/scenario, no equipped passive matrix, no real sockets, no graphical client, no certification of a complete class.

`client-tools/diagnostics/check-combat-gui.py` can collect actual requests, server acceptance, delivery and precise client deltas for a legitimate existing fight. Its unit tests validate the verdict logic with synthetic evidence; they do not perform graphical casts.

**Source stability was not verified.** No manifest/hash was collected before and after this baseline, and another agent may have changed shared files during execution. Git status cannot establish stable inputs. Treat this as evidence for the observed run, not an immutable release qualification.

No services were restarted, no database/socket tests were performed, and no deployment was attempted as part of this baseline. The baseline also exposed a test hygiene issue: `test_combat_cinetosis_chain.setUpClass` called an audit with its default historical output path. That test rewrote `cinetosis-fulgor-runtime-audit.json`. The coordinating agent preserved the generated result under `.runtime/combat-review-20261007/cinetosis-unit-baseline-output.json`, restored the historical report, and changed the test to use a temporary output directory. This change isolates future runs; it does not fix combat behavior.

## Environment qualification for granted spells

This baseline did not enable `WAKFU_NATIVE_GRANTED_CAST=1`. The runtime catalog merge for granted effects is gated by that flag. Consequently, the missing `313166` assertion and granted/summon dispatch failures must be qualified against that disabled feature setting before classifying them as absent exports. A targeted rerun with native grant and area callbacks enabled completed: 23 tests in 24.816 seconds, 1 assertion failure, 1 error, no skips. The source manifest was stable for server Python code, tools, the three test modules, and six core protocol catalogs. The original unqualified baseline remains unchanged. Granted-cast tests now pass; missing `313166` in that baseline was a disabled feature merge rather than proof of an absent export. Summon entry now reaches a different blocker: `Summoned-actor lifecycle propagation remains unaudited`. The Sacrier berserker-chain assertion still fails because expected state `9315` is absent in one setup.


Targeted command:

```sh
WAKFU_NATIVE_GRANTED_CAST=1 WAKFU_NATIVE_AREA_CALLBACKS=1 PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_granted_cast test_combat_summon_entry test_combat_cinetosis_chain
```

The actual run used the same unittest modules inside a wrapper that collected the pre/post source SHA-256 manifest and bounded individual failure diagnostics to 8 KB. Detailed evidence is stored privately in `.runtime/combat-review-20261007/targeted-flags-unit-review.json`; it is aggregate unit evidence, not per-spell semantic or client verification.
