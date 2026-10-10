# Multi-step movement QI callback mismatch

## Observed incident

At 2026-10-10 07:12:05 UTC, request `3f95bb9a252b4e0d8b81df24555e8b99`, fight 150, effect 152027 failed with `Native QI actor registration requires an actual lifecycle update`. Its caster 619552775529057364 is a registered faP border area, not the captured Tofu (actor 234). The affected fighter is NPC -1125899906844032, and the callback cell is (-193,-26,0).

The same request's `combat_monster_tactical_action` records two movement previews, one failed, and an actual end-turn decision. This is a rejected forecast; it does not establish a committed Tofu action or corrupt checkpoint.

Readonly inspection of fight 150's aborted checkpoint found all five fighters IN_PLAY with positive HP and exact matching QI slots, positions and radii. Replaying the common `move_registered_actor` producer to (-193,-26,0) also passed `current_registry`. No database state was changed.

## Concrete source cause

`server/ai-service/wakfu_ai/native/native_oracle.py` first executes the whole movement path through `Fight.move/server_move`, which updates QI to the final destination. Its subsequent per-step area callback loop directly assigns `actor.position = cell`. For an intermediate step, the actor coordinate differs from the still-final QI row. Original faP effect 152027 queries native geometry and the shared registry correctly rejects that stale pair.

The execution adapter should use `move_registered_actor` for each callback step, as the existing world `prepare_area_movement` path does. This concerns execution-state coherence, not planner scoring or monster spell implementation. Lifecycle admission guards must remain intact.

## Prepared verification

`test_native_movement_qi_boundaries.py` exercises the actual NativeOracle preview and original area callback with a two-step native NPC route. It checks complete QI consistency at every callback and isolation of the live source. `test_combat_qi_death_lifecycle.py` additionally checks that actual multi-step QK updates remain current and an illegally moved scalar is rejected without repairing the registry.

The registry failure messages now identify the actual actor, lifecycle boundary, byte/radius/XY tuple and expected QI tuple. No guard was relaxed. The narrow adapter correction is implemented. Focused automated verification is complete; no deployment or restart occurred.

The first focused run exposed an additional execution-adapter gap: its factory did not publish the actual rail/tackle actor authority, unlike the world factory. Native movement now binds that same complete registered/ordinary actor provider before the FSM, including forecasts from reconstructed checkpoints. The original post-movement deterministic forecast RNG seed and callback action sequence are preserved. Isolated QI lifecycle fixtures now explicitly declare typed movement facts; no runtime guard was relaxed. The QI lifecycle suite (13 tests) and captured-roster checkpoint suite (5 tests) passed. The actual bridge regression selects a legal two-step route directly from the original arena, preferring native QI.P perimeter callbacks, and passed (1 test, 23 seconds). Combined focused evidence is 13 QI lifecycle tests, 5 captured-roster checkpoint tests and 1 actual execution-bridge preview test across separate runs. The final integrated gate remains owned by the parent agent.
