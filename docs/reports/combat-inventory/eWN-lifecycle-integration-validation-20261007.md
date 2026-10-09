# eWN lifecycle and effect integration validation — 2026-10-07

The focused integration batch covered the new native eWN lifecycle/cleanup path, effect dispatch/runtime/removal, retained stat and area effects, cell groups, value transfer, maximum-resource amount/arithmetic/reduction, the `IsOnBorderCell` boolean predicate, and bootstrap/runtime-adapter integration.

Command (offline):

```sh
PYTHONPATH=server:server/tests WAKFU_NATIVE_GRANTED_CAST=1 WAKFU_NATIVE_AREA_CALLBACKS=1 /tmp/wakemu-combat-review-venv/bin/python3 -m unittest \
  test_combat_border_cell test_combat_qi_snapshot test_combat_conditions \
  test_combat_runtime_adapter test_combat_bootstrap \
  test_combat_maximum_amount_source test_combat_maximum_lifecycle \
  test_combat_maximum_reduction test_combat_maximum_resource \
  test_combat_parameter_maximum test_combat_effect_dispatch \
  test_combat_effect_runtime test_combat_effect_removal \
  test_combat_effect_area_events test_combat_retained_area_314 \
  test_combat_retained_areas test_combat_retained_cell_groups \
  test_combat_retained_groups test_combat_value_transfer \
  test_combat_value_transfer_runtime test_combat_lifecycle
```

Result: unittest discovered **147 tests total**: **138 passed and 9 skipped** in 48.087 seconds. All 9 skips are the tests in `test_combat_lifecycle.py`; its `PostgresCase.setUp` skips with `Isolated PostgreSQL required` when `WAKFU_POSTGRES_TEST_URL` is unset. That URL was intentionally not supplied, so the tests made no database connection. The suite printed its final summary, then its known lingering worker was interrupted. No Docker, database, socket, or world service was used.

One fixture needed a test-only authority correction. The spell-6266 transaction test manually built a `Fight` and omitted the current casting context that range resolution now requires. The native casting row has categories `[4, 8, 10]` and no conditional branches. The fixture now explicitly provides a fresh empty `eHl` range-modifier map and a cast context with `RANGE=0`, `carried=false`, and empty `fight_properties`; it passes that context into cast preparation. No production source changed for this correction.

All files in the pre/post SHA-256 manifests matched across the run. Key production sources:

- `combat_conditions.py`: `36f973ecb2a31acda56376a139960db53d5e2894c37dc83d0af94e2f0787d56e`
- `combat_runtime_adapter.py`: `2d9579831a7b25a396163503856501e637e77bf5722eaeaadbe622c32b81c420`
- `combat_effect_runtime.py`: `c70023b1aa23228439f733628979a6b93ebd0c4e526570b74a9c9123338989ca`
- `combat_effect_dispatch.py`: `2c9dde38b0099f3a9f29d40d69c38d5fd56095d80e5ff99a2f6f2447e9090304`
- `combat_effect_removal.py`: `216dc454fe71fa9593aec74d225edd19146c5a2bb063cd1286c71589a94505aa`
- `combat_effect_area_events.py`: `4c781242deec04e22f872708f60f703c92946299863eac198ed0a2429c4e1e75`
- `combat_retained_effects.py`: `a294f2ad74fa1bb44c717ca12c7ef922823dcb7ab23f81d7782e2dbfc29ee0a3`
- `combat_retained_runtime.py`: `b9be1a0180be274beb5883c8b8f89d2cafe97a0e02647aab852ba403d06a2898`
- `combat_value_transfer.py`: `1add905c87816c8d38550c4e3bda9d47d3c76ccf0324434b554b76de76f9adf3`
- `combat_value_transfer_runtime.py`: `688715256772f62e94ca87a829469d558d78816245a9a1c628b5a02e6101e416`
- `combat_maximum_resource.py`: `8c155aac4da0fb8d5d6fe2ffda81de2813131250bc5045947da1a707876779ad`
