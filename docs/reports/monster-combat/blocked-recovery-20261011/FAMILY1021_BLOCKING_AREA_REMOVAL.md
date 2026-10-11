# Family1021: remove a movement-blocking effect area

Installed registry maps family1021 to `eXV`, extending `eYc`. Its native description is `Retrait uniquement`, with one parameter: area reference to remove (`-1` means any reference). Representative extracted definitions include341885 (reference1759), 333026 (reference1725), and100526 (reference-1).

## Native behavior and reuse

`eYc.C` decodes the removal reference. Missing replacement parameters default to `-1`, so the one-parameter1021 definitions do not construct replacements. `eYc.c` uses an explicit Qq recipient when present; a rejected explicit area never falls back. Otherwise it iterates actual `Qs.bdm`, tests the virtual `y` filter and cell membership, and takes the first matching area. It then checks `Qq.bcF` independently, emits its normal notification, and removes through `Qs.b`.

The only selection difference of `eXV.y` is rejecting areas whose `Qq.bcP` is false, in addition to the base reference mismatch. `bcP` is movement blocking, not `bcF` removability or the existence of an obstacle ID. Native faW and fbd return mutable constructor movement-blocking booleans. faZ/faY/faN/faX/faU/fbc inherit `Qq.bcP=false`; faV does not override it. faP overrides the method, but the existing registered battleground-border producer verifies its nonblocking constructor.

Existing `NativeAreaRemovalHandler` already implements eYc lifecycle, selection, codec, removability, Qs removal callback and removed-PV event scope for843/911. Family1021 now reuses that machinery with the movement-blocking predicate applied before the first-match selection. Unknown contracts or missing constructor booleans fail closed; normal `_rows` validates faW/fbd provenance before selection. No native default was inferred from an absent arbitrary field.

Runtime changes are limited to registering1021 with that handler and adding it to the existing preparation family tuple. Existing843/911 paths use their original selection behavior.

## Coverage boundary and validation

The static current-family coverage report contains49 monsters with owned spells missing1021 (34 have this as their only missing family;15 have additional missing families). The50 exact matching rows, including one `no_owned_spells` record, are preserved in `.runtime/monster-blocker-recovery-20261011/family1021-affected-refs.json`. These counts describe dependency reach, not successful runtime activation. Conditions and area constructors can still block execution.

New `test_combat_area_remove_blocking.py` verifies native true/false and unknown constructor authority, first eligible Qs ordering, explicit-target no-fallback and the actual341885/reference1759 removal route. Independent focused validation passed **9/9** (new3 plus existing removal6), with stable source hashes; receipt `offline-area-remove1021-tests.json/log` is in the private recovery directory. Full monster qualification remains pending.

Bytecode evidence is retained privately as `eXV-family1021.javap`, `eYc-family1021-base.javap`, and `Qq-family1021.javap` under the recovery directory.
