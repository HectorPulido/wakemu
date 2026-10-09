# Area-only retained state containers

Bulk spell8137 failed on effect379770/family315, target area218, state UID221, with `Missing actual retained child state container`. The area runner already carries an actual state owner. `NativeRetainedRuntime.record` captures the immutable original RunningState PL after its owned runner is installed; its ownership checker previously inspected only statistics and groups, omitting areas.

`owned_container_users` now includes registered `native_owned_area_effects` with the exact matching state UID. This preserves the real owner snapshot while an area child remains, including after the parent leaves Qf, and rejects unrelated areas. It creates no state or fictitious container. This complements central child-area removal on parent expiration, without changing clock semantics.

`PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_combat_area_state_container.py`: 2 tests pass. Actual class8137 execution remains pending refreshed offline validation.
