# Shared combat LEGO lifecycle review — 2026-10-11

Scope: read-only review of the recent shared corrections, plus a new test-only module. No production source, service or database changes.

## Findings

No hardcoded breed, player7 identity or monster species gate was found in the reviewed resolved-population scope, selected area manager, signed state preparation, native321 decurse or own-Qq routing corrections. The shared boundary is native PV identity and contract, not a class list.

`combat_effect_dispatch.py::_execute` resolves a population once, opens the configured scope around the complete ordered traversal and then invokes `_execute_resolved`. `combat_effect_runtime.py` supplies both caster and recipient identities. `combat_state_managers.py::selected_area_pv_scope` validates real native prototypes before holding their actual row pointers. ContextVar tokens are reset in `finally`, with fight-object identity checked when reading retained rows. This preserves later selected recipients after earlier siblings unregister them without making removed areas visible to spatial scans.

`state_manager` intentionally sees active/retired Qf managers, whereas `retained_area_pv_row` additionally sees execution-local selected/removed PV pointers. A removed null-Qf area can still be a known selected PV and satisfy its identity/owner predicate while having no state manager. Do not repair this distinction by inventing ledgers, HP or turns. Existing real Sadida multi-recipient failure motivated the selection lifetime change; the generic regression separates that lifetime contract from Sadida semantics.

Signed state preparation permits the original signed-short calculation before criteria, while actual application retains strict validation. Native321 prepares the runner/value and phases before deferred execution, releases prepared entries on failure and completion, and does not borrow421 dispel flag semantics. The reviewed paths do not require a player recipient; NPC fighters remain ordinary registered actor managers. Actual summon birth/action tests elsewhere remain necessary to verify their populated metadata.

Fight-start first-round publication is an explicit Wakemu server policy. It sets the validated existing round before callbacks, not an invented extra turn. Controlled class managers receive1028; every installed participant receives1003. This controlled-only1028 distinction is declared policy, not proof that every native monster ability is class initialization. A future monster-defined1028 consumer must be evaluated against its actual source before changing the policy.

## Automated evidence

Luna reports38/38 existing focused tests passing against active PG677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d: selected-area scope, start events, state decurse, effect resolver and deferred subscription runners. Evidence: `.runtime/remaining-six-refresh-20261010/generic-scope-start-decurse-resolver-677.log`.

New module `server/tests/test_combat_generic_population_lifecycle.py` adds:

- Real published null-Qf GLYPH validation, negative NPC/companion-like owner identities, removed selected-area recognition, absent state manager and absent spatial membership.
- Failed private-preview execution releasing contextual pointers, preserving the authoritative population and isolating another fight with the same area UID.
- Actual two-player plus NPC `Fight.ready` boundary: every callback sees table/round1, class setup excludes NPC, general start includes all, turn remains1.

These tests deliberately do not claim actual companion birth, arbitrary monster spell execution, transport/reconnect or complete spell-transaction rollback. Their callback collector observes the delivery boundary; it does not replace the production scope/prototype/query/first-round behavior. Luna executed this module and `test_combat_state_signed_calculation`:6/6 PASS, pinned active677; log `.runtime/remaining-six-refresh-20261010/generic-population-signed-677.log` (population source1eb5c724, signed92ceeb8d).

## Remaining broader acceptance

Retain existing actual Sadida, Enutrof and Aniripsa summon tests in the frozen validation batch. Add a future actual monster-owned multi-area spell transaction with a deliberately failing later child, asserting authoritative checkpoint plus RNG/UID/payment rollback, no scope leak, and legal replay afterwards. This is stronger than a context manager unit test and should use a real published NPC ability rather than a fabricated species-specific spell. Multi-client reconnect and terminal dungeon progression remain manual/system acceptance, not attested by these unit tests.
