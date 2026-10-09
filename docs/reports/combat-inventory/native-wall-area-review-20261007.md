# Native configured wall area review

WALL is the generic `bcZ` implementation of `fbd`, native area type `7`. The creator records the exact fbd constructor snapshot, captured Qf manager, mutable HP, LOS and movement flags, and the QI obstacle slot when the native flags require one. The row remains a Qq PV; it is never inserted into `Fight.actors` or assigned fighter resources.

`fbd.aQc` consumes `bhe[0..3]` as HP base, per-level HP, movement blocking and line-of-sight blocking. It computes `base + (short)level * perLevel` in Java float arithmetic and converts the result to int. A valid four-value constructor creates the HP `PA` and `eZV` Qf manager. The provider mirrors float32 arithmetic and Java float-to-int behavior, validates native class/type/container identity, and keeps the values immutable in `native_wall_constructor`.

The two blocking flags have separate consumers. `bcP()` reads movement (`bhe[2] == 1.0f`); `fTq()`/`bcJ()` read LOS (`bhe[3] == 1.0f`); `bcO()` is their OR and controls QI obstacle registration. `fbd.bcK()` returns `6`, which is exposed as the wall's LOS metadata. It is not an event callback channel: inherited `Qq.bcx()` returns `1`. `fbd.e(amP)` is false, `c(amP)` is null, and `n(amP)` is empty, so the wall's own activation produces no child recipients while its constructor-created Qf manager still exists.

The installed prototype `1605` is a useful zero-HP example: parameters `[0.0, 0.0, 1.0, 0.0]`, properties `[3, 8]`, and HP `0` at levels 1, 30 and 200. The Java probe reports `Qq.baF=true`, `baG=false`, `baK=false`, while `fbd.baD=true`. Thus fbd's HP-based `baD` does not mean the Qq lifecycle guard is removed; HP0 alone leaves its QI obstacle registered. The separate `Qq.b`/`QI.g` removal path is represented only when that actual lifecycle event occurs.

Prototype `1063` provides the positive-HP path: `[1,000,000,000, 0, 1, 1]` creates a wall with one billion HP, movement blocking and LOS blocking. The fbd static characteristic set is `rMK` (`17, 27, 28, 29, 30, 31, 49, 95`) plus HP (`1`); `eRF.aYY` initializes the non-HP values to zero. Unlike eGj actors, fbd has no absorption characteristics `92`, `97` or `100`. The eXt target path checks PV characteristic presence and writes HP through the target PA. The wall damage snapshot therefore exposes only the proven fbd characteristics and the mutable current/max HP pair. Missing actor-only armor, virtual HP and barrier remain zero and are not added to the row.

Damage resolves an active registered fbd PV through area identity and constructor authority, calculates against its real position/direction, and updates `native_wall_hp_current` with source `fbd.PA.sgC.aYS`. It emits the damage packet and ledger event without creating an actor alias or an actor death event. Reaching HP0 preserves `baF=true`, `baG=false`, `baK=false` and the QI slot; an explicit Qq removal remains a distinct transition.

The offline client probe cloned installed walls at levels 1, 30 and 200 and inspected actual PA values and Qq lifecycle predicates. Probe source: `sniffer/java/ProbeNativeWallArea.java`; native disassemblies: `/tmp/wakemu-wall-bcZ-fbd.javap`, `/tmp/wakemu-fbd.full.javap`, and `/tmp/wakemu-Qq.full.javap` from `client/lib/*`.

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/combat-review-20261007/wall-probe sniffer/java/ProbeNativeWallArea.java
java -cp '.runtime/combat-review-20261007/wall-probe:client/lib/*' ProbeNativeWallArea 1063 1605
PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_wall_area test_combat_qi_fight test_combat_qi_death_lifecycle test_combat_damage_handler test_combat_ordinary_damage_events
```

The focused Python command completed 42 tests successfully. Its lifecycle cases verify constructor authority, real QI registration, actual fbd damage to HP0, continued Qq/QI membership, and back-event classification through the wall's actual direction. The suite does not yet exercise a reaction that unregisters the target wall during eXt's L2 phase; that requires retaining the exact local Qq object across Qs removal and is not inferred from the active-row path.
