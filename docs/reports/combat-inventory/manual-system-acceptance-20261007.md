# Complete class-combat manual acceptance

> Manual execution plan superseded by [representative acceptance cards](manual-representative-acceptance-20261008.md). Hector is not required to execute every spell row or enemy combination. This older exhaustive document remains a scope/reference checklist, not the current manual workload.

Status: prepared, not executed. This is the single final acceptance plan for all 18 installed classes and the complete class spell dependency graph. No server restart, deployment, account/database change or user probe was performed to prepare it. Schedule this session after automated integration and the user-authorized deployment are complete.

## Required evidence before the session

Record the deployed source/catalog hashes and build identifier. Confirm the offline audit snapshot corresponds to that exact build. Pending mechanics, unknown producers, unresolved native decoding, missing states/criteria or unverified packets must be listed explicitly; they cannot become a pass by using a simpler scenario. The27 native surface decoding failures remain unavailable map authority until resolved. Use verified map 1134 for this session; other maps require their own map/terrain validation.

The acceptance register `manual-acceptance-spell-register-20261007.csv` contains all 722 owned class spells plus 91 class-granted spells, 813 unique IDs. All result columns start pending. Its granted rows retain native grant paths; inaccessible granted spells require those actual conditions to be reached, rather than a fabricated spellbook entry. Complete the graph's referenced states, conditional branches, area templates, summon abilities and lifecycle sequences using `class-dependency-coverage-20261007.csv`, native spell trees and the most recent frozen audits. A completed basic fight or many generated scenarios do not certify this graph.

For each case, prepare an expected-value sheet from the installed native data and its verified evaluation at the actual level/context. Include active/critical roots, selected conditional casting contract, costs, range, line/diagonal/path/LOS flags, target constraints, selectors, affected cells, state levels/durations, resource maxima, effect amounts, removal/trigger ordering and applicable passive/innate/granted effects. A tooltip states the player-facing contract; raw effect parameters alone are not final damage. Damage/healing expectations must include actual stats, resistances, orientation, armor, critical result, target count, rounding and triggered effects. Missing expected evidence is pending, not permission to invent a number.

## Test roster and verified commands

Use an administrator account with the test roster already prepared and with a second player available for allies, control and multi-player synchronization. Verify `WAKFU_ENABLE_COMBAT_TEST=1` in the deployed configuration before expecting test spawn commands. Account authorization is checked by `command_permissions.authorize_command`; ordinary players normally have only `!ayuda` and `!pos`. Level/resource overrides in the deployed environment must be recorded before comparing costs and maxima.

The existing offline tool `server/tools/create-class-test-characters.py` creates 19 account-owned characters: one for each 18 class plus a Sacro control character. It defaults to level 200,24 slots and prefix `Prueba`; new characters receive the first12 available active spells and no passives. Existing same-name characters are reused without resetting their level/build. Its invocation requires the real database URL and account ID; this is a write prerequisite for the operator, not a command executed here. Roster report, account IDs and credentials remain private. There is no verified chat command for changing class, giving an arbitrary spell, setting critical chance or resetting an existing character to a lower level.

Use separate level 1/20/200 roster characters for level-boundary acceptance. `!nivel` only raises a level, and instructs character reselection to refresh spells/points. Do not attempt to lower level 200 characters to 20.

Commands below are verified against `server/wakfu_server/maps/test_console.py` and `server/local_game_server.py`. Enter them in game chat outside combat and outside the haven bag:

```text
!ayuda
!pos
!tp 1134 -8 -7 -1
!mob 5525 1 1
```

Expected: help lists supported commands; position reports map/instance/XYZ; teleport reports a local transition to map 1134 instance 0 at the requested native walkable cell; spawn reports a newly created group near the character with a reachable free native position. Select that newly created group's fight interaction. Monster behavior is only a test fixture; monster-spell correctness and AI behavior are outside this class acceptance scope.

For tests needing multiple targets, use `!mob 5525 1 3` and inspect the newly created group. The quantity is bounded 1..8 and spawning requires instance 0. For level progression of a fresh low-level test character only:

```text
!nivel 20
```

Expected: level saved and instruction to reselect the character; after reselection, the level and native available spell/deck slots update. The permitted command syntax for a specifically required, separately verified item is `!item <native_reference> <quantity>`; the receipt supplies its actual UID, used in `!equip <uid> <slot>`. No item/reference/slot or damage/critical bonus is assumed by this plan. Prepare exact verified equipment references in the expected-value sheet if such equipment is needed.

For the native nonzero-floor regression, outside combat:

```text
!tp 1134 61 -128 50
!mob 5525 1 1
```

Expected: the arena contains the chosen native floor, selected surface masks agree with native Vy indices, and actions on that floor do not fail due to selection of the lower surface. The source-only bounded proof at this location has 118 selected cells and one nonzero index; actual encounter bounds/configuration must be recorded rather than assumed identical.

## One sequential session

1. Select the class and level under test. Open the spellbook and record the actual level, innate states, active/passive/granted entries and deck cap. Capture spell tooltips before equipping a legal first active batch and the intended passive batch. Respect 12 active slots and 6 passive slots at level 200; lower-level slot unlocks remain native. Cover every813 register row in successive legal decks/conditions; no single 12-spell deck represents the full class.
2. Start a fight, place both sides and press Ready. Expect each actor exactly once, correct native selected floors, resource/HP maxima, initiative/current actor and installed innates/passives. Client and server must agree before any cast. End two full turn cycles without casting; verify start/end subscriptions, per-turn counters, durations and HUD refresh. Record actions and turn ACKs from both clients.
3. For every active/granted spell, test its displayed minimum and maximum range, one cell inside a prohibited minimum and one cell beyond the maximum. Repeat relevant linear/diagonal, self/ally/enemy/empty-cell, blocked/occupied cell and LOS cases. Castable highlighted cells and server acceptance must agree with the selected conditional contract; rejected casts leave resources, counters, effect UIDs, areas and states unchanged.
4. Cast once from a clean state. Record AP/MP/WP and HP before/after, selected cells, actual hit/critical indication, per-target amounts, armor changes, placement/orientation and logs. Compare each component to the prepared exact expectation. Repeat with insufficient each required resource and exhausted native per-target/per-turn/cooldown limits. No rejected attempt consumes resources or advances those limits.
5. Exercise normal and critical branches under a verified actual critical producer. Random normal/critical casts are recorded separately; absence of an observed critical is pending. Do not assume multiplying normal damage certifies the critical effect tree. Test positive and negative criteria, stack thresholds, duration expiry, overwrite/removal, dispel/immunity, death and target disappearance where the actual spell graph includes them.
6. Add each passive/innate and its required triggers, then repeat the affected casts. Compare the same actor/level/stats with and without the passive in a new fight. Confirm trigger source, owner, target, exact value, once-per-event limits and cleanup. An installed passive without the advertised activation is pending. Repeat every distinct conditional branch and interaction recorded in the dependency graph.
7. For summons and controlled actors, verify actual native description, appearance, HP/AP/MP/WP, owner/controller, placement/occupancy, timeline and legal granted abilities. Move, cast, control where actually provided, change turn, kill/despawn and recast. Compare both clients and server after each transition. No invisible blockers, stale HUD actor, duplicate effects or leaked controller remains. Balises/areas that are not native fighters must retain their actual native lifecycle, rather than inherit fake fighter stats/timeline behavior.
8. For glyphs, traps, beacons, bombs, gates and other areas present in the native graph, test placement legality, area owner/affiliation, footprint/height, overlapping areas, ally/enemy selection, entering/leaving, movement/cast/start/end triggers, duration, activation and removal. Check whether an area truly occupies the QI registry; visible representation does not by itself establish blocking. A blocked destination is distinct from a missing selected surface. Test teleport check-cells variants against that distinction.
9. Exercise the class's full advertised sequences with actual state/resource setup: transformation → granted spells → action → expiry/removal; summon/area → trigger → owner death/removal; resource gain → spending → maximum changes → restoration; displacement → collision → subscriptions. Derive exact sequences from the native grant paths and tooltips. Evaluate both positive activation and an explicit negative branch, including cross-class ally/enemy interactions.
10. Attempt a cast that the server rejects after preview validation under a specifically prepared legal failure case. Compare the full before/after state and packets: no partial cost, movement, state, summon, area, retained effect, RNG/counter advancement or client desynchronization may escape the failed transaction. A visually unchanged HP bar alone does not prove rollback.
11. Finish by victory and by defeat/withdrawal in separate fights, then start a fresh fight. Verify retained/area/summon/controller cleanup, world return, HP/resources, deck and innate reinitialization. Reconnect one participant after a completed fight and confirm no stale actor/area/turn survives. Preserve rewards according to the separately verified lifecycle policy.

## Class rotation and class-specific sequences

These labels and IDs come from the existing roster source. The additional focus column is a checklist to bind to the actual installed tooltip/dependency graph, not a claim that every named mechanic is already implemented. Mark a focus inapplicable only with native evidence.

| ID | Class | Additional complete-sequence focus |
|---|---|---|
|1|Feca|Armor, glyph ownership/activation, state duration and protection triggers|
|2|Osamodas|Summon descriptors/abilities/control, transformation and granted spells|
|3|Anutrof|Class resource/state transitions, range/terrain conditions and transformations|
|4|Sram|Traps, concealment/state conditions, positional and triggered damage|
|5|Xelor|AP resource and maximum changes, delayed/turn triggers, class areas|
|6|Zurcarak|Random/probability branches, critical branches and state-conditioned effects|
|7|Aniripsa|Ally/enemy healing/damage branches, marks/states and triggered effects|
|8|Yopuka|Class combo/state sequences, AP/MP/WP spending, movement and collision|
|9|Ocra|Exact client/server range, balise placement/activation/removal and area selection|
|10|Sadida|Doll/summon grant paths, control/ownership, armor/healing and shared triggers|
|11|Sacro|HP-dependent thresholds, movement/swap/carry relations and class resources|
|12|Pandawa|Carry/uncarry, controller/source selection, area/container and turn states|
|13|Tymador|Bomb placement/chains, triggers, ownership, removal and granted abilities|
|14|Zobal|Masks/transformation, doubles/controlled actors and passive activation|
|15|Uginak|Transformation/granted effects, target marking, class resource restoration|
|16|Steamer|Class areas/constructs, transformation/granted effects and damage modes|
|18|Selotrop|Gate placement/ownership, gate-conditioned eligibility and movement|
|19|Hipermago|Class resources, elemental state combinations, conditional/granted effects|

## Recording and completion rule

For each spell row, retain tooltip capture, frozen native expected sheet, character/level/build, actor stats, map/floor, target identity/type, branch/critical/trigger setup, ordered actions and before/after values from both clients and server. Record states and effect/area/summon IDs needed to replay a mismatch. Store captures and private logs outside commits; put sanitized evidence paths in the register.

Set a row to pass only after all applicable normal/critical, conditional, state/turn, client synchronization, sequence/synergy and rollback checks have evidence. Document native-proven inapplicability instead of silently omitting a branch. Class completion additionally requires its referenced innates, states, passives, areas, summons, control, granted abilities and cross-spell sequences. Overall completion requires all 18 classes and the 813-row register plus graph dependencies; scenario totals or handler counts are insufficient. Failures are grouped by shared mechanism first, then class/state/condition specifics.
