# Detached constructor manager identities

Offline representative: Emperador Gelax (1345), blocked by `Unverified native cell group manager` while constructing initial state children. The actual freshly created actor owns a Qf before fight roster registration. `detached_summon_scope` already authenticates its native controller, targeting identity, team -1 and StateLedger; `state_manager` and `state_managers` already include that scoped actor. The retained cell-group view alone rejected the real caster because it checked the registered roster directly.

The general correction resolves the manager through `registered_or_detached_actor`. It keeps the subscription family, exact wire caster identity, missing actor target and retained manager identity requirements. It does not add the constructor to the roster or change ordinary selection/event populations. The scope is fight-specific and disappears on exit.

Native disabled spell-level runner 47/eZb had the same roster-only assumption in caster validation, target validation and packet actor lookup. The source-qualified detached SELF actor can now complete that runner during actual placement construction, using the shared `constructor_stat_context` predicate. Registered actors in placement remain rejected. Cross-actor deliveries involving detached actors remain rejected: constructor delivery is SELF. Registered ordinary casts retain their previous eligibility.

Native source: `.runtime/combat-review-20261007/family47/eZb.txt` shows `C`, `c` and `bbR` immediately returning. Thus effect47 remains a disabled spellbook mutation with its existing lifecycle and notification behavior; no spellbook behavior has been invented. Existing `combat_retained_runtime.finish_group` retains real Qf ownership after child execution, and `combat_summon_initialization` explicitly establishes construction before controller/roster registration.

New regressions in `test_combat_constructor_manager_identity.py` cover authenticated detached manager acceptance, forged manager rejection, foreign fight isolation, scope cleanup, SELF effect47 notification, no roster registration, cross-actor rejection and prepared-runner cleanup. Existing retained cell-group and disabled47 regression modules are unchanged. Focused execution is delegated to the monster test owner; direct bare execution requires the normal PostgreSQL catalog bootstrap.

This is code and local verification preparation only. No catalog publication, image build, restart or live activation was performed.

## Next boundary: authoritative target identity

After the manager fix, the actual 1345 construction completed: five initial states and twelve placement effects. A separate cheap first-spell probe then failed the strict requested/native target identity check. This was a fixture overlap, not another constructor failure.

Exact offline witness (`.runtime/monster-blocker-recovery-20261011/gelax-target-diagnostic.json`): caster -200 at (-8,-7,-1), native physical radius1; player7 at adjacent (-9,-7,-1), radius0. QI iteration on the requested player cell is [-200,7], so the native first-fighter target is -200. The validator had requested7 using anchor-position assumptions. Neighboring apparent empty cells inside the caster footprint similarly resolve -200. The guard correctly rejects both mistakes.

`combat_npc_spell` now attaches `native_target_diagnostic` to this same rejection, recording requested and native identities, cell, and ordered QI occupants. The identity comparison and exception message remain unchanged. Validator search owns the fix: nonoverlapping real actor placements, radius-aware search bounds, and native target authority. AI action producers must also respect QI footprints rather than anchor-only occupancy; no identity bypass is appropriate.

## Carrier proof and native permanent flag

Representative2400 (Marino del Tyra Nis, level98) had one initial state1581, whose application succeeded and retained child349. The native state carrier itself was absent correctly: turn duration -1, realtime0, skip-turn/permanent flag true. The actual `state_requires_retention` predicate treats that flag as selecting the realtime indefinite branch; it does not retain this turn-only sentinel. The validation helper previously recognized only two zero clocks as nonretained, incorrectly rejecting the complete native placement snapshot.

The helper now follows the production retention predicate. Both-zero clocks are always nonretained; a positive turn clock or any nonzero realtime clock is retained for either flag; the remaining negative-turn/zero-realtime case requires the real flag and shared predicate. No unknown flag is guessed. Existing zero/positive regression fixtures remain valid without test edits. The actual replay passed: state1581 applied, `nonretained_state_ids=[1581]`, placement147bytes, one child349, zero310. Before/after receipts are preserved separately in the recovery directory.

A second actor/area classification inconsistency in `NativeStateHandler._area_target_blocked` now resolves the authenticated detached actor before requesting area authority. The actual constructor fighter is not an unregistered area. Once its scope ends, the same unknown identity still reaches and fails the strict area authority guard. No area authority contract was relaxed.
