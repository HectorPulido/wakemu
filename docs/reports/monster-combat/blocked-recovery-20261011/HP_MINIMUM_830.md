# Native HP minimum setter (family 830)

## Installed-source contract

The installed runner is `eXw`. Its calculation method `C(Qe)` is empty. Its execution method checks that the actual target PV exists and contains HP characteristic `ffw.sgC`, then calls `PA.aZg()`. Otherwise it marks nonexecution with `mu(true)`. `aZg()` delegates to `on(aYW())`: assign the actual minimum, respecting the characteristic's frozen flag. The minimum is not assumed to be zero.

Unlike the existing kill runner, this runner has no KO-clock mutation, added event 192, or HP restoration on removal. Its caster is optional. Calculation must preserve an amount changed by L1 subscribers: the installed Java probe sets running amount 37 and proves that calculation leaves it 37 while the HP assignment still uses the minimum.

## Implementation and supported authority

`combat_hp_minimum_set.py` reuses the owned-runner/application infrastructure with its own execution semantics. Registered ordinary targets require an actual HP snapshot including minimum and bounds; incomplete snapshots reject. Raw HP authority and frozen characteristics retain their existing setters. Actual HP-owning `faW` and `fbd` area PVs reuse their existing validated constructors and HP writers; they remain registered Qq PVs, with no fighter alias or ordinary-fighter death event. Proven HP-absent area PVs and null targets do not execute. Unknown PV/resource authority rejects.

The runtime registers family 830, its preparation and event lifecycle, and the stat-removal dispatcher removes retained runner records without restoring HP. Source context currently accepts an absent caster or a registered ordinary fighter caster. Other source-PV/context combinations still require qualification; registration does not imply every historical monster can activate.

## Evidence and focused validation

The installed Java probe and output are under `.runtime/monster-blocker-recovery-20261011/faw-pa/ProbeNativeHPMinimum830.java` and `native-hp-minimum830.jsonl`. The new sealed test fixture covers 12 combinations of minima 0/1/17, current values 17/80 and frozen/unfrozen characteristics, with running amount 37.

Independent focused gate: 14/14 tests passed (six new family-830 tests and eight existing kill tests), with no existing test edits. Receipt: `.runtime/monster-blocker-recovery-20261011/offline-hp-minimum830-tests.json`. Tests additionally cover raw HP assignment, retained removal, missing minimum/presence rejection, actual faW/fbd creation and rollback, QI preservation, and proven HP absence. The isolated native actor characteristics supplement is the existing extracted `monster-combat-final-20261010/actors.json`, not fabricated bounds.

## Inventory limits

The authoritative historical classification contains 72 references mentioning 830: 46 `almost_one_family`, 16 `multiple_missing_families`, eight `data_gap`, and two `no_owned_spells`. The aggregate missing-family count 70 excludes the two without owned spells but includes the eight data gaps. Neither number means ready to activate.

Representative 2339 Crugmita historically mentions 830 and owns spells 3430/3431/3432. Existing extracted leaves 86428 and 86431 contain `HasState(7504, "caster") and HasState(7507, 6, "target")`. However, traversal of the current sealed spell roots reaches newer 339xxx references and does not reach those old leaves. This catalog divergence must be resolved by a fresh bounded actual closure/replay before claiming qualification for that monster or projecting activation counts. No database, deployment, service restart or active-catalog modification was performed.
