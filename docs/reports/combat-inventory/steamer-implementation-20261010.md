# Steamer implementation and acceptance — 2026-10-10

Work in progress. PostgreSQL revision548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd is the pinned source. This report separates native behavior, shared Wakemu policies, automated evidence and pending manual acceptance.

## Current source closure

[audit_steamer_catalog.py](../../../server/tools/audit_steamer_catalog.py) reuses the read-only common closure reader, including current native casting and nested426 documents. [steamer-catalog-inventory-20261010.json](steamer-catalog-inventory-20261010.json) resolves41 class spells,8 common passives,1316 effects,42 states,4 areas and7 derived spell references, with no missing references in its declared traversal. The initial three missing7697/7698/7699 were reader-scope omissions, not missing gameplay definitions. Constructor seed closure and removal/condition-only references require separate qualification.

[steamer-passive-branches-20261010.json](steamer-passive-branches-20261010.json) enumerates all20 passive definitions, subscriptions, cross-class deck guards and conditional casting rules. Null/display roots do not imply a passive does nothing:6930 changes Microbot casting selection;6935 modifies innate regeneration;6937/6939/6942 act through other native class trees. Native `False` branches are preserved.

## General fix under validation

Actual7008 cast failed because `microbot_path_projection` required `fight.map_id`, which the real Fight domain does not have. The authoritative map is already persisted in `native_qi_surface_provenance`. The projection now reads that map and compares the entire provenance with the current published native selected-surface record before obtaining QI/Sn projections. Missing or conflicting source remains an error. No guessed map, artificial network or native QI mutation is introduced.

Only production file changed for this fix: `server/wakfu_server/combat/combat_microbot_path.py`, SHA7ca12000e5576983752af4c8888e380fdb3ea575a7abb553d3606d6c24b3b609. Root owns complete build/deployment. Syntax and whitespace checks passed; runtime results are recorded below only after Luna reports them.

## Native contracts that must not be patched away

- Stationary turret profile2011 has PB114. It registers an actual actor/QI obstacle and owner but is deliberately excluded from the fighter timeline; no invented controllable spellbook is supplied.
- Cañonero6924 requires the caster on an owned Microbot978 or legacy area385. An empty-floor cast correctly rejects.
- Steamerator7647 and Cañonero7648 are native states. They must not be converted into a fabricated family933 morph/book replacement. State appearance/stat/property inverse delivery needs actual verification.
- Characteristic123 SP has native initial0/min0/max6, expandable with signed-int hard maximum. Conditional passives may legitimately change maximum. WP remains characteristic4.
- End regeneration1037 is a documented shared Wakemu policy backed by native descriptions/consumers; the original server emitter was not recovered.
- Native343087 subscribes1036 and removes Cañonero off own Microbots; alternate343096 handles turn/resource boundaries. No original1036 combat caller or production emitter has yet been established. Immediate leave-area semantics remain a risk to qualify, not an invented event alias.

## Automated work and evidence

|Case|State|Scope|
|---|---|---|
|Initial Ready/resources|Passed in first Luna run|Real548e Ready,WP3/SP3 and four owned grants|
|Initial7008|Passed after production fix|Actual selected-surface map provenance; owned Microbot network|
|Initial7700|Passed|Native stationary PB114,not a timeline participant|
|Initial6923/6924|Passed|6924 creates and moves onto a real owned Microbot first|
|Map/provenance guards + shared network/path/rail|Passed in Luna run|Real Fight has no map_id; actual publication identity and conflicting provenance|
|Actual cast→two-Microbot network→rail movement→recast removal|Passed in Luna follow-up4/4|No injected network; normal movement spends actualMP|
|Actual regeneration/inversion/cap and6923 inverse|Passed in Luna follow-up4/4|Four owned turn cycles,6935 comparison,form removal|
|All-active/all-passive nominal matrix|42/42 Ready; source stable|42 decks:two active chunks ×baseline+20 legal single-passive variants; no arbitrary resource inflation|

No complete-class functional claim is made while these cases are pending. The earlier refresh's70±15 estimate is a source capability estimate only.

## One manual acceptance battery

Use a legitimately leveled Steamer, preferably level200 so all20 passive choices and all21 active spells are available. No state/resource injection or invented item command is required. Run in a normal combat with enough space and a durable target; use separate fights to change the legal deck/passives.

1. **Opening and grants.** Ready with no optional class passive. Record AP/MP/WP/SP before/after. Expect the owned Microbot7008,Torreta7700,Steamerator6923 and Cañonero6924 actions,WP3/SP3 from the normal6WP opening. Action bar names/ownership must survive reconnect.
2. **Microbot and rails.** Place two Microbots in legal aligned cells with a clear short path. Walk onto the first,then three connected cells. Expect normal entry cost,then1MP for the three-cell rail segment. Recast on a Microbot to remove it; the disconnected segment must no longer provide rail cost. A rejected placement must leave AP/WP/network unchanged.
3. **Turret.** Cast7700 on a legal free cell. Expect an owned stationary turret,not an extra controllable player turn. Exercise6917 Blindaje,6918 Sobretensión,6919 Maquinaria,6920 Emboscada,6921 Transición and6922 Flujo de Stasis in their native eligible contexts. Check actual state/resource/numerical deltas. Kill/remove the turret with legal attacks and verify no obstacle ghost or timeline stall remains.
4. **Forms.** Enter6923 on SELF,verify7647 and appearance/stats,then wait for the native SP drain to remove it or respect the two-turn cast interval before toggling out;verify inverse cleanup. Attempt6924 on empty floor:expect rejection without payment. Place a Microbot,move onto it,enter6924 and verify7648/rail-only movement;toggle out and confirm ordinary movement/stats return. Test moving/displacing off the network separately; record whether removal is immediate or at the documented next boundary.
5. **Resources.** Observe four real owned turn cycles with baseline and6935 Inversión de Energía. Check WP/SP natural recovery and native cap behavior. Attempt resource-demanding actions below their real cost:expect no payment,state,position or packet mutation on rejection. Compare6933 Paciencia and6941 Conquista Serena maximum/threshold branches separately.
6. **All active elements.** In two legal deck chunks,cast6902–6916 against appropriate nearby/distant/linear targets; verify HP/armor,state applications and actual costs. Repeat representative blockedLOS,wrongalignment,out-of-range and occupied-cell cases. Do not call a no-eligible context an engine failure.
7. **All20 passives.** Equip each legal passive individually,repeat its enumerated branch in the machine-readable passive inventory,and compare baseline. Null/display roots must be judged through their cross-tree deck/casting guards. Preserve nativeFalse branches as negative cases. Test6931 with actual allies;6932/6937/7810 with actual turret context;6938/6943 with actual damage;6939/6942 with native turret/element interactions.
8. **Lifecycle.** With machines/forms active,exercise owner death,stationary-machine death,failed cast,turn ACK,reconnect,normal victory and surrender in multiplayer. Expect correct death recipient,freedQI,no duplicate effects/grants,no dead machine targeting,no stuck turn,and intact teammates/world return.

Record exact passive set,spell,target,resources before/after,state levels,turn boundary and visible result. This is a pending complete acceptance plan,not a claim of current client verification.

## October11 validation follow-up

The initial four Steamer-specific runtime methods and selected map/network/path/rail regressions passed on548e. Further tests remain delegated: two-Microbot removal respects the native two-casts-per-turn limit;6923 inverse follows actual SP-drain cycles;6935 regeneration checks the initialized expandable SP maximum rather than base6. Passive6926 affects characteristic93 separately from the raw selected casting-rule range;7745 belongs to6925 at full WP. Native turret nested7697 and full-WP6925 cases subsequently passed. These are automated results,not client acceptance claims.

### Remaining source-qualified boundaries

- Cañonero7648 has an enabled global1036 listener343087 that removes the form after leaving owned385/978. No current1036 publisher or recovered original combat caller is established. Alternate343096 listens to actual turn/resource events and can remove the same form later. This is an immediate departure timing risk, not an absent inverse lifecycle claim.
- Turret profile2011 is stationary through PB114. Its elemental reactions use owned nested abilities7697/7698/7699; an empty constructor action book does not establish missing player control. Real cast/end-turn activation is being validated separately.
- Passive6939 changes the turret's native7684 accumulation branches; checking its null display root alone is insufficient. Actual elemental/turret context reaches the owner resource branch; the corrected transient-state observation is awaiting independent rerun.
- Passive6933 passed with6935 through natural SP regeneration, with the number of turns derived from the actual initialized maximum (bounded at256). No test raises SP or changes the native maximum to make its7677 threshold reachable.

Luna follow-up gates on548e: rails/resources/SP payment4/4 and passive casting/turret nested ability/full-WP6925 3/3 passed. Logs: `.runtime/remaining-six-refresh-20261010/steamer-followup-final.log` and `steamer-extra-final.log`. Real6922 pays SP3 once; unfunded6918 rejects without checkpoint/RNG mutation. Real6923 pays SP1 upon entry,then native end-turn drain removes7647 at zero. The old HUD golden omitted the entry cost; its independent correction rerun passed. Patience6933 passed; Recirculation6939 transient-state observation remains pending.

The independently rerun legacy HUD scenario also passes on548e (`steamer-hud-frozen-rerun.log`): entering6923 from SP3 pays native SP1 and displays SP2; successive form drains display SP1 then0 while ordinary WP regeneration displays4 then5. It now asserts the actual extra-resource receipt. This corrects an obsolete no-SP-payment expectation rather than changing production payment or the native form drain.

### Concrete first-round ordering correction (validated)

Actual Patience6933 qualification exposed root395986: external1003 requires `GetFightCurrentTableTurn()==1`, then395987 (native reduction family192) costs WP2. At `combat_ready.prepare_ready`, initialization/start replay runs before `RuntimeMessages.combat_started/turn_started` publishes `native_table_turn=1`. `Fight._begin_turn` has already established `native_timeline_round=1`; the exposed table counter is still0. Before correction the real test observed WP3; with the branch executing it observes WP1, matching the native2WP reduction. The initial test expectation misclassified family192 as gain and was corrected from source. This is a shared startup-counter ordering issue, not an absent resource definition. The approved shared correction in `combat_start_events.deliver_fight_start` validates the existing first native timeline round and requires the exposed table counter to be0 or1, then publishes1 on the private preview before the existing1028/1003 replay. This is explicit Wakemu server lifecycle policy, not a recovered client callsite. No packet or event is added. Generic callback/invalid-boundary and prior-class startup/aptitude/turn regression passed88/88 with stable1760hashes; actual Patience threshold now passes; the broader prior-class gate remains pending; no assertion was weakened or counter injected into the fixture.

Patience source closure qualification: actual6933 level200 roots are395986 and343859. Characteristic maximum root343643 belongs to state7677, so it expands SPmax by the acquired state level2 only after the full-SP threshold; it does not expand the initial cap by the character level. The test follows that actual ownership and naturally reaches the original cap before observing the expansion.


### Latest scoped results

Patience6933 now passes with the actual initial WP2 reduction, natural full-SP threshold, and state7677-owned maximum expansion. The three conditional followup methods also pass: full-WP casting rules, turret specialization/armor inheritance, and dormant literal-False descendants. The actual AI turret-death integration passes with a real NPC attack, turret-only death delivery, freed registry membership, and delivery-failure rollback. These are automated results, not client manual acceptance.

Recirculation6939 reaches native applications344354 (baseline) and344355 (passive) on owner7. State7684 is a duration-zero resource-processing state whose children include its own removal344366; an empty post-execution ledger is therefore expected. The corrected test observes interpreted application levels before that cleanup; its independent rerun is pending. The 42-deck nominal matrix is currently running. No production change was required for these fixture qualifications.


### Bounded matrix completion

The active548e matrix completed42/42 initialized decks with source_stable=true:523 prepared transactions,86 no-eligible-context outcomes,441 expected owned active rows and523 grant observations. Source: `.runtime/remaining-six-refresh-20261010/steamer-normal-matrix.json`. The raw report explicitly retains `full_conditional_gameplay_verified=false`: nominal eligibility/preparation and individual passive decks do not prove every semantic branch or manual client behavior. No resource inflation or database writes were used.

Recirculation qualification: baseline304 parameters `[7684,0,0,1]` use the actual nested ability execution level; passive6939 selects `[7684,0,1,0]` fixed one. This fixture's nested ability executes at level1, so both apply transient level1 to owner7. The former baseline4 assertion incorrectly substituted owner character level200. The final test checks distinct source branch IDs and interpreted level against actual invocation level, as well as the applied carrier level; its rerun remains pending.
