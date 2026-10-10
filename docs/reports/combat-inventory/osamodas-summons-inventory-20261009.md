# Osamodas summons inventory — 2026-10-09

Inventory only. No implementation, database mutation, service restart or deployment was performed for this review. Current source was inspected; historical automated outcomes below are attributed to their reports rather than claimed as new runs. Concurrent source/catalog migration means source paths and published catalog keys must be distinguished.

## Scope and conclusion

The captured-creature system is substantially implemented: owned ten-slot storage, selection, capture320, deployment324, native scaling/book/codec, controller identity, recall859, settled-death retirement and departure availability reset all have production code and focused tests. It is incorrect to describe all these as absent based on the first October7 reports. Equally, separate component tests and one captured profile's full book do not establish a complete usable Osamodas lifecycle in the client.

Three independent summon domains must remain separate:

| Domain | Producer and authority | Inventory boundary |
|---|---|---|
| Captured creatures | Family320 capture; owned Symbiot descriptor; family324 deployment | 33 original capture-eligible profiles, 181 original book entries in the initial export. Selected owned entry determines profile, name and slot. |
| Nested captured-creature summons | Ordinary family307 with scoped source profile/book | Eight additional nested profiles; total captured dependency closure41 profiles,195 spells,178 states,21 areas,2156 effects. Nested profiles are not capturable roster entries. |
| Static class summon, including Jamajam | Family307/native descriptor and own book | Jamajam profile1620, summoned via7350; actions7351–7355. Shared39-profile/43-unique-ability static catalog is across classes, not39 Osamodas summons. |

Catalog filenames cited in historical evidence, including `native-class-captured-profiles.json`, are now logical catalog keys served by `server/wakfu_server/storage/native_catalog.py` through pinned PostgreSQL releases. Their absence as plain checkout JSON is not a missing gameplay definition. The active published release was not inspected in this subtask.

## Current component inventory

| Component | Present implementation / evidence | What remains unproven |
|---|---|---|
| Ten-slot component | `characters/captured_roster.py`: immutable owner-bound descriptors, availability, selection, native yS/yT/tr codec; signed fields/UTF-8/truncation tests in `test_captured_roster.py`. `captured_roster_fresh.py` permits empty initialization only at proven fresh breed2 construction. | Current player's actual persisted contents and client display, not inferred from empty fixtures. |
| Persistence | `captured_roster_store.py` owner locking/revisions; missing schema exposes unknown rather than invented empty roster. `combat_captured_roster_checkpoint.py` saves plain mutation records in existing fight/terminal transaction. `test_captured_roster_checkpoint.py` and `test_captured_roster_departure_integration.py` cover unchanged revision, ownership and failed persistence. | Published schema availability/current live row was not queried. Old “migration075 unapplied” statements are historical, not current deployment findings. |
| Slot selection | `captured_roster_selection.py`; opcode13571 in `local_game_server.py`. Exact9-byte owner/slot packet, combat-session execution with no independent DB commit, exploration owner-locked transaction. | Visible selected slot after reconnect, out-of-order packets, simultaneous multi-character selection and crash recovery. |
| Capture | `combat_capture_handler.py`, `combat_capture_slot.py`: native NPC kind and dTE checks, native properties/counters, actual owner component; lowest empty slot; full roster returns failure; fresh equal-profile descriptors are permitted by native identity semantics. Tests cover full roster, ineligible summon/type and missing counter authority. | Entire eligible33-profile domain, all ten slots, duplicate profile capture and full-slot client behavior. A marked living creature becoming a roster entry only after actual lethal event must be checked at the spell graph, not inferred from isolated320 handler. |
| Captured creation | `combat_captured_summon.py`, `combat_captured_summon_handler.py`: selected availability, reserved actor UID, actual caster level/team/direction/controller, descriptor initializer, factory→fan→lE(true)→slot unavailable ordering. Origin and owner/slot are recorded in registration authority. | Multi-profile positive graph execution, two-player ownership isolation, current client spawn/labels/timeline/own bar, rollback after every late failure. |
| Scaling | `combat_captured_scaling.py`: actual fan current/raw-maximum groups and float parameters; exactly two parameters select scaling factors. | Published spell variants and all characteristic combinations, especially owner stats/passives after summon creation and level changes. |
| Own action book | Scoped original captured books; `combat_captured_dependencies.py` imports nested constructor closure/level-zero roots; raw action UIDs remain summon-owned rather than player's deck. | Every legal ability/effect branch of195 spells. Profile5347's three committed owner/empty-cell branches are a narrow sample, not general enemy damage certification. |
| Control | `combat_ai_control.py` family325 mutates native AI/control observer, restores class baseline on removal; `test_combat_ai_control*.py` includes retained runtime boundaries. Controller/master, account owner, summon UID and effect UID remain separate identities. | Actual action bar switch and turn completion for captured and Jamajam actors, owner death/disconnect, reconnection while summon acts, controller changes and nested summons. |
| Recognition/count | Shared validated registration supplies dTE and origin; native count requires registered in-play actors, native dead status, exact direct controller and property103 exclusion. | Osa-specific creation→stat→movement→turn→reconnect count/client consistency. Slot availability is not NbSummons and dead registration is not a living count. |
| Recall859 | `combat_summon_recall.py`: exact eHP owner/direct controller; clears one counter each65/66/19/12, sets HP minimum and KO maximum0; death callback/OFF_PLAY is separate from retirement. `test_combat_summon_recall.py` checks phase order, raw HP, ownership and callback rollback. | Actual spell-driven recall followed by settlement, slot reuse, cell reuse, correct death animation and client removal in one transaction. Retained859 explicitly unsupported; reachability from actual class graph must be established before calling it a class defect. |
| Settled retirement | `combat_summon_retirement.py` now calls `release_captured_slot_on_retirement` after exact registered source validation and QI/global/timeline retirement. `test_combat_summon_retirement.py::test_captured_retirement_releases_exact_slot_without_changing_descriptor` covers bound slot release. | Natural death/recall/end-fight complete loop across several profiles and rejected duplicate events. This integration is present despite older component report describing it as pending. |
| Departure/reset | `combat_captured_roster_lifecycle.py`: actual controlled PC teardown resets all ten availability flags, preserving descriptors and selection. `persist_departing_captured_roster` stages a private snapshot and saves after exit receipt/owner fences. | Real disconnect/resume, surrender, victory, defeat, dungeon continuation and current world-return packets with two clients. |
| UI roster release/rename | Selection and combat capture/deployment are located; this review found no dedicated captured-descriptor deletion/rename handler in `characters/` or the server opcode selection branch. | Determine original UI request/producer and whether UI exposes these operations. This is an unlocated capability, not a proved reachable rejection or authorization to invent a protocol. |

## Jamajam and auxiliary action inventory

Jamajam7350 is a separate static/fresh summon profile1620, not a captured descriptor. Its own five auxiliary actions are7351 Intercambio Astral,7352 Aura lunar,7353 Aura Solar,7354 Motivación Estrellada and7355 Nova. The grant graph passes through state7135; references in the owner's grant closure do not imply all actions belong in the owner's permanent player deck. Actual actor-owned book/target criteria are authoritative.

`class-summon-descriptors-native-review-20261007.md` records historical missing root-selector/controller/definition issues for7354/7355. Its later compiler correction included all319 scoped granted records in the exact623-effect own-book closure and both references subsequently prepared. Therefore those old missing-definition observations are not current known defects. The63 prepared target attempts in that report are preparation only; no complete committed Jamajam five-action loop is established there.

Required inventory probes: creation cost/initial states/control/timeline; each auxiliary action at a legal owner/ally/enemy/empty target; positive and negative original-controller conditions; solar/lunar area owner, shape, occupants and expiry; Nova costs/consequences; owner death, summon death, dismissal, reconnection and post-fight cleanup. Check property103 count exclusion from actual profile authority rather than assuming every static summon contributes to the captured summon limit. Any ephemeral/static lifecycle must derive from actual native properties/timers, not the captured slot release policy.

## Existing transaction evidence and its limits

[Captured typed closure](class-captured-native-typed-closure-20261008.md) reconciles successive runs:

- Initial full parent7348 rejected downstream `GetMonstersInFight`; this was later surpassed by complete prepare run03 and commit run04. Do not report the old rejection as current without replay.
- Run04 committed captured actor295,73 packets, turn transition/ACK and slot3 unavailable; repeated parent cast rejected without source/RNG mutation.
- Run06 independently committed7356/7357/7358 from actual captured turn. Each consumed WP6→5 with AP4/MP0 unchanged.7356 hit owner7 HP1580→1507;7357 used empty-cell family302;7358 used owner177/300 children. No enemy-damage outcome or full battle is claimed.
- Exact capture mark/lethal death evidence is referenced by [manual-osamodas-system-20261008.md](manual-osamodas-system-20261008.md). Its character13/level200 setup is historical and unverified now; do not assume those credentials, position, deck or roster remain current.

No manual full lifecycle pass was located. Existing focused test modules demonstrate components and bounded providers; this review did not rerun them. The parent inventory's delegated current batch should be used for any new test total.

## Highest-risk acceptance gaps

1. Capture living eligible creature → lethal event → exactly one persistent descriptor → reconnect → select → captured324 creation → actual summon controlled turn/action → recall/death retirement → released slot and freed LOS/QI → same descriptor resummon.
2. Two Osamodas owners, repeated same-profile captures and multiple registered summons: exact ownership/count/slot separation, foreign action UID rejection, one-time resources and RNG rollback.
3. Jamajam creation and all five own actions alongside a captured creature, dragon mode and mode changes; native count and direct-controller predicates must remain consistent.
4. Monster death/corpse and summon removal must not block LOS/cells or animate another entity; first turn, reconnect, surrender, terminal rewards and dungeon continuation must preserve both clients.
5. Retained324 and retained859 reject explicitly. Establish if actual active/passive/event roots can reach those variants; unsupported capability is not automatically a class-blocking defect.

The existing manual system card is a starting sequence, not the complete class inventory. Add all profile/book and Jamajam/ownership/lifecycle branches before calling Osamodas100% or accepted5/18.
