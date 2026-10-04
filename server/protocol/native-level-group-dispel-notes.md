# Native level groups999 and dispel421

Offline eVi registry:999=eYm extends eYg;421=eXe extends eZR. Current spell-effect trees contain68 definitions999 (51 with8 parameters;17 with10) and168 definitions421 (all1 parameter). Class inventory's120/107 related spells are dependency counts, not definition counts.

## Executable class999 interface

`combat_level_group.level_group_override(effect,level,actor_level)` is the integration hook. `NativeLevelGroupHandler(execute_child,actor_level,actor_position,group_cells)` wraps the existing verified ordered-group helper. `execute_child` must call the same dispatcher without replacing its active ancestry; callbacks must reference the same transaction preview. It retains base/state UIDs, transforms child levels and applies inherited target/cell, rebind, transmission and success-limit policies. This module does not register handlers in the factory or change the main server.

Javap eYm.C: inherited parameters0..5 are eYg group controls. Parameter6==1 selects caster, otherwise target;7 is evaluated integer ratio percent. With8 parameters the linear pair defaults0/1. With10 parameters,8/9 are native floating `eVn.w` base/growth evaluated at the parent level. eYg.c calls fPP actor rebind before eYm.d, so the level source is selected after rebinding. eYm.d reads eGj.cmZ, multiplies level*ratio with Java int overflow, divides100 truncating toward zero, computes floor(float32(base+float32(growth*scaled))) and stores eVt.SP. eZR.fRR treats override-1 as absent; other overrides cast to signed short. Native eVE.w snaps the growth term near integral floats before adding base.

ProbeNativeLevelGroup.java runs the actual native eYm.d method with an eGj test actor whose only meaningful method is cmZ. Constructors are bypassed to avoid unrelated client infrastructure; no live client/server is started. Probe examples:actor200/ratio100/base6.25/growth.75 ->156;actor101/ratio33/base0/growth-.1 ->-4;actor-101/ratio33/base6.25/growth.75 ->-19. Overflow32767*2147483647 produces override21474508 (signed short-21300). These are native outputs, not an independent recreation of the formula.

Real definitions368107/379594/379596 have tested transformations. Definition379594 at parentlevel10/actor200 yields249, because the native float .12*10 is below1.2; rounding to250 would be wrong. Relative probability, unknown flags, delayed execution and negative signed child levels reject before calls. Actor levels must be authoritative eGj.cmZ snapshots; missing actors/non-eGj fallback is not inferred. Parent/child execution status behavior follows the existing group adapter contract.

## Class421 audit; registration pending

Native eXe.c begins mu(true), snapshots eligible running effects from target.bax(), then for each selected effect calls ms(true) and Qf.q(effect). It does not edit numeric stats directly; native owned-effect removal machinery does the reversal. Parameter counts:0=default dispel;1 matches definition eVn.aZE (AGT generic effect ID);exactly2 matches PK.awM (action class) usingparameter0, ignoringparameter1. Other counts still use generic-ID comparison. Exact requested identity matches are added BEFORE E eligibility/protection checks, including class421 itself.

For default selection E rejects type2 definitions whose eVv.cxq isfalse; rejects eZk state when fyW.guN istrue or fyW.cxq isfalse; rejects missing container. Container types1/3 accept;type11 accepts except fyG whose spell fyF.elO istrue;other types reject. Default selection additionally excludes eVi.rvF, confirmed native registry class421 by the Java probe. Generic ID0 is not a request to remove all: only no parameters sets the native MIN_INT sentinel for default dispel.

Current owned-stat/state ledgers do not expose complete ordered target.bax entries, definition type/cxq, container metadata or spell elO for all retained effects. A handler that equates generic IDs with state IDs, removes every state, or silently skips unrepresented retained effects would be incorrect. Class421 is implemented below with an explicit complete-view contract; automatic registration remains pending. Integration requires an authoritative running-effect view and callbacks to reverse every selected effect within the same preview before emitting removal packets.


## Extensible retained-effect view and native421 handler

`combat_retained_effects.NativeRetainedEffectView(fight, entries, population_verified_complete=True)` consumes a complete authoritative ordered snapshot. The boolean is an explicit caller attestation; it cannot be derived from the currently implemented stat/carrier ledgers. Every existing owned stat and state carrier must appear exactly once, agree with original payload/generic/class/owner identities, and retain its parent link. Additional retained families must also appear. Missing known effects, orphan carriers, duplicate UIDs and inconsistent ownership reject. Order is supplied by the authority rather than inferred by sorting UIDs.

`RetainedEffect` records identity and default-dispel metadata: native PK.aZD, eVv.cxq, explicit container presence/type/actual fyG classification and fyF.elO, state fyW.guN/cxq. Missing default-selection metadata rejects; exact generic/action matching intentionally does not consult these protection fields, matching the native early-match branch. A state ID is never substituted for the carrier's generic definition ID(-1 for current standalone310 payloads).

`NativeRetainedRemoval(view).register(effect_class, exists=..., remove=..., validate=...)` is the common removal contract for dispel, timers and state replacement. All callbacks belong to the same preview. It preflights every requested UID, family and recursively owned child before the first mutation. Child removal precedes owner removal, including new families registered later. Unknown families reject rather than discard retained children. Callback failure requires discarding the transaction preview/private outbox. `register_owned_removals` binds existing NativeStatHandler.remove and310 carrier cleanup; it preserves native13560 payload identities and stat reversal of actual deltas. The view is a per-operation snapshot, not a new automatically persisted source of truth.

`combat_dispel.NativeDispelHandler(view_provider=..., removal_provider=...)` implements class421 without factory/dispatcher changes. Providers rebuild the view from the live transaction preview on each call. Default selection uses all native guards; one parameter matches generic AGT identity; two match action class. No match still returns successful execution, reflecting eXe.c's unconditional initial mu(true). Flags/delayed timing remain explicit guards. The family registry provides a reuse point for timers and state removal, but their existing implementations were not edited.

ProbeNativeDispel.java runs actual native eXe.E and eXe.c with a Qf test manager that records removal calls. Ten cxq/container cases and four selection cases match the Python implementation. Protected generic123/action400 is removed by requested123 or[400,999], but not default or requested456. The second action-mode parameter is unused natively. Tests:8 new dispel tests plus5 state-child and5 timed-expiration tests pass (18 total). They cover restoration before carrier removal, unknown owned-child family rejection before mutation, registration of a new family, explicit completeness omissions, targeted child retention of its owner, empty-match success, failed later transaction preserving original state/stat values, and real native308272 removal of owned308267/class400 via13560.

Coverage constraint: among168 current class421 definitions, targeted definitions are66 class330 groups,21 class400 indicators,8 class1020,4 class447,4 class39,4 class315,2 each876/877,1 each72/999, and55 references absent from the spell-tree dictionary. Those may belong to other catalogs. A stat/carrier-only runtime cannot attest completeness for these families or supply missing group/container metadata. Such casts must reject until the owning families are represented in the authoritative view and registered removal machinery. No main/factory/dispatcher changes or restarts were performed.

## Central runtime registration (updated integration)

`combat_retained_runtime.NativeRetainedRuntime` now owns the ordered retained population on the transaction preview. Explicit Fight fields preserve group payloads, metadata, insertion order and tracking through checkpoints. The factory registers executed stat effects, native310 carriers and330/844/999 groups;421 consumes that complete tracked view. Unknown retained families or a prior untracked history reject. The initial empty server ledger proves coverage of server-owned effects; client innatas and deck subscriptions must be installed before claiming correspondence with the full client population.

`ExportRetainedEffectMetadata.java` exports178337 native definitions plus actual spell protection and state removal flags. Catalog identity is checked against native class, variant, level bounds, parameters and execution mode. Two independent canonical exports have SHA256 `d0583a0330e4ca16d55ce86fb07da52c40851d010b3bf53947f8b01d6e4f72e9`.

Native Qf preserves insertion order: group children execute before parent registration, although the parent UID is allocated first. eYg.bbR does not reverse separately executed children. Subscription registration checks Qa.aZN masks0/1/3/4/5, skips conditions/probability/children and retains the group itself. Event replay remains rejected until explicit activation context and native suppression rules are provided. Removal-only mask2, delayed effects and unsupported retained families remain guarded.

`ProbeNativeRetainedGroups.java` executes real eYg/eYr/eYm serializers. The shared running-effect protobuf contains UID, base UID, generic definition, cell, caster, target, original container kind/identity and native TimeDatas. Child context keeps incoming base/state identity, with raw native844/999 level override. Native eWu child context is exactly `0801100020ffffffffffffffffff0128013000380040004800`; its fLN flag bypasses probability. Manager ownership is recorded separately from payload target and drives13560 outer actor identity.

Timed expiry removes owned groups and central records in native insertion order. State replacement removes owned stat/group effects before its carrier. Group removal preserves independently owned executed children. All mutations and packets stay on the preview and roll back with it.

For direct innatas, the factory exposes `dispatcher.native_state_handler` and `dispatcher.native_retention`. `open_state(invocation)` / `close_state(invocation)` wrap direct `apply_reference`; `apply_state_reference` provides the same scoped operation. `plan.native_retained_container` declares native container presence explicitly, permitting a proven null parent container. State children use their actual fyW container. Individual running-state protection overrides catalog defaults. This path creates no synthetic304 definition.

Validation after direct-state hooks:28 functional tests passed (retained groups9, dispel8, state handler6 and timed expiration5); the new explicit native state-context probability test also passed. State-child removal/checkpoint rerun passed9 of10; the remaining checkpoint fixture expired its session while loading the catalog and raised `Fight checkpoint session is stale`, rather than failing snapshot assertions. The retained-group checkpoint test passed. The separate old command's nonexistent `test_combat_checkpoint` module was an invocation mistake; the correct module is `test_fight_checkpoint_store`. Java native serializer/context probe and Python compilation passed. No server entry or service restart was performed during this update.

## Native event selection and flag1 audit

`combat_native_events.subscription_selection` implements eZX.b plus Qi.a/b mask selection without executing events. Ordinary channels1/2/3/4/5/6 select masks0/1/3/2/4/5. Reversed-subscription channels10/20/30/40/60 and global channels11/21/31/41/61 select0/1/3/2/5. Mask2 queues removal. Source self/parent, source suppression, all-event suppression and level-one suppression are explicit inputs. Flags1 bypasses only the last guard.

The jar-wide constant-reference audit finds eVl.rwy only in its enum and eZX. Its native name is ALWAYS_TRIGGER_LEVEL_1. eZX checks this flag on the retained listener when the source aZB() would suppress level-one reactions. Registration performs no such selection; flags1 is consequently admitted for groups while unknown flags remain blocked. `ProbeNativeEventDispatch.java` executes native eZX and Qf: ordinary listeners fire for ordinary sources, skip level-one-suppressing sources, and listeners with flag1 fire in both cases. Four isolated Python tests match this matrix and check remaining suppression/channel guards.

Qe.bbw() emits the union of native PK.aZO (the seventh exported mask) and the running effect's dynamic bfA set. These are event IDs supplied by the definition and actual runtime, not target categories. Qe.k clones the listener, uses retained UID as base UID, marks bfM via j()/bbL(), and rebinds target using native aZw/aZy/aZz. Correct replay still requires those native booleans, event source identities/runtime flags, dynamic event production, clone conditions/probability and suppression of retained re-registration. No guessed event1028 or direct activation has been introduced.

Event rebinding correction: group runners inherit eZR.l/m overrides, so the Qe base aZw/aZy/aZz rebinding described above is not their replay contract. `ProbeNativeEventTargets.java` runs actual overrides. Native Qd/aZV target codes0/1 keep original target,2 use the manager's carrier actor,3 use original caster,4 use triggering caster,5 use triggering target. Qb/aZW caster codes0/1 keep original caster,2 use manager carrier,3 use original target,4 use triggering caster,5 use triggering target. Null Qb also keeps original caster. `subscription_actor_ids` matches all12 probe cases; event helper suite5 tests passes.

The retained metadata exporter now includes these codes and actual global/reversed subscription flags for all178337 definitions. Two regenerated canonical exports match SHA256 `2fe6d64b61c4bba8d444f8e0289158a73576224bada9256f7dcbf859da7e9516`, superseding the earlier export hash. Real innate listener416581 has carrier/carrier actors and ordinary subscription;416965 has carrier/carrier actors and global subscription;316982 has carrier/carrier actors and ordinary subscription. Source event IDs, dynamic bfA generation, Qj reentrancy history and event clone criteria remain necessary before enabling live replay.

Factory now binds native1065 AP-category modifications and common1047 HP-level groups. The latter shares child ordering, level override context, subscription registration and retained removal with330/844/999. Native999 callback explicitly receives active-fight context for flags1/17. Four isolated AP-cost tests and five event-selection tests passed;1047 helper's five tests were verified by its owning agent. No large concurrent test suite was launched.

Queued activation order is distinct from retained insertion/removal order: native eZY sorts by PK.aZM priority descending, generic effect ID ascending, then running UID ascending. `activation_order_key` and `ProbeNativeEventOrder.java` match `[902,903,904,901]` for the priority/tie matrix. Event metadata now additionally exports `event_priority`; final two reproducible exports match SHA256 `934498f04ddda814941a9457b4d3d2eaf12b774dd59a0cd86273f17533d267e9`. Event helper suite is now6 tests, all passed.

Executable event replay and source identity (2026-10-03): `combat_event_replay`
now activates retained groups from verified real running-effect deliveries. It
uses native Qf recipient channels, native ordering/rebinding and active Qj
triples; clone criteria/probability precede transient UID allocation. Activation
runs children without registering the listener clone. Fresh running effects
encode baseUID=selfUID; event clones preserve baseUID=listenerUID, while a
state-owned child's stateUID remains separate. `ProbeNativeEffectUIDs` exercises
actual Qe.k and verifies fresh901/base901 then clone902/base901.

A compact reproducible native fixture contains healing source152544 and actual
retained308265 ->308266 ->400308267, including the HasEffectWithSpecificId
criterion. Eight replay tests cover activation, finite listener exhaustion,
recipient/suppression, active-history release, callback delivery and mismatched
source UID rejection. NativeHealingHandler emits its event callback only after
applying HP/virtualHP/resistance and appending12613; callback exceptions propagate
so the caller discards the private preview/outbox. Factory accepts an explicit
NativeHealingEventAuthority to bind this automatic callback. Delivery authority
must still establish Qf routes, bfQ/PK.aZB, dynamic events and clone corpse/baK
context; an absent authority does not claim automatic lifecycle-event coverage.
Twenty-one focused healing/replay/1020 tests pass. Real1020=eYw uses the actual
trigger-source value, float32 ratio and Java truncation;913=eYn remains distinct.

Event-production audit follow-up: `Qe.dr(byte...)` delivers Qf channels by
calling `L(byte)`; it does not remove event IDs. `Qe.k` delivers channels1/2
before clone execution, and `Qe.a` delivers3/4 after execution. `eZR.L` also
routes globals11/21/31/41 through PN.bab().m(caster). The current healing callback
is a post-application hook and does not yet cover this entire pre/post lifecycle.
Listener execution depletion now follows Qe.bbj loading PK.aZS into bfB and
Qe.k calling listener.aX(true) after accepted clone execution. Persisted group
execution_count decrements after guard/RNG acceptance even when children return
false; zero removes the retained listener. Unknown legacy counts reject replay.
Actual308265 has count1 and therefore disappears after its first accepted clone.

The retained metadata exporter now includes PK.aZB as
`event_suppresses_level_one`: all178337 definitions currently returnfalse. All
previous metadata fields were compared for equality before atomic replacement.
SHA256968551a7722f44d8d9bdd49605ab01d8ae57f8d3115655edf25cbf0e19314feb.

Metadata additionally exports PK.aZS as event_execution_count. Subscribed
definitions:6957 unlimited(-1),1994 count1,10 count0,14 count2..6. Current SHA256
695eddd0b247d4470c35fa2396bee4a6d1518d45f0da7118209f412c4c612255.

Ordinary healing production is now automatic (2026-10-03). Adapter.contexts binds
OrdinaryHealingEvents for exact OrdinaryActorAuthority creation contexts, and the
factory binds it to the same preview/retention/dispatcher. Dispatcher preparation
allocates the fresh source UID, delivers L1 with initial value0, and calculates
native eXs.C before criteria/probability. Accepted applications deliver L2 with
requested amount before consumption, append12613 after HP/virtualHP/resistance,
then deliver L3/L4 with actual consumed amount. Local caster/target deliveries
remain ordered10/1,20/2,30/3,40/4. Newly installed global listeners are inspected
AFTER local reactions, matching eZR.L. PK.aZB metadata and exact fresh registry
bfQ/bfA path replace optional manually invented suppression values.

ProbeNativeHealingPhases executes actual Qe.d/eZR.n/bbJ/eZR.a/Qe.a with explicit
arithmetic fixtures, verifying values0/42/7 and channel sequence10/1/20/2/30/3/40/4.
Six ordinary production tests plus healing/replay total22PASS, including factory
automatic wiring and actual source152544→listener308265→child308267. eXs.bbw returns
an empty event BitSet for undead property20 even with flag33; production now
respects that native behavior. Original-listener target baG and rebound-target
baK guards require alive ordinary authority; post-death flags are rejected,
not inferred from HP. Global delivery to multiple relevant managers requires an
audited native_event_actor_order; it is not replaced by dict/insertion/initiative
order. Non-group subscribed runners, eVt.aZi callbacks and other producer families
remain explicit coverage gaps. Global phase actor iterator's membership/order
fcb.m/fcd must be exported before removing the multiple-manager guard.

### Native event producer and cost groups (2026-10-03)

Ordinary eXt damage and eXs healing now emit native phases 1/2/3/4 on the same preview, including reversed caster and target channels. Damage phase 2 carries calculated damage before consumption; phases 3/4 retain the native blocked value. Block probability is drawn after damage arithmetic. BACK event 29 is independent of the arithmetic localization option. The retained source UID, fresh self base UID, and listener clone base UID remain distinct. Forty-three focused damage/healing/replay/parameter-maximum tests passed.

The null target selector uses the caster XY as area origin (native amQ.a/anc.a/amX.a), while fcE area selection retains its target-cell origin. A regression test moves the caster and target cell independently; targets plus replay: 21 tests passed.

Groups 910/eYv and 912/eYt now use the shared group registration, retention and dynamic-level callback. NativeEventSource carries an optional cost_source snapshot. Ordinary damage/healing sources attest runner_class=other, allowing the exact 912 SP=-1 path. Group 910 still requires an authoritative live fyF spell_context/cost snapshot and rejects unknown context; paid action costs are not substituted. Cost/repeat helpers, ordinary producers and replay: 22 focused tests passed.

Remaining event coverage: generic non-group subscriptions (including eXE400) need the native original-listener payload and clone notification path; 949/eXL needs PT-created and accepted-application counts, separate from boolean child success. Group clone lifecycle events, authoritative multi-manager native iteration order, post-death native actor buckets and collision synthetic sources remain explicit pending contracts. No production entrypoint or service restart was changed.

### Non-group eXE400 subscriptions and relative callback

The central retained registry now stores eXE400 listeners alongside retained groups with explicit effect_class=400, using the common UID/owner/timer/removal record. This is storage reuse, not an eYg mode interpretation: registration skips eXE.C, criteria and probability exactly as Qe.d(Collection) does for aZN. The original payload carries constructor execution status -1 and executed=false. Event copies allocate one fresh UID, retain the listener UID as base, calculate eXE.C when accepted, preserve the original container/clocks/context and rebound actor IDs, and never enter owned_stat_effects (Qe.k/bbL => Ty=false). eXE.bcd=true bypasses both corpse guards. The clone emits lifecycle events0 plus aZO using the ordinary event authority. Removal class400 routes both registered listeners and already executed stat markers; no family collision is ignored.

The real Impacto Felino5249 definition359836 is included in the reproducible native-event fixture. Its subscription is event1002 on reversed channel60, unlimited count-1. Registration, exact clone UID/base, no retained clone, and mixed class400 removal pass in the 10-test replay suite. The delivery fixture supplies this actual event explicitly; this does not claim that the server already produces event1002. The current emitter covers damage/healing lifecycle events only.

ProbeNativeNullListener exercises native eXE/Qe.k and decodes Python original/clone payloads with eXE.ds: UID901/base901/status-1/unexecuted original; UID902/base901/status-1/executed clone. Probe passed, including preserved fyG container. Expected native logs report absent actor context in this offline decode fixture; no connection or official runtime is used. The probe accepts two payload file paths for reproducibility.

Relative groups have an explicit dispatcher relative_group_children(effect,values,invocation,children) hook, with factory callback adding preview/plan. The hook owns native candidate eligibility and integer/fraction RNG and returns native child IDs. Child eVt context carries a(true,false), bypassing the ordinary second probability draw. One focused hook test passes; real relative provider remains separate work and no weighted-choice behavior is substituted.

Validation observed: 37 focused replay/stat/dispatcher/ordinary event tests passed before the added mixed-removal case; replay10 and relative-hook1 passed afterward. Factory/dispatcher/retention sources were then frozen for the active-spell audit. Generic subscribed families beyond400/eYg families, repeat949 PTcreation, and group clone lifecycle events remain pending.
