# Rogue (Tymador, native breed 13) — refreshed implementation inventory

**Scope:** read-only source, catalog, and test inventory. No gameplay, protocol, database, or service edits were made; no tests were executed for this inventory task. This refresh updates the older [class review](../remaining-classes-20261010/13-review.md) against the currently active PostgreSQL catalog and the current shared combat code. It does not change user acceptance or claim manual/client verification.

## Current source authority and denominator

The active complete PostgreSQL release was `548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd`. I read it with direct SQL in a `READ ONLY` transaction, bypassing the catalog/Redis reader. It reports 7,484 documents. `spells.json` and `spell-names.json` still have the hashes recorded in the Oct. 10 source audit; the spell roster therefore agrees with the previously published reconciliation, but the active release itself has advanced since then.

The current roster contains exactly **21 owned actives, 20 owned passives, and four extra/granted actions**. The class innate record is breed 13 / `ROUBLARD`, with seeds 4464 and 7920, and source resource defaults AP 6, MP 3, WP 6, base HP 50. Those data establish catalog inputs, not runtime state initialization or user-visible behavior.

Relevant active document hashes in release `548e…`:

| Document | SHA-256 | What this establishes |
|---|---|---|
| `spells.json` | `44fcaea5a01906d1247079fe14e861ddc2b375486aa72eaaeabc976774b98fea` | Current owned IDs, breed, kind, unlock and UI order. |
| `spell-names.json` | `7a76a231b133b20499edd9bc98917596f9e5a163f713d0717d87de699831325f` | Current localized names for the owned roster. |
| `spell-effect-trees.json` | `a188b3681c79ad455d296b303491370419cbe23da130501a8b86b51bd9a518ba` | Current primary spell trees. |
| `granted-spell-effect-trees.json` | `2d07839bdf094a23cd6cba02da6853766bc21f82244b59a1d2fcdc3bfb903477` | Current extra spell and nested effect trees. |
| `breed-innate-definitions.json` | `99d83aa956797dfdb8746e485dbe267574ef606bf23c71416244e7393558c25d` | Breed 13 innate seeds and resource defaults. |
| `native-spell-casting.json` | `0e6ef6f9f3bd4f3c4192a77673fd0598034e51d1149364d66f5f24f5ff6095c9` | Per-level native AP/MP/WP spell-cost tuples. |
| `native-spell-resource-costs.json` | `fb10cfe102215efac81153552aa112a3a92d95d91dff76e53fb036d754f827b0` | Complete resource-cost tables and conditional alternatives. |
| `combat-state-definitions.json` | `845f211b808b9ce20a14b25f3e3068480094243c507e4aaa8f9da5fad5bca7b9` | Current exported state/effect definitions. |
| `native-effect-areas.json` | `e4b888bf1ddcb5a19f9c74cbb842daee6e81a3892786c32622b84b61f7329dff` | Current native area definitions. |
| `native-class-summon-abilities.json` | `d5388ce9ad2223e1e89f52fb4bab01a1d370d16aa9e5ba506d923a404041be34` | Current fixed profile ability books. |
| `native-class-summon-initial-states.json` | `4c4f97d4075b507a4c16b1b624018857d79decd34db5e109b5e8969f572a80b0` | Current fixed profile initial-state data. |

These are immutable catalog documents; their presence and hashes do not prove runtime execution. The previous per-class structural inventory was generated from the Oct. 7 native graph and carries release `a1f84e…`; I use its closure only as a dated structural index and explicitly recheck the queried IDs against the active release below.

## Owned spell roster and bounded action evidence

The current native casting document gives the following AP/MP/WP costs. A cost tuple is source metadata; it is not evidence that every branch pays correctly in a fight. The historical normal-cast inventory used legal decks with capacity eight at level 20 and twelve at level 200. It observed prepared transactions for 14/14 selected owned actions at level 20 and 17/21 at level 200. Four high-level actions exhausted the bounded target search without finding context: 6489, 6491, 6492 and 6493. “No context” is not a native rejection or a proven defect. The audit's full eligible spell/level pairs were all committed after preparation, but no class-wide effect or client result was established.

| ID | Spell | Unlock | AP/MP/WP | Normal-cast selection |
|---:|---|---:|---:|---|
| 6463 | Llamambrada | 1 | 4/0/0 | Prepared at 20 and 200; also has the narrow 7062 / family-999 regression below. |
| 6464 | Bomba Pegajosa | 3 | 2/0/1 | Prepared at 20 and 200. |
| 6465 | Ejecución | 9 | 3/0/0 | Prepared at 20 and 200. |
| 6466 | Cruce | 15 | 2/0/0 | Prepared at 20 and 200. |
| 6467 | Perforación | 21 | 5/0/1 | Level 200 only; prepared. |
| 6468 | Metralla | 1 | 2/0/0 | Prepared at 20 and 200. |
| 6469 | Tromba | 5 | 3/0/0 | Prepared at 20 and 200; the level-200 audit rejects a corpse target, then prepares/commits a legal target. |
| 6470 | Bala Emplomada | 11 | 4/0/0 | Prepared at 20 and 200. |
| 6471 | Daga Bumerán | 17 | 3/0/0 | Prepared at 20 and 200. |
| 6472 | Púlsar | 23 | 2/0/1 | Level 200 only; prepared. |
| 6473 | Golpe Rápido | 1 | 2/0/0 | Prepared at 20 and 200. |
| 6474 | Trampa | 7 | 3/0/0 | Prepared at 20 and 200. This is not evidence for the Sram trap mechanic or a Rogue bomb lifecycle. |
| 6475 | Arcabuz | 13 | 4/0/0 | Prepared at 20 and 200. |
| 6476 | Obliteración | 25 | 4/0/1 | Level 200 only; prepared. |
| 6478 | Larga Hoja | 19 | 5/0/0 | Prepared at 20 and 200. |
| 6489 | Descargador | 90 | 3/0/0 | Level 200 target search exhausted. |
| 6490 | Patada | 3 | 1/0/1 | Prepared at 20 and 200. |
| 6491 | Evanescencia | 45 | 2/0/1 | Level 200 target search exhausted. |
| 6492 | Gancho | 30 | 0/1/1 | Level 200 target search exhausted. |
| 6493 | Imán | 60 | 0/0/2 | Level 200 target search exhausted. |
| 6494 | Fumígenos | 15 | 0/0/1 | Prepared at 20 and 200. |

The most specific class replay is breed 13, level 50, passive 7062, spell 6463. It reached production Ready, delivered the native start event, completed end/ACK/start, and exercised group-level effect 371570 (family 999) with an authoritative class actor; one requested 6463 transaction and the relevant families committed. Its report explicitly sets `full_passive_semantics_verified=false`, `full_client_verified=false`, and `attributable_completed_effect_observed=false`. It proves that bounded context and event contract only; it does not prove Tiro Sorpresa's damage bonus or a bomb chain. Evidence: `.runtime/combat-review-20261008/rogue-6463-childcontext-01.json` and its source-stable log.

At level 200, the normal inventory rejected the first 6469 target with the existing actual-corpse guard and proceeded on a second legal target. Across the whole multi-class report, 61/61 prepared selected spell/level pairs committed; its Rogue rows include 6468 and 6469. This is a bounded transaction observation, not full damage, displacement, death, or client acceptance for all 21 spells. Evidence: `.runtime/combat-review-20261008/class-normal-qifamily16-displacement-02.json`; report SHA and run scope remain inside that artifact.

No dedicated Rogue- or bomb-named test module exists under `server/tests`. Spell IDs appear in cross-class offline audits and generic shared tests, but such matches must not be presented as Rogue-specific behavior tests.

## Passives and temporary source branches

The older 339-passive optimized audit contains exactly one legal breed-13 Ready context for each of these 20 passives. All 20 reached Ready, completed an actual end/ACK/start cycle, and committed production movement. In each, its selected 6463 action prepared in 18 cases and was transaction-rejected in two (7062 and 7091); the available 6495 grant exhausted its bounded target search in all 20. These are passive-installation/lifecycle observations, not proof that any passive mechanic works. The report marks `full_passive_semantics_verified=false` and `full_client_verified=false` globally.

| ID | Passive | Unlock | Bounded observation |
|---:|---|---:|---|
| 6479 | Tymobum | 10 | Ready and turn cycle; 6463 prepared. |
| 6480 | Gran Evasión | 55 | Ready and turn cycle; 6463 prepared. |
| 6481 | Bomber Fan | 45 | Ready and turn cycle; 6463 prepared. |
| 6482 | Artificiero | 20 | Ready and turn cycle; 6463 prepared. |
| 6483 | Túnica Reforzada | 40 | Ready and turn cycle; 6463 prepared. |
| 6484 | Desminador | 75 | Ready and turn cycle; 6463 prepared. |
| 6485 | Hoja Oxidada | 70 | Ready and turn cycle; 6463 prepared. |
| 6486 | Maestro de las Hojas | 30 | Ready and turn cycle; 6463 prepared. |
| 6487 | Pared de Pólvora | 80 | Ready and turn cycle; 6463 prepared; actual wall/bomb ownership untested. |
| 6488 | Fugitivo | 25 | Ready and turn cycle; 6463 prepared. |
| 7062 | Tiro Sorpresa | 50 | Ready and turn cycle; the selected 6463 action was rejected; its claimed bonus is unverified. |
| 7063 | Barril | 65 | Ready and turn cycle; 6463 prepared. |
| 7064 | Kabúm | 85 | Ready and turn cycle; 6463 prepared. |
| 7065 | Explobomba | 15 | Ready and turn cycle; 6463 prepared. |
| 7090 | Bombas Elementales | 35 | Ready and turn cycle; 6463 prepared. |
| 7091 | Maestro Tymador | 60 | Ready and turn cycle; selected 6463 action was rejected. |
| 7092 | Jackpot | 90 | Ready and turn cycle; 6463 prepared. |
| 7982 | Táctico | 95 | Ready and turn cycle; 6463 prepared. |
| 7983 | Rastro de Pólvora | 10 | Ready and turn cycle; 6463 prepared. |
| 7984 | Bombas de Efecto Retardado | 100 | Ready and turn cycle; 6463 prepared; delayed trigger/chain untested. |

The underlying evidence is `.runtime/combat-review-20261008/class-passive-mechanic-gap-inventory-20261008.full.json` (20 breed-13 rows). It records 9–14 omitted action occurrences in each selected context. Omitted spells and source contracts remain unobserved, not failed. A second exact test, `.runtime/combat-review-20261008/rogue-6463-childcontext-01.json`, improves only the 7062 / 6463 / family-999 child-context claim.

## Granted actions, bomb profiles, books and ownership

All four extra grant trees exist in the active release and trace from the innate state 7920 via effect 357490. The four final grant effects retain the source criterion `not HasEffectWithActionId("caster", 933) and GetInstanceId() <> 862`. The native Ready audit observed all four as granted actions. It is source evidence for grant availability; it is not proof that all four become visible, can be used legally, or are removed/restored correctly.

| ID | Action | Native AP/MP/WP | Current source path / profile | Status |
|---:|---|---:|---|---|
| 6495 | Detonación | 1/0/0 | 7920 → 357490 → 368100; available in Ready fixtures. Its bounded target search was exhausted. | Grant tree present; invocation and bomb chain unverified. |
| 7904 | Ardid | 2/0/1 | 7920 → 357490 → 357495; effect tree also selects only source-qualified bomb/actor contexts. | Grant observed; action transaction prepared in sampled Ready cases; effect outcome unverified. |
| 7905 | Tymobot | 2/0/0 | 7920 → 357490 → 357507; current granted tree invokes summon family 307 for profile 1236 on a free cell. | Grant/source route present; actual actor, controller, book, turns and retirement unverified. |
| 7906 | Dinamita | 0/0/1 | 7920 → 357490 → 371288; current granted tree has family-307 alternatives for profiles 3795, 3796 and 3797 on a free cell. | Grant/source route present; bomb placement and chain behavior unverified. |

Current profile documents include all four old class-linked profile IDs:

| Profile | Current ability book | Source connection | Runtime conclusion |
|---:|---|---|---|
| 1236 | 6517, 6520, 7952, 7951; each max level 245, override −1 | 7905 summons 1236; class conditions include `HasSummonWithBreed(1236)` / `IsBreedId(...,1236)`. | Definition/book present. Ownership, action readiness, actual turns, reconnect and cleanup not verified. |
| 3795 | Empty | Direct family-307 alternatives in 7906; multiple class conditions use `IsOwnSummon` and original-controller relationships. | Definition present; bomb actor behavior/identity not verified. |
| 3796 | Empty | Same as 3795. | Definition present; bomb actor behavior/identity not verified. |
| 3797 | Empty | Same as 3795. | Definition present; bomb actor behavior/identity not verified. |

The three bomb profile IDs and their ownership predicates are current native source facts. Calling profile 1236 the Tymobot follows the 7905 action label plus its summon root; the complete user-facing actor/book connection is still not tested. Empty bomb books are not a catalog omission by themselves: tests still need to establish whether bombs should take turns, how player control is represented, and which ordinary state/action effects operate without a book.

## Resource and state inventory

The installed-client HUD contract says breed 13 uses characteristic 57 (`ROGUE_RESOURCE`) and popup state 7919. The current server's explicit `STATE_RESOURCE_RULES` in `combat_hud_resource.py` contains only breeds 8 and 11. Therefore a Rogue-specific HUD projection is **missing from that explicit adapter**. This does not by itself prove every alternate writer absent or a confirmed in-game display failure. The current native breed record also does not assign meaning to every field in its opaque `clf`/`clg` arrays; do not infer those meanings from their numbers.

The historical typed closure contains 74 unique class state references. I cross-checked those IDs against the current active `combat-state-definitions.json`: **73 definitions are present; state-reference 7986 is absent**. The same active catalog retains the exact state applicator 371126 in a granted-tree document with criterion `False`, under parent 371110 whose criterion is `(not IsOwnSummon(3795, "target") and not IsOwnSummon(3796, "target") and not IsOwnSummon(3797, "target")) and False`. Its ancestry comes from the historical class-13 closure. This is a known missing definition on a source-guarded, currently false branch; do not synthesize state 7986 or label this path a live gameplay defect. Other dynamic reachability remains unknown.

The 74 dated structural state IDs are: 756, 3434, 3495, 3656, 4464, 5563, 5564, 5627, 6527, 6620, 6876, 6877, 7916, 7917, 7918, 7919, 7920, 7921, 7923, 7927, 7928, 7934, 7935, 7936, 7937, 7942, 7980, 7981, 7982, 7983, 7984, 7985, 7986, 8022, 8025, 8026, 8027, 8028, 8033, 8034, 8035, 8037, 8040, 8041, 8042, 8049, 8050, 8051, 8052, 8053, 8054, 8057, 8093, 8172, 8173, 8174, 8303, 8414, 8415, 8433, 8892, 8893, 8894, 8896, 8907, 9304, 9305, 9307, 9310, 9311, 9315, 9331 and 9367. This is a refresh check of the prior structural set, not a regenerated 2026-10-11 class closure.

## Bomb areas, walls, timers and death order

The current active area catalog contains all seven class-linked area IDs: **781, 1333, 1335, 1809, 1810, 1811 and 1818**. All seven have native definitions and report type `GLYPH`; the older class review associates them with shared/default and class bomb/wall state branches. Existence does not establish placement shape at a target cell, owner registration, collision, trigger timing, client display or retirement.

Current source criteria give concrete links that should guide tests:

- Pared de Pólvora (6487) distinguishes owned bomb profiles 3795–3797 and its area conditions include 1333/1335.
- Bombas de Efecto Retardado (7984) references the 3795–3797 actor family, profile 1236, and areas 1809/1810/1811/1818. It also has HP/armor, native trigger-caster, active-spell, passive, owner and free-cell conditions; these should be retained exactly when constructing legal tests.
- Bombas Elementales (7090), Explobomba (7065), Jackpot (7092), Desminador (6484), and Tiro Sorpresa (7062) occur in class source gates around bomb states/trigger events. Their actual elemental conversions, caps, damage/initiative shifts and death behavior are not established by the passive Ready audit.

No scoped Rogue runtime evidence currently proves: placement and bomb-count caps; three bomb-profile spawn branches; owner/controller preservation; bomb turn policy; delayed versus immediate timers; one-shot chain ordering; resistance to duplicate callbacks; line/wall footprints and LOS; simultaneous or nested bomb deaths; replacing a bomb on an occupied cell; death retirement and cell reuse; or cleanup across turn-end, disconnect/reconnect and fight completion. Generic shared area, wall, trap, turn, summon and death tests cover reusable adapters, not these class source contracts.

## Current shared-code reuse and test boundaries

Shared code inspected includes effect dispatch, resource-cost/payment events, condition evaluation, retained effects, area creation/trigger/removal, wall and trap constructors, turn events/duration, summon books/relationships/retirement and death scripts. Historical local gates on prepared revision `3472243858e1e2fc715342a7ba70396d077344847570b2109a4f37326b7dcee5` passed 75 cost/retained/turn/Feca cases, 17 effect-dispatch cases and the 173-case broad class/NPC regression gate. Parent reports the latest gate is 182 green on active revision `548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd`, and Luna freshly passed 36/36 across seven relevant shared modules on active `548e…`. I did not execute those newer gates. They reduce risk in reusable engine contracts; none executed Rogue bombs, so they do not establish their class-specific behavior.

Adjacent existing tests include `test_combat_group_level_transmission.py` (the generic group-level contract relevant to 371570), `test_combat_effect_dispatch.py`, `test_combat_area_*`, `test_combat_wall_area.py`, `test_combat_turn_events.py`, `test_combat_turn_duration.py`, `test_combat_summon_*`, and `test_combat_death_script*`. There is no `test_combat_rogue_*` or bomb-specific module. Their generic adapter coverage should be kept in the regression set while class-owned bomb tests are added. The named 6463 source regression is in `.runtime/combat-review-20261008/rogue-6463-childcontext-01.json`; the normal transaction inventory is `.runtime/combat-review-20261008/class-normal-qifamily16-displacement-02.json`.

Reusable changes from accepted/shared class work may help only when their native contract overlaps: complete AP/MP/WP cost tables and transaction rollback; child-level/group-context propagation; effect recursion and identity guards; state/area ownership, callbacks and removal; summon identity/book/retirement; and actor-turn/death ordering. Recent Sram trap and Feca shield observations do not prove Rogue glyph/bomb behavior; Hupper resource receipt changes do not prove characteristic 57 Rogue resource synchronization. No direct class-specific behavior is inferred from another class passing.

## Estimated practical implementation (not evidence coverage)

For comparison across the six refreshed classes, this estimate uses the same weights: shared foundation 25, class core 30, passive/secondary mechanics 30, lifecycle 15. It estimates how much executable implementation is present in the current source, whether class-specific or reusable. It does **not** subtract points merely because a Rogue-specific test is missing; evidence gaps are listed separately below. This is a source review estimate (roughly ±8 points), not an acceptance percentage.

| Area | Weight | Estimate | Source-based basis |
|---|---:|---:|---|
| Shared foundation | 25 | 22 | Current tree has complete cost/payment paths, effect dispatch, areas and removal, walls/traps, retained effects, timeline/events, native summon creation/registration/books/control/retirement, and death handling. Recent shared gates were reported green on active `548e…` (182 regression cases and a fresh 36/36 seven-module Luna run); these support reusable engine completeness, not Rogue-specific correctness. Small deduction for known generic limitations and the still-missing explicit breed-13 HUD-resource adapter. |
| Rogue core mechanics | 30 | 20 | All 21 owned actions and four grants have current native routes/cost tables; 7905/7906 connect to strict family-307 construction and four current profiles; seven areas and 73/74 historical state definitions exist. Sampled transactions exist, and source routes are not missing wholesale. Deduct for four level-200 normal actions without bounded context and for no executable Rogue bomb placement/detonation wiring proof; source-specific placement/trigger linkage remains uncertain, not presumed absent. |
| Passive and secondary mechanics | 30 | 17 | All 20 passive definitions, grant trees, state/area references and the 6463/7062 child-context route are present. Generic condition/group-level/retained/area machinery exists. There is no demonstrated source-specific implementation failure for a passive from this inventory, but mechanic-to-handler coverage, class resource characteristic 57 synchronization, bomb conversion/arming, wall, delay, and grant restoration are not traced end-to-end. Missing state 7986 sits under false criteria and is not scored as a live gap. |
| Lifecycle | 15 | 9 | Shared summon owner/controller registration, timeline insertion, fresh action books, controlled actions, checkpointed retirement, KO settlement and area removal are implemented. Current Rogue profiles provide data for these paths. Rogue bomb turns, timers, chains, simultaneous/nested deaths, reconnect/fight cleanup and cell reuse have no class-specific implementation/evidence trace. |
| **Estimated practical implementation** | **100** | **68** | **Most reusable foundations and catalog wiring exist; remaining risk clusters in Rogue-specific activation, resource projection, and bomb lifecycle integration.** |

The **68/100** figure describes estimated source implementation only. It does not claim 68% manual acceptance, client correctness, or that 68% of actions have been individually proven. The exact explicit adapter omission is `STATE_RESOURCE_RULES` lacking breed 13 in `combat_hud_resource.py`; treat this as a known source gap for that adapter, not proof every alternate resource writer is absent. Missing Rogue tests are an evidence gap, not by themselves an implementation defect.

Evidence separation for this estimate:

- **Present in source:** shared transactional casts/costs; general 307 summon construction and registration; profile-based spellbooks and control; summon KO retirement; retained area construction/trigger/removal; wall geometry; event/turn duration and death handlers; current native Rogue catalogs for 21 actions, four extras, profiles, areas and states.
- **Observed for Rogue in scoped historical audits:** legal transaction preparation for 14/14 owned actions at level 20 and 17/21 at level 200; passive Ready/end-turn cycles for 20/20; four extra grants in Ready; narrow 6463/7062 child-context and 6468/6469 transaction observations. These are not spell-effect acceptance.
- **Source-specific gap:** no breed-13 entry in the explicit HUD resource projection adapter.
- **Unverified class integration:** which Rogue bomb placement/trigger routes successfully compose with shared family-307, area, wall, timer and death machinery; characteristic 57 updates in a real Rogue turn; source-specific passive effects, detonation/chains, and complete bomb/controller cleanup. There are no Rogue/bomb-specific test modules. These remain unknown unless source tracing shows an actual absent route; absence of tests alone does not lower the implementation score.

## Next verification queue

Use a small set of system-level scenarios instead of cartesian spell/passive replay:

1. Establish normal owned-book AP/MP/WP and characteristic-57 baselines; cast all 21 legal owned spells across unlock levels and record exact paid resources, target/LOS/range rejection and rollback. Resolve the four level-200 target-search no-context rows.
2. Separately exercise innate 7920 grant timing and each extra spell 6495/7904/7905/7906, including action-bar delivery, cost, failed-cast atomicity, nested use, restoration and the profile links proved by current source.
3. Create each of 3795/3796/3797 through a legal source spell, then verify owner/controller, placement, occupied-cell limits, turn eligibility, per-bomb states/book expectations, replacement and death retirement. Run 7905/profile1236 as its own controlled-actor/book lifecycle.
4. Cover areas 1333/1335/1809/1810/1811/1818/781 as selected by their actual class roots: owner attribution, footprint/collision/LOS, trigger event, charge/delay, cell reuse, removal and visual delivery.
5. Test single, chained, simultaneous and nested bomb deaths with 6487/7984/7065/7090 source gates and 6495 detonation. Assert exact once-only event order, damage/state/resource ledger, retired records, owner survival/death and rollback on unsupported children.
6. Follow one successful and one rejected fight through turn end, reconnect and fight completion; compare characteristic 57, popup 7919, summon/bomb records, active areas and visible action books with the original client.

Do not add state 7986 to satisfy the false guarded branch. Preserve its current catalog absence and source ancestry as documented until a reachable, non-false native path is demonstrated.

## Evidence and provenance links

- [Prior detailed native Rogue review](../remaining-classes-20261010/13-review.md)
- [Current class inventory index and published reconciliation](../remaining-classes-20261010/README.md)
- [Oct. 10 class route report](../class-effect-route-inventory-20261010.md) (pinned to release `a1f84e…`; route-only)
- [Historical guarded-missing-state analysis](../class-only-bulk-closure-20261007.md)
- [Native client HUD characteristic contract](../../../protocol/native-breed-hud-resources.md)
- [Current HUD projection code](../../../../server/wakfu_server/combat/combat_hud_resource.py)
- [Generic group-level contract tests](../../../../server/tests/test_combat_group_level_transmission.py)
- [Historical level-20/200 normal-cast transaction evidence](../../../../.runtime/combat-review-20261008/class-normal-qifamily16-displacement-02.json)
- [Historical 6463 / 7062 group-context evidence](../../../../.runtime/combat-review-20261008/rogue-6463-childcontext-01.json)
