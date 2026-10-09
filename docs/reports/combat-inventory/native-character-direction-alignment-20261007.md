# Native character direction and alignment

## Evidence

The offline probe `sniffer/java/ProbeNativeGetCharacterDirection.java` invokes the client `eJv` evaluator from the local client jars. `eJv` initializes its selector to caster. Its one-argument form selects target only when the argument equals `target` ignoring case; any other string keeps caster selected. The evaluator calls `eII.a`, returns `-1` when no `eGj` resolves or when `eGj.bcy()` is null, and otherwise returns `aAS.dyI` widened to a long.

The probe confirms the client's `aAS` values: `NONE=-1`, cardinal/diagonal directions `EAST=0` through `NORTH_EAST=7`, `TOP=8`, and `BOTTOM=9`. It also confirms target selection and case-insensitivity with distinct caster and target facings. The server's current fighter snapshot stores planar directions 0–7; absent or invalid snapshots remain unknown rather than being replaced with a default.

One target form remains intentionally unsupported: when the selected value is an explicit cell (`aBn`), `eII` may search its `QI.U` occupants for the first `eGj`. The runtime does not yet provide that exact first-occupant authority, so `GetCharacterDirection("target")` on a cell raises `UnknownCondition`, even if a fighter happens to be at that cell in the broader actor roster. A proven null target with no cell and a registered Qq/faV area still resolve to `-1`; an area PV's position is not treated as an eHg coordinate.

`IsInAlignment()` compares the resolved caster and target coordinates: same X or same Y. A resolved native null target returns false. An unresolved non-null recipient remains an error. Alignment and diagonal share the typed target resolution: actor targets and explicit `aBn` cells provide coordinates; a registered Qq/faV PV does not.

## Validation

Focused Python regressions cover every native direction enum value, selector behavior, null/non-fighter handling, unknown direction snapshots, and malformed signatures. Adapter tests verify live caster/target direction snapshots and explicit cell/null alignment. The probe is compiled and run offline with:

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/combat-review-20261007/get-character-direction-classes \
  sniffer/java/ProbeNativeLevelGroup.java sniffer/java/ProbeNativeGetCharacterDirection.java
java -cp 'client/lib/*:.runtime/combat-review-20261007/get-character-direction-classes' ProbeNativeGetCharacterDirection
```
