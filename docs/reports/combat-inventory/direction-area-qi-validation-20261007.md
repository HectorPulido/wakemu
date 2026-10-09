# Direction and typed area-coordinate validation

The native `GetCharacterDirection` probe and exact client findings are recorded in [native-character-direction-alignment-20261007.md](native-character-direction-alignment-20261007.md). A final review of `eII` showed that explicit cell targets can fall back through `fbX.ay` to `fcb.dC` and the first `eGj` in `QI.U`. This checkout has no producer for that exact first-occupant lookup, so direction on a target cell remains unknown. A fighter's mere presence in the broader actor roster is not enough to infer that it is the native QI-selected fighter.

The adapter now marks explicit `aBn` cells separately from proven null targets. `GetCharacterDirection("target")` raises `UnknownCondition` for an explicit cell until QI authority is available, including when a fighter is at that coordinate. A target with no cell returns `-1`. A registered Qq/faV area PV is validated as an actual area but is not converted into an eHg coordinate; its direction getter returns `-1`, while alignment and diagonal return false through native null behavior.

## Final focused validation

Command:

```sh
PYTHONPATH=server:server/tests WAKFU_NATIVE_GRANTED_CAST=1 WAKFU_NATIVE_AREA_CALLBACKS=1 \
  /tmp/wakemu-combat-review-venv/bin/python3 -m unittest \
  test_combat_runtime_adapter \
  test_combat_character_direction \
  test_combat_condition_diagonal \
  test_combat_conditions \
  test_combat_qi_snapshot \
  test_combat_target_life_selectors \
  test_combat_area_authority \
  test_combat_gate_area_lifecycle \
  test_combat_area_predicate_integration \
  test_combat_effect_area_events \
  test_combat_closest_specific_area
```

Result: **98 tests passed** in one process. No service, database or socket was started. The regressions include a real GATE 823 PV whose stored cell equals the caster's cell; direction/alignment/diagonal still follow the native non-eHg null path. They also include an explicit target cell with a fighter at that position and verify that the missing QI lookup stays unknown.

The eleven test modules had identical pre/post SHA-256 manifest digest `25ed77484a248bf727bdb8092970f149f15551c18a827dc40cc9ca06c2e3d9c3`. Six relevant production files were identical pre/post:

| File | SHA-256 |
| --- | --- |
| `combat_conditions.py` | `f829aa534ac5f32cd29a16d12b4cef1a87ce6ad01e8fe2be1813ffd1f15fd039` |
| `combat_runtime_adapter.py` | `ea864089b46850e5ba07bcac9ad78e2adad00f5cd0df158b5872f6e071e67c78` |
| `combat_condition_alignment.py` | `98f7e3a626e49e9785153a92744863aa204d436f4bd8be1181eb7a90237c6e33` |
| `combat_condition_diagonal.py` | `02a66e5a7a1eff7ee7a46ad51de09de8b57800a6f2e67e92c46c1f9d78e54c72` |
| `combat_state_managers.py` | `c7f2588d377280120e6285ebd1b485aeb3cfc55b38a9bda2b998d76994ddfe9b` |
| `combat_effect_area.py` | `0406b4bf48b7f2c360dbd557ef887655e2778521555476753aa453bc68bf94cb` |

The full combat-source manifest differed only because `combat_terminal_metadata.py` changed during the run, from `3bf0bf133bcb4fba53d938aa87b6e609347298487fb4e0e9f0f712b7ba211c1c` to `cb203625aaff906b64ffa2c34eccf3a86d685944b690a168266ba8cf85035641`. It is outside this test's relevant source set. Detailed sorted manifests are preserved in the ignored private review directory `.runtime/combat-review-20261007/` as `direction-qi-final-before.sha256`, `direction-qi-final-after.sha256`, and their corresponding `direction-qi-final-tests-*.sha256` files.

A broader 231-test integration run passed before the final typed-Qq and explicit-cell QI corrections; it is a historical checkpoint and is not presented as validation of those two later changes.
