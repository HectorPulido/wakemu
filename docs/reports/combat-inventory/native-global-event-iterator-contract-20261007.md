# Shared global event delivery: native iterator contract

This audit concerns class damage, healing, resource, state and maximum-resource
reactions sharing `OrdinaryHealingEvents.phase`. It does not certify an entire
class or infer external event producers. No services, DB or AI were touched.

## Native evidence

Installed `wakfu-client.jar` SHA-256:
`e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`.
Reproduce with `javap -classpath 'client/lib/*' -p -c CLASS` for `fcb`,
`fbX`, `Qs`, `fcd` and `ayT`.

* `fcb.m(amP)` yields the actual caster alone in `fbZ.rRo` when that caster
  implements PV. This bypasses `fcd` membership filtering. Other contexts use
  `bak()`, which constructs `fcd`.
* `fcb.fVh` concatenates the `dLy()` fighter iterator, a copied `Qs.bdm()`
  area collection when nonempty, then `fUn()` extra registrations. `ayT`
  exhausts each segment before advancing to the next. It does not sort or
  deduplicate.
* `dLy()` uses `fdt.a` with the installed `fdD.fYb/fYd` filter. It is not a
  promise that every Python roster actor belongs to this native collection.
* `Qs.bdm()` exposes Trove `bhs.valueCollection()`, distinct from
  `Qs.bdj()`'s Java HashMap `bhr.values()`. Area insertion order or UID sorting
  does not prove its native order. `fbX.fUn()` copies Trove `rRc.values` into
  an array, so this order also needs its actual collection provenance.
* `fcd.v` accepts an eligible eGj under native `fdx.sax/say`, OR a current
  `Qs.do(Sn)` registration, OR current `fbX.rf(Sn)` registration. Membership
  is evaluated while advancing the iterator, after preceding reactions. A
  manager removed during a reaction can therefore be skipped subsequently.
  Qf presence is not this predicate; it matters during PV delivery.

`ProbeNativeGlobalPVIterator.java` executed the installed `ayT` and Trove
classes offline successfully. Native concatenation returned
`[9, 2, -4, -1, 9]`, preserving the repeated PV. Inserting those five distinct
IDs into a fresh default Trove map returned `[9, 8, -4, 2, -1]`; removing `2`
and adding `20` returned `[20, 9, 8, -4, -1]`. This directly contradicts
insertion-order reconstruction. This probe covers collection composition,
not the actual fighter-status or area-registration filters.

`fdt.a(fdD...)` builds its fighter list through `saq.forEachValue(fdv)`;
`saq` is another fresh default Trove map. An exact shared Trove collection
producer can therefore support all three segments, provided its insert,
remove, capacity and rehash history is recorded at the actual lifecycle
boundaries. Merely replaying the final set of keys loses that provenance.

## Closed modular contract and integration gap

`combat_global_event_iterator.py` now expresses segment concatenation,
duplicate preservation, lazy membership and caster-only bypass. Its six
pure tests cover reaction-time removal, mixed actor/area order, duplicate PV,
unknown authority and the distinct caster-only path. It requires captured
orders and a real membership callback; it invents neither.

The next modular layer is implemented in `combat_trove_long_map.py` and
`combat_global_pv_collections.py`. The installed default constructor export
records capacity 23, load/auto-compaction factors 0.5, initial compaction
counter 10, and the actual `PrimeFinder` capacity table. The map preserves
native hashing, double probing, removed slots, descending-slot rehash,
growth and auto-compaction in plain checkpoint state. The collection producer
offers fresh initialization, actual fighter/area registration, area removal
and explicit fighter-registry status transitions. It cannot initialize a
legacy restored roster automatically.

`ExportNativeTroveLongMap.java` additionally produced 1,200 deterministic
native operation snapshots, including signed-long keys, replacement,
removal, growth and compaction. The offline oracle is stored under
`.runtime/combat-review-20261007/global-pv-iterator/`. The updated verifier
compared all 1,200 operations and five fields with zero mismatches, stable
tracked sources and matching installed client/Trove JAR hashes. Evidence:
`native-trove-global-iterator-oracle-20261007.json`. The additional unit and
integration suites are pending coordinated validation; the native differential
does not establish all class synergies or GUI behavior.

The fresh producer is now wired into bootstrap, registered summon creation,
actual Qs area registration/unregistration, and the owned lethal-damage
OFF_PLAY transition. The shared lifecycle consumes it after local delivery,
visiting actual eligible PVs in native order and reading subscriptions at each
delivery. A null-Qf area receives no Qf replay. Missing legacy topology still
uses the old guarded path; it is not reconstructed from a restored roster.
The old path collects matching managers into a set, rejects multiple matching
areas, and requires `native_event_actor_order` for multiple fighters. No
production producer of that old field was found. A single matching listener
does not establish class-wide event completeness.

The participant order is proved through the actual installed cvb12847 handler:
`buK.b(cvb)` builds per-team `buL` lists from packet participants, with
`buL.e` inserting each leader at index 0 and `buL.d` appending other members.
`buK.a(cvb,buL)` registers team 0 then team 1 through
`fcb.a(byte,Collection,false)`, consuming list order into fdt. Current own
bootstrap serializes one PC followed by NPCs, with that PC and the first NPC
as leaders. Its registration order therefore matches this source exactly.
This statement does not generalize to an arbitrary differently grouped
participant packet or leaders inserted elsewhere.

The new integration avoids filtering the whole global iterator to a cached
set of currently relevant listeners. Native delivery visits eligible PVs;
earlier reactions can change subscriptions and membership before a later PV
receives the same source. The runtime should evaluate those facts at the
actual delivery point. Fighter collection mutation and iterator failure
semantics require a separate native probe before extrapolating this helper's
captured tuple model to arbitrary roster creation/removal during replay.

The producer preserves actual fighter filter/order, Trove area order and
live registration membership across checkpoint and restore. Its extra-PV
map is authoritatively empty at the fresh fbX constructor; later extra-PV
creation remains outside this implemented source path. Actual fdt.bx map
removal has a separate API and is not inferred from a corpse or generic summon
retirement. The fresh mode is rRm; the distinct rRo caster-only mode requires
an explicit native cleanup transition. Replacing these facts with initiative,
insertion order, sorted IDs or a set would implement different class synergies
even if narrow tests passed.

## Live fighter status binding

The producer's explicit fdy state now supplies `baF`, `baG` and `baK` for
ordinary actors and registered summons. IN_PLAY, OFF_PLAY and OUT_OF_PLAY
remain different booleans, independent of current HP. Owned death records
OFF_PLAY; it does not remove the actor or its Trove slot. The shared clone
guard reads the retained original target's actual `baG` before criterion actor
rebinding and applies the installed runner corpse policy. It no longer rejects
a proved true value as unknown or substitutes a hardcoded false.

Legacy actors without this producer retain the bounded older creation/death
authority; arbitrary HP0 provides no OFF_PLAY proof. Six focused life tests
and actor, retained-original-target and registered-summon death integration
regressions were added. Together with the iterator/map/producer suites this
checkpoint contains 31 new tests; their execution remains pending the shared
validation run. Revival, withdrawal, actual fdt removal and fight cleanup need
their own explicit native transitions and are not inferred from HP changes.

## Other producer gap

Area event `10006` is accepted by `NativeAreaEventRuntime.event`, but no local
producer was found. This does not justify emitting it at turn end: its native
cause and ordering remain unproved. Existing `10000` turn-start policy and
the native movement `10001/10008/10002` path remain separate contracts.
