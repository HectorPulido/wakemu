# Native `IsOnBorderCell` validation — 2026-10-07

`IsOnBorderCell` now reads the captured native QI arena snapshot and delegates the cell predicate to `NativeQISnapshot.P`. The runtime adapter only evaluates a registered fighter with explicit eGj authority and a serialized arena snapshot. A missing snapshot or unresolved explicit-cell fighter lookup remains unknown; a registered non-fighter PV with no ePy state manager follows the proven null-Qf result (`-1`).

`create_placement` stores a plain copy of exactly `x`, `y`, `width`, `height`, and `cell_masks` from the serialized arena after constructing the `Fight`. It rejects partial snapshots. The regression verifies source-list isolation and JSON checkpoint round-trip preservation.

Validation command (offline; no services):

```sh
PYTHONPATH=server:server/tests WAKFU_NATIVE_GRANTED_CAST=1 WAKFU_NATIVE_AREA_CALLBACKS=1 /tmp/wakemu-combat-review-venv/bin/python3 -m unittest \
  test_combat_border_cell test_combat_qi_snapshot test_combat_conditions \
  test_combat_runtime_adapter test_combat_bootstrap \
  test_combat_maximum_amount_source test_combat_maximum_resource \
  test_combat_maximum_reduction test_combat_parameter_maximum \
  test_combat_gate_area_lifecycle test_combat_effect_area_events \
  test_combat_area_captured_activation
```

Result: **100 tests passed** in 38.086 seconds. The process printed the successful unittest summary but retained a worker after completion; only that known test process was interrupted after the final summary. An initial invocation used two nonexistent module names (`test_combat_max_resource`, `test_combat_max_reduction`) and reported import errors; the corrected invocation above is the validated run.

SHA-256 manifests captured immediately before and after the run matched for all directly affected production modules, border/bootstrap/runtime tests, and the concurrent maximum-resource source/test. Key files:

- `combat_bootstrap.py`: `d1971e4e40a44ddf84133e87655a6cad16f03e9fa4c76205eb1f297d083c37bb`
- `combat_conditions.py`: `25e5748ea146f310009ef9d74c8ff4350eeb38674839354c48c68929615b64e4`
- `combat_runtime_adapter.py`: `2d9579831a7b25a396163503856501e637e77bf5722eaeaadbe622c32b81c420`
- `combat_condition_border.py`: `784df8f3e1e177204044ea7a26965e477f59b888e5af772678a5e225754de0c`
- `test_combat_border_cell.py`: `c3e915beda70a36d807bcc5dc11abce23fee72369fee2be9206ed863e4b04a16`
- `test_combat_runtime_adapter.py`: `af7c925902cb653fddeecd0ace2334cbe54256a8513231ced3b5507f9c74f83e`
- `test_combat_bootstrap.py`: `9e47a317306ccfab9dbc2b389d56d5d56ffab0dd21f29993f66dff59f739bdaf`

The explicit-target-cell fallback through native QI.U remains unsupported because this runtime has no producer for that lookup; the adapter rejects that context rather than guessing an actor from coordinates.

## Predicate type correction

The 100-test batch above exercised `IsOnBorderCell` only in numeric-comparison form, so it did **not** validate the native predicate parser contract. Ready/passive validation later exposed the mismatch: eOr is a boolean `eIX` condition, whose internal `a()` result is `0`/`-1` and whose `b()` consumer converts `a() == 0`. The implementation now registers and evaluates it in the boolean predicate path, returning `True` only for native code `0`; numeric comparisons such as `IsOnBorderCell("caster") == 0` are rejected. Direct predicate, negation, boolean composition, malformed signatures, QI snapshot semantics, and runtime-adapter behavior were rechecked offline:

```sh
PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest \
  test_combat_border_cell test_combat_qi_snapshot \
  test_combat_conditions test_combat_runtime_adapter
```

Result: **53 tests passed** in 20.539 seconds. The completed test process retained a worker after printing the unittest summary and was interrupted afterward. The Ready/passive catalog batch must be repeated to verify direct native spell predicates.
