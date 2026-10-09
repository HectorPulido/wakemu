# Class summon pipeline review

Scope: class-reachable creation and reactions, including Osamodas summons,
Cra beacons and other class profiles. Monster spell coverage is excluded.
The 39 static profiles, 155 creation definitions and 43 book references are
structural evidence, not an end-to-end success count. See
`class-summon-descriptors-native-review-20261007.md` for descriptor evidence.

| Pipeline stage | Current evidence and remaining acceptance gap |
| --- | --- |
| Fresh creation307 | Native descriptor level/team/resource producer and distinct actor/effect identities exist; failed native context remains guarded. |
| Property baseline | Fixed: fresh actor now owns counters. Native eZl.C sets each distinct descriptor property to one; concrete big.a subsequently increments each ID into the actor manager after initial states, preserving their writes. Property mutation side effects on summoned actors remain separately guarded. |
| Preparation rejection | Fixed: dispatcher cancellation removes the exact prepared summon runner when criteria/probability reject application. Other runner preparations and spent identities are preserved. |
| Owner/controller/carry | Registered authority separates controller, master, root and physical carry relations; actual control changes still require producers. Family325 and dynamic captured-roster control are not established by static creation. |
| Own action book | 39 profiles / 86 actions / 43 references are source-backed. Empty books do not establish passive reactions. |
| Initial innate effects/states | Bulk native exporter closes all39 `eGH.cle` arrays: six profiles have initial states. Typed producer preserves triple order, inherited level and exact `flag==0` conversion. Actual detached-actor eWu execution remains pending. |
| Cra beacon reaction | Published profiles3798/3799/3800 have empty action books but native initial states7781/7780/7779 respectively, at descriptor level, followed by1304 level10. Required proof remains initialization → incoming own-Cra attack → source-qualified event → conditional reaction geometry/damage, including attacks from another actor and wrong element. No per-profile shortcut is acceptable. |
| Actual topology | Shared QI registration exists. Acceptance must include actual occupied surfaces, area overlap, removal and rollback, rather than center-cell occupancy alone. |
| Teams and turns | Fresh team and insertion producers exist. Lifetime, retained creation, independent death/removal, controller updates and turn-order property callbacks require separate native closure. |
| AP/MP/HP | Fresh characteristic snapshot is native-derived, including zero-level cases. Fresh resources must not be copied from caster except native explicit copy branches. |
| Osa dynamic capture324/325 | Pure captured-roster component exists; persistent storage, adapter and wire integration remain unproven. Static books cannot attest a captured creature's dynamic book. |
| Client delivery/reconnect | Creation13497 and retained-runtime normalization are represented. Complete spawn/state/book replay and reconnect acceptance remain pending; packet presence alone is insufficient. |
| Transaction/lifecycle | Preparation cleanup is fixed. Retained summon creation, timeline/occupancy side effects and complete late-event/removal rollback remain explicit gaps. |

Activation predicates use current evaluated spell scope; triggering runner
critical/blocked fields have separate provenance. Current spell and source
runner spell are distinct. A beacon reaction must preserve actual owner,
trigger caster, element, state container and child-effect area provenance.

Automated verification: `test_combat_summon_preparation_cleanup` passes two
pure rejection cases. The actual native-builder property assertion is added
to `test_combat_summon`; broader descriptor/lifecycle tests are delegated to
the validation agent. No service, client, Docker or database action was taken.
Manual acceptance remains pending in `manual-system-acceptance-20261007.md`.

## Native initialization contract

The only direct native subclass of eGj in the client jar is big. Its bridge
`b(long,aBn,short,eHD,SQ,boolean,eHN)` invokes the concrete creation factory,
which calls fresh bje.aQc before controller/team registration. bje.aQc calls
big.a(eGH), consuming `cle()` as ordered short triples. Only level-1 inherits
the actor level. The third short becomes `native_rBq = (flag == 0)`.

For each row, native big constructs eWu using the new actor's PN manager and
the new actor as target, calls bbC, assigns the same actor as caster, sets
rBr through fNg and executes `a(null,false)`. This differs from an ordinary
cast304 child. Temporary summon properties are subsequently incremented into
the fresh actor property manager, then controller/team and roster registration
occur. Implementations must preserve this ordering and actual initial actor
authority; a parent-Cra caster alias would change reaction condition semantics.

`ExportClassSummonInitialStates.java` exports only the existing39 class-profile
scope. Results:3789 initializes1304/2007;3793 initializes1304;3794 initializes
1304/4230;3798/3799/3800 initialize their respective beacon state plus1304.
All other profiles have empty triples. `test_combat_summon_initial_states`
verifies39×246 descriptor-level plans and malformed signed-short inputs.

## Symbiot origin predicate

`IsSummonedFromSymbiot` reads native eHg.dTC, independently of breed or the
ordinary summon flag. eGj delegates to eGZ; actual eGz returns false when
pHM is null, otherwise reads eHD.pRO. Fresh eZl307 constructs a new descriptor
whose pRO has the JVM false default and never writes the origin setter.
Before initial states, the descriptor is not yet attached; after creation it
still has false origin. Both stages now publish the exact typed authority.
Ordinary fresh actors also have no attached summon descriptor.

Captured324 eZr calls the common creation factory first and then writes
`actor.lE(true)`, which reaches the attached descriptor's pRO setter. A
captured descriptor is a separate producer and is not represented by assigning
true to a breed or a static307 profile. `ProbeNativeSummonOrigin` checks actual
bjm/eHD null, fresh attached and true/false setter behavior: six assertions
pass offline. Constructor staging tests verify the fresh typed field and its
source provenance before and after initial-state execution.
