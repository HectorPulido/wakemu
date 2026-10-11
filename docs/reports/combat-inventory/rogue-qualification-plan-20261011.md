# Rogue (Tymador, breed13): current qualification inventory and execution plan

Scope: read-only current PostgreSQL reconciliation and code/test review. No gameplay edits, test executions, database writes, activation, or service changes were made for this inventory. The earlier estimate in `remaining-six-refresh-20261010/rogue.md` is historical; no new percentage is assigned without mechanic evidence. Exact owned roster/root IDs and the ordered test plan are in `rogue-qualification-plan-20261011.json`.

## Current authority

A direct PostgreSQL `READ ONLY` transaction on2026-10-11 found active complete release **677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d**, with7484documents. This supersedes the previous548e inventory pin. Current `spells.json` and `spell-names.json` hashes are unchanged, preserving **21owned actives,20owned passives,4grants**. The scoped query projected only indexed records named by the prior native class graph; it did not load the whole catalog or regenerate the graph.

All3042historical effect IDs are present in current complete effect records. Of74historical state IDs,73are present;7986 remains absent. These counts include global innate4464 cosmetics and must not be called class-semantic coverage. All7area IDs remain the structural test denominator:781,1333,1335,1809,1810,1811,1818. Profiles1236,3795,3796,3797 remain source-backed.

The current summon-abilities document hash is `c3fec45b34c4ecc8c7169cc087a68348045998eb0492d93cbf23b82530ce84ee`; its four actual profile records were read again, rather than assuming an old document hash proves their content:

| Profile | Actual book | Native initial PB properties | Implication for tests |
|---:|---|---|---|
|1236|6517,6520,7952,7951; raw castingUIDs equal refs, max245, override−1|15,69,54|Actual7905 creation, controlled turn/book/payment/reconnect need execution.|
|3795/3796/3797|Empty|54,114,15,1,47|Empty book is intentional. PB114 excludes these bombs from ordinary timeline insertion; do not manufacture bomb turns or abilities.|

No native initial state triples are listed for these profiles. Additional states must come from actual summon-source child effects, not fixture injection.

## Concrete gaps versus unverified behavior

1. **Proven explicit-adapter omission, not yet a proven client incident:** `combat_hud_resource.py:11` maps only breeds8/11. Native Rogue HUD uses characteristic57 and popup state7919. Current7919 has only child370126 (family400), so it does not directly write characteristic57. Enabled acquisition/consumption exists in source (for example415991–415993,419073–419075 apply7919, while419071/419077 remove it). An actual fresh Rogue action must compare state7919 and stat57 before proposing a narrow source-qualified projection. No universal popup-to-characteristic rule is authorized by the data.
2. **Dormant data absence:** missing7986 is applied by371126 with literal `False`, under371110 whose criterion also contains `False`. Preserve this branch as dormant; do not synthesize7986 or treat it as a live defect.
3. **Unverified class integration:** no dedicated Rogue/bomb runtime test module exists. Source/handler presence and old normal-cast preparation are insufficient to claim bomb placement, detonation, delayed chains, passives, walls, resource caps or reconnect correct. No new runtime failure was reproduced during this inventory.
4. **Intrinsic event producers are already wired:** innate398440 listens on local2289/2290. Current class records include62intrinsic producers with those IDs in target_masks[6]: family304 Powder applications produce2289; family321 removals produce2290. `combat_state_handler.py:224` and `combat_state_decurse.py:67` dynamically forward these mask IDs into lifecycle phases. A missing literal2289/2290 source string is not a missing publisher.

Recent source corrections are relevant but are not Rogue acceptance: deferred family321/eZi registration (`combat_subscription_runners.py:24`), fresh own-Qq selection (`combat_effect_resolver.py:257`), Qj replay reentrancy and fresh activation ancestry, actual first-round counter initialization, live summon PB properties, summon flag serialization, and actual death1013 channel6. Each needs Rogue source-owned execution to establish class behavior.

## Exact source routes for first fixtures

Innate7920 contains357490, which grants the following actions via class649:

| Action | Grant effect | Native baseline cost | First meaningful positive / negative |
|---:|---:|---|---|
|6495 Detonation|368100|1AP|Own actual bomb / ordinary actor or foreign bomb; assert real chain and once-only cleanup.|
|7904 Ardid|357495|2AP1WP|Actual qualified bomb relationship / unqualified target, atomic rejection.|
|7905 Tymobot|357507|2AP|Actual free-cell1236 creation / duplicate or occupied cell; inspect true controller/book.|
|7906 Dynamite|371288|1WP|Actual native alternative3795/3796/3797 / unavailable Powder or occupied cell; no forced branch.|

All four grants preserve the native no-morph933 and instance≠862 criteria. Innate370123 listens on1005 and recomputes Powder according to6486/7063 and actual7923 counts. Innate415964 listens on1024 only for source elements1/3/4. Its positive fixture must use a legitimate elemental action and retain the original trigger context. The old level200 target search found no usable context for6489,6491,6492,6493; actual owned bombs should supply the missing prerequisites before diagnosing rejection as a bug.

## Execution queue

1. Add a dedicated actual Rogue fixture using `SpellTransactionTests.native_server_fixture(13,200,native_qi=True)` with a valid ordinary deck, fresh owned stats, actual innates7920/4464, actual first1001, and real grant UID resolution. Cover all20passive Ready configurations as initialization evidence only. No state, HP, resources, books, bomb actors, areas or RNG outcomes may be injected.
2. Establish Powder through legitimate actual casts/movement, compare baseline versus6486 and7063, and assert native acquisition/cap/consumption/2289/2290. Compare stat57 with7919 and the native stats wire. This is the first candidate general implementation gap.
3. Execute7905 and each reachable7906 alternative. Assert source profile, actual owner/controller, PB54/114, QI slot, actor payload summon flag, book, placement and duplicate/occupied-cell rollback. Bombs remain outside the native timeline; Tymobot receives its true controlled turn.
4. Exercise21owned actives and the4grants against their genuine contexts, with exact damage/state/position/resource effects and negative atomicity. Separate simple elemental actions from own-bomb manipulation and weapon/turn prerequisites.
5. Add source-derived positive/negative tests for all20passives, grouped by actual event and dependency: Powder/blades, bomb element/conversion, detonation/delay, armor/escape, wall/area, damage modifiers. Compare child effects/recipients and numerical formulas with unequipped controls; Ready alone is never semantic PASS.
6. Follow single, chained and simultaneous bomb deaths through1010/1013, actual QI retirement, area removal, next actor/ACK and cell reuse. Cover own and foreign targets, delayed timer expiry, no double callback, owner death and rejection rollback.
7. Checkpoint JSON and owned reconnect preserve actual UID, current stats, books, Powder, bomb states/areas and timeline without executing spells again. Complete/abandon cleanup and reward idempotency follow the shared production policy.
8. Delegate execution serially to existing Luna, then run the final18class shared gate against one frozen current source/revision. Prepare a complete manual Rogue battery only after these automatic prerequisites pass.

Existing shared regression modules to retain include `test_combat_effect_resolver`, `test_combat_subscription_runners`, `test_combat_group_level_transmission`, `test_combat_wall_area`, `test_combat_summon`, `test_combat_summon_slot_reuse`, `test_combat_death_events`, `test_combat_runtime_messages`, and owned reconnect/QI/area modules. These cover reusable contracts; they do not substitute for the dedicated Rogue scenarios above.
