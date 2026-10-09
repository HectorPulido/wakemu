# Native GATE creation and area authority

The shared area creator now supports native `faX` / `bcS` GATE prototypes. This is a type contract, not a spell or class exception. Both catalog GATE prototypes (823 and 2131) satisfy it: type 19, fixed point geometry, empty effects and entry/exit masks. Their native properties omit property 12, so their actual Qf is null; the server does not create a state ledger for them.

## Native evidence

`ProbeNativeGateContract.java` loads the actual client binary prototypes and constructs both areas through `bcN` / `fbm`. It verifies `bcS` / `faX` identity, type 19, fixed position, zero radius, null Qf, empty callback targets, and fresh Qq guards (`baG=false`, `baK=false`, `baF=true`). Changing the owner's affiliation after construction leaves the area's captured affiliation unchanged. Both probes pass. Private output: `.runtime/combat-review-20261007/gate-probe/native-proof.txt`.

The `faV.j(PV)` bytecode copies bcM only from an actual eGj owner (native PV type 20). Other owner types retain the constructor value -1. The runtime adapter provides this typed authority through `area_affiliation(preview, source_identity)`. The creator validates its signed-byte result before allocating UIDs or emitting packets. When present, this callback captures affiliation for every supported faV type; GATE requires it.

`Qq.bcN` is a separate obstacle identifier. Native `faV.b(fbm)` copies it from the creation specification; eYQ's fresh fbm leaves it at zero. `bcS.aQc` selects visual sprites and does not establish spatial occupancy. The server records this constructor fact separately from captured bcM.

## Shared implementation

The creator, registered-area PV resolver, Qq guard resolver, and Qs query boundary accept the proven faX contract. Gate positions remain independent of owner movement. Team-area counting uses captured affiliation when available, rather than recalculating it from the current owner. Existing legacy rows without captured affiliation still use the earlier actor fallback; those rows are not newly accredited by this change.

No packet codec or area event dispatcher changes were needed. The existing area application packet carries creation. The supported GATE prototypes contain no effects or event masks to execute. Missing affiliation authority and unsupported GATE callbacks remain explicit errors.

## Validation and limits

36 lightweight unit tests pass across GATE lifecycle, area guard authority, Qs queries, actual/null Qf resolvers, area codec, geometry, and the adapter affiliation producer. Four new regression tests cover both native prototypes, owner movement and affiliation changes, complete explicit occupancy facts, and rejection before side effects when affiliation is absent or invalid. This run did not record a before/after source manifest; other agents were integrating shared runtime changes.

Command: `PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python -m unittest server.tests.test_combat_gate_area_lifecycle server.tests.test_combat_area_authority server.tests.test_combat_effect_area_queries server.tests.test_combat_state_managers server.tests.test_combat_state_null_area_qf server.tests.test_combat_effect_area_codec server.tests.test_combat_area_geometry server.tests.test_combat_area_affiliation_adapter`.

These tests do not prove client delivery or complete fight integration. QI.U occupancy still requires actual spatial registration, footprint and bcN facts; GATE presence tests supply an explicit complete callback and do not infer occupancy from teams, HP, or actor existence. No services, database, monster logic, or live client were used.
