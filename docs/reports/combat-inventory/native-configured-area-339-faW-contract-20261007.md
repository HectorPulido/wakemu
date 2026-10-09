# Configured area339 and native faW fake-fighter boundary

Targeted original eVi/eYQ, bcQ/faW, faV and fbm inspection plus direct original-client probes. No Python source or catalog changes were made while integrated tests were active.

## Registry and shared area creation

Native family339 is **not orientation**. eVi installs a default eYQ, described as generic area placement for wall/fakefighter/warp. Orientation is family303/eWF. Original `ProbeNativeConfiguredArea339` reports bbz=false, bbA=false, bbB=true, identical to the default eYQ used by315. Current generic eYQ creator already validates original runner/owner flags structurally; wiring339 alone would merely expose its next subtype requirement.

The audited definition174979 has parameter array [1035] at levels1/30/200. This identifies data for the investigation, not an implementation exception. Installed prototype1035 has native type15 FAKE_FIGHTER, client class bcQ extending faW, point shape, child175729, own entry masks10001/10000/10008, properties3/1, and parameters[-1,-1,0,0,1,1,1,1,6,-1]. General support must select by the native faW contract, never this reference or class spell.

## faW constructor and callback authority

faW extends faV, independently of fighter roster and faY/faZ/faN/faX subtypes. It stores orientation from actual fbm.bcy in bkU; its bcy getter uses that override, while inherited PV.baA may remain null. Fixed coordinates remain its own Qq coordinates.

faW.aQc reads its actual type parameters:

- slot0 rounded integer rMl;
- slot1 != -1 creates HP characteristic and scales its base/current using slot1+level*slot2;
- slot9 in[0,127] creates resistance characteristic; further groups of4 optionally create other characteristic records;
- slot3==1 → movement blocking rMh/bcP;
- slot4==1 → extra obstacle visibility rMi/fTq; bcO is their OR;
- slot5==1 → actual Qf/eZV in bgq; otherwise null;
- slot6==1 → own-owner callback applicability rMj;
- slot7==1 → other-target callback applicability rMk;
- slot8 int>0 supplies signed-byte height, otherwise6.

This Qf producer differs from the faV property12 bax rule. Pretending faW is faY would wrongly declare native null Qf for the audited prototype. No HP/AP records exist for slot1=-1/slot9=-1/short parameter list; native false characteristic presence must remain distinct from a fighter's zero resource.

faW.e(amP) uses PV object identity: owner target returns rMj, others rMk. faW.c(amP) returns the actual passed target's packed XYZ, null target returns null. faW.d(amP) returns singleton actual owner PV (including native null when owner absent). Generic area callback logic must preserve those exact own/other applicability and coordinate/actor result roles; it cannot reuse aura owner-entry suppression or gate's null callbacks.

## Direct original-client evidence

`ProbeNativeFakeFighterContract` clones installed1035 through bcN/faV.b(fbm), actual owner eGj and actual orientation. Output confirms bcQ/type15; Qf present; AP/HP characteristic absent; captured bcM0; movement bcP=false; visibility bcO=true; radius0; height6; owner applicability true. Its bx/guard state remains native Qq constructor state and needs the existing exact creation provenance.

A separate constructor correction was found: fbm explicitly initializes bgW=-1. Without a later M(byte) producer, cloned area bcN is -1. A prior probe using explicit M(5) verified transfer of5 but could not prove constructor0. Producers claiming `fbm.constructor` must record -1. This is obstacle identity and remains independent of captured fight affiliation bcM and actual QI registration.

## General implementation proposal

Reuse the shared eYQ339 alias and configured owner/codec behavior. Add a distinct verified FAKE_FIGHTER/faW contract across creation, local PV/Qf resolution, geometry, activation, query population and removal. Generate the faW constructor record from actual parameters, preserving optional characteristic population rather than inventing fighter HP. Qf presence comes from slot5, not property12. Owner/current target applicability uses slots6/7 and actual identity. Store native orientation separately from PV.baA and do not infer QI registration from visibility/blocking flags.

The existing geometry is adequate only for installed supported shape families. Unknown faW characteristic inheritance or owner snapshot transforms must reject unless their actual producers are present. Event mask10008 and the child effect175729 must go through the shared event runtime; support for creating a row alone is insufficient. All changes require coordination over the six shared area modules and targeted constructor/event regression tests before an integrated spell audit. No case IDs should appear in execution policy.

## General constructor correction completed

After the integrated test window closed, the common eYQ producer was corrected to record native_obstacle_id=-1 with fbm.constructor provenance. Gate regression expects19/-1. Thirteen gate/aura/affiliation tests pass and the test process exited normally. Additional direct original-client clone probes for823/2131 confirm bcN=-1 and bcO=false, so native QI.f returns without assigning a slot. No fake-fighter row or spatial membership was fabricated.

The actual registration chain was recovered: Qs.a invokes Qu.f; original fcb.f dispatches negative bcN to QI.f. That method returns for !bcO; otherwise QI.j finds the first free biQ index, stores the object and calls QK.M(slot), then bounds-checks and registers its footprint. Thus a visible/movement obstacle faW with bcO=true requires an actual complete slot population and registration producer; its final registered bcN cannot be inferred from constructor state or UID. FAKE_FIGHTER implementation remains pending this producer and the next coordinated source window.

## Explicit shared slot registry and native oracle

`combat_qi_registry.NativeQIRegistry` accepts all 127 slot entries explicitly. It never creates this population from the current fighter roster, HP, affiliation, or the list of Qs areas. Reserved objects outside the rectangle remain in the slot table without QL membership. Registration selects the first free slot before testing the anchor bounds; a positive radius outside-anchor object therefore does not gain membership merely because its square intersects the rectangle. Full capacity returns -1 without assigning another identity. The snapshot consumer supplies only explicitly indexed entries to `NativeQISnapshot`.

The helper currently implements fresh registration and identity-checked removal only. It rejects an identity mismatch as an unavailable producer rather than mutating an unrelated object. Native QI.g actually preserves the occupied slot but writes -1 to the mismatched object's own bcN; that malformed-source behavior is not exposed as successful removal. Movement, index toggles, preset-ID replacement through QI.i, ignore sets and the complete initial combat population still require their actual lifecycle producers. No existing Fight constructor or summon creator is wired to this helper yet.

`ProbeNativeQIRegistry.java` executes original QI methods with actual QK interface proxies, without loading spell catalogs. It verifies first-free 0/1, out-of-bounds reservation without membership, removal/reset/reuse, bcO=false retaining -1, and all 127 slots plus exhausted-capacity -1. The original-client probe passed. Six lightweight Python regressions passed in 0.036 seconds, including shared actor/area identity space and clipped square radius membership.

Required integration hooks are explicit: initial complete QK placement checkpoint; Qs/Qu registration and removal; summon creation using the same slots; ordinary and forced movement preserving indexed coordinates; actual death/removal releasing identity; and checkpoint serialization of the table. Capturing current positions without proving these mutation paths does not establish a complete QL population. QI.U applies aK before its W-index lookup; QI.Z has the separately proven W-only alias semantics and must not inherit this bounds policy.

## Implemented faW constructor and shared spatial lifecycle

The generic eYQ handler now accepts FAKE_FIGHTER/type15/bcQ prototypes through a separate faW constructor parser. The proven empty-characteristic path requires HP slot1=-1, resistance slot9 outside0..127 and no complete additional characteristic group. Optional PA creation or owner-copy branches remain explicit errors. Kind4 additionally requires the unimplemented timeline registration producer. These checks use constructor data, with no spell/reference exceptions.

Qf presence derives from slot5 even when property12 is absent. Native owner/other activation flags derive from slots6/7. Geometry remains ordinary Qq geometry; actual spatial obstacle radius is inherited Qq.bcL=0 independently of the area shape. The target adapter exposes the registered bcN and faW bcO/bcP. bEe remains true because faW/bcQ inherit faV's constant getter; it does not derive from HP or geometry. Captured property1 affiliation filtering is preserved.

For obstacle constructors, the explicit registration callback first receives `(fight, None, constructor)` before either UID. This validates authority and capacity without reserving an anticipated slot. After constructing the area row it receives `(fight, row, constructor)`; `row.uid` and `row.cell` identify the actual QK and position. Its result is the assigned slot. Removal releases the exact effect-area identity through the shared registry, writes bcN=-1 with QI.g provenance, and preserves the independent Qq.bhi lifecycle guard.

The registry now implements relocation and indexing toggles. Toggling off retains its reserved slot. Moving reindexes the destination even when the old membership was toggled off; an out-of-bounds destination keeps its slot without membership. A separately serialized touched-cell history preserves native QL empty byte-set entries after movement/removal rather than turning them into absent entries. Fresh initialization may begin with no touched cells; linked snapshots require the actual history. The Java original-client probe verifies these movement/toggle behaviors and preserves the empty-entry distinction. Thirty-four focused Python tests passed in0.077 seconds. No services or world process were changed.

## Summons share the same obstacle slots

`NativeSummonBuilder` previously selected a new obstacle byte from actors alone, which could reuse the byte of an actual faW obstacle. Fresh summon registration now validates the current complete registry before inserting the actor into the roster, registers its actual snapshot radius and coordinates through the same first-free QI operation, and checkpoints slots plus touched-cell history. Actual eGj bcO/bcP are true independently of summon breed affiliation. The assigned byte is captured in targeting metadata only after registration; controller/master/carry construction remains unchanged.

This occurs after the actual actor snapshot and relationship producers, during the existing fresh eZl creation path. When no QI population has been produced, the historical actor-only byte allocator is retained only for a registered area population proven to contain no spatial obstacles. An unknown area or any registered faW obstacle requires the shared population and rejects explicitly. Four focused summon/area registration regressions and eight registry regressions passed in0.036 seconds: a reserved area byte remains owned, the summon takes the next byte, unknown shared population rejects, legacy non-obstacle areas do not fabricate a QL table, and stale actor populations are not reconstructed.

## Central retention and removal verified

The shared retained-area removal dispatcher now accepts the proven faW contract. The running-effect removal codec consumes the installed configured eYQ owner metadata, validating actor/cell recipient presence against actual bbA/bbB rather than adding a special spell/reference exception. For cell delivery, eYQ field4 retains the nonzero area reference. An actor field7 is rejected for cell-only class339; class314's configured actor delivery remains supported.

A regression executes the real NativeRetainedRuntime.wrap around the faW handler, records the running effect on the caster's Qf, and removes it through the central NativeRetainedRemoval path. It verifies areaUID901 versus effectUID902, manager7, the13560 trailer `(7,902)`, retained-record cleanup and spatial slot release. Together with existing actor/cell314,315 retention and malformed removal tests,17 focused tests passed in0.014 seconds. This closes central routing and UID ownership; it does not assert client rendering or every optional faW characteristic branch.
