# Native remote effect snapshot producers

The installed client exposes two different snapshot producers. They must not
be treated as interchangeable reconnect contracts.

## Source contracts

Evidence: `spell-access-eZU-native.txt` and `spell-access-eZR-native.txt` in
`.runtime/combat-review-20261007/`; `javap -p Qe eZR eZk`; native `eZV.fSq`.

* `eZU.fSp()` serializes every retained runner. It partitions state carriers
  (`eVi.rpJ`) and ordinary effects into separate new `HashMap<Qe, byte[]>` maps.
* `eZU.mv(boolean)` applies exposure predicates, first selecting state carriers
  and recording excluded state IDs, then suppressing ordinary children whose
  actual state container ID is in that exclusion set.
* `mv(true)` admits ordinary runners only when they are neither `eXE` nor
  subscriptions (`aZN`). State carriers use `fSf OR predicate`, not the
  ordinary predicate alone.
* `mv(false)` has a special owner route when `eZV.fSq()` is true. That method
  tests actual owner `instanceof eGj` and `aGJ()==5`. Its predicate admits
  `fSf`, state carriers, and effects whose actual container is a `fyW`.
* Otherwise a state carrier with `fyW.cxj()==true` is admitted first; the
  ordinary predicate excludes `fSf/fSi/fSh/fSm/fSj/cxz/fSk/fSl`.

`eZR.fSf` requires both a non-null definition and a non-null container, a
container type `aZY` of 12, 14, or 31, and `!definition.fKP()`. The other
container-type exclusions are 36, 19, 25, 32, 28, and 34 respectively.
`fSm` independently tests actual `fyW` container identity and `cxj()`.

## Wire and ordering

The outer snapshot is signed-short total count, then all state map entries,
then all ordinary map entries. Each entry is runner class int, payload length
short, actual `aqv()` bytes, and remaining wall-clock duration int.
The latter is zero when `eZV.ra(uid)` is false; otherwise it is Java narrowing
of `max(0, eZV.qZ(uid) - System.currentTimeMillis())` from long to int.
Turn duration does not establish this separate wall-clock timer registration.

`Qe`, `eZR`, and `eZk` declare no `hashCode` or `equals` override. The two
fresh `HashMap<Qe,...>` maps therefore use object identity hashes. UID order,
insertion order, and the retained manager's iteration order do not prove the
resulting map iteration order. State-first partitioning is proven; exact
within-partition native ordering remains unavailable without actual native
object hashes and map topology.

## Metadata completion

The shared `ExportClassSummonEffectTrees.metadata` exporter now records
`native_active_effect = effect.fKP()`. Existing state exports already preserve
`cxj` for each selected level. This source edit has not regenerated deployed
metadata. Container identity/type, owner `aGJ`, timer deadlines, runner bytes,
and object-hash topology are runtime facts rather than static definition
defaults. A reconnect exporter must identify its actual caller (`fSp` versus
`mv`) before applying filters. No actor payload or services were changed.
