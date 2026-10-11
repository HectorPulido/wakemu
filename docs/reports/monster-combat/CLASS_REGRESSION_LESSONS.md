# Class Regression Fixture Lessons

This note records fixture defects found while running the native class regression set alongside the under-level-10 NPC spell activation work. The regression target is to preserve class spell and combat behavior; these corrections are test setup only and do not relax behavioral assertions.

## Authority facts required by the fixtures

- A native QI population must be produced from the serialized arena while the fight is still in placement. Install actor slots before `Fight.ready()`. Include both placed actors in the rectangle, and initialize global PV fighter collections at the same fresh participant-registration boundary when forecasts evaluate ordinary fighter membership.
- Actor LOS heights come from the actor snapshot catalog: player height uses `default_actor_los_height`; NPC height uses the exact NPC profile, such as ref 1740. A fixture that mixes both actor kinds must not apply the player default to its NPC.
- Position changes after QI registration must go through `move_registered_actor()`. Directly changing `Actor.position` leaves the QI slot at its registered cell and makes native movement reject the fixture.
- Movement previews that evaluate disengagement need `native_rail_movement_authority`, including current actor metadata and property facts. Direct `NativeProvider.actions()` can produce movement paths without this authority, but preview then rejects those paths.
- Resource current values must agree across the actor field, effective stat snapshot, and raw current snapshot. For example, changing `mp` to 6 while leaving the native max and raw maximum snapshots at 3 is not a valid native actor state. Keep fixtures within measured resource bounds and adjust the map positions when a test needs a reachable approach.

## Changes and verification

The affected fixtures are in `test_combat_spell_transaction.py`, `test_combat_npc_attack.py`, `test_combat_xelor_cast.py`, and `test_combat_tactical_ai.py`. They now provide measured LOS heights, fresh QI/PV producers, registered movement updates, explicit `po.SX` bytes, and movement-preview authority. The small-position corpus uses the NPC's native 3 MP snapshot and places the remote target within a legal approach distance.

The coordinated preserved-baseline run recorded 167 tests with 1 failure and 2 errors before the final targeted fixture corrections. It showed that Wonejo forecast, replay, state-isolation, and HTTP decision cases passed once QI and PV producers were present. One remaining baseline error was in the concurrently added Feca Orbe fixture (`test_orbe_delivers_armor_at_actual_turn_boundary`), where an actor roster change lacked native summon registration; that case is outside the four edited fixtures.

After the final movement-authority and legal-position updates, the two focused tactical tests passed against the read-only PostgreSQL-backed baseline catalog:

- `test_jalato_native_spell_rejection_keeps_certified_movement_candidate`
- `test_native_build_request_warm_cost_on_small_position_corpus`

The warm-cost test reported 24 forecasts per position and 19 transitions, with 7 adjacent casts and 8 approach-case casts. Measured producer time was about 152 ms for adjacent placement and 143 ms for approach placement on this run. These values are diagnostic timing observations, not performance guarantees.

The targeted run validated only those two cases and did not rerun the full expanded suite or certify a candidate release. Runtime sources changed during concurrent NPC activation work, so the earlier broad baseline report is tied to its recorded source state. No production combat code, services, containers, or database rows were changed by this fixture review.

## Original-controller area packet-format discrepancy (unresolved)

`test_combat_original_controller_area.py::OriginalControllerAreaTests.test_all_native_hours_use_original_controller_and_original_source_orientation` configures `StatExecutionContext(... retained=False, ...)`, while its packet assertions read the effect family at byte 12 and parse fields starting at byte 18, which match the retained `13497` layout. Independent bytecode inspection and an offline probe against the installed client's actual `cvY`/13497 and `cvX`/12613 decoders now confirm both envelopes: retained family@12/payload@18, immediate flag@12/family@13/payload@19. The JAR SHA-256 is `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`. Evidence is under `.runtime/monster-failure-triage-20261010/native-client/`. The original expectation remains unchanged and visible as a known contradiction. The local parser proposal is preserved at `.runtime/monster-failure-triage-20261010/controller-parser-proposal.patch`; it was not applied to obtain a green result.
