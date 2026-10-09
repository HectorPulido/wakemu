# Native shared casting range contract

Offline original client bytecode proves this sequence:

1. `fyF.j` selects the current `fyP.gui().Qi(level)` minimum.
2. `fyF.i` selects `fyP.guj().Qi(level)` maximum and sums `eHl.b(fyU)` for each spell category (`fyF.rgG`). Java signed 32-bit addition applies. Category modifiers affect fixed-range spells too.
3. `fcj.a(PV, boolean, int, int)` reads characteristic `ffw.sgK` (numeric ID 11). An `eHH` actor with `buX()` true adds one to this generic bonus.
4. Only when the category-adjusted maximum is at least one and the selected table allows range modification, add the generic bonus and clamp to at least the selected minimum.
5. Property `ffe.sdz` (numeric ID 2) caps a maximum above one to one, including fixed-range spells. It can produce a maximum below the minimum; do not repair that result.

`eGj.buX()` means `pGW != null`: the actor is carried. The independent `pGV` relationship and `frA()` describe carrying another actor. Neither condition can be inferred from the other.

The only original jar writers of `eHl.b(int, fyU)` are `eZg.c/d`. Native registry reflection maps `eVi.ruQ` to effect family **1066**, runner `eZg`, extending `eZf`. Application adds `aSg`; removal adds `-aSg`. This is opposite to AP category reduction family 1065 (`eZe`). Both use the shared `eZf` amount/category parsing and category additional-data protobuf `ij.getValue` (field 10). Category effects therefore need complete separate AP (`pOJ`) and range (`pOK`) snapshots, including retained application/removal; freshly created actors have empty snapshots.

## Offline verification

`ProbeNativeCastingRange` invokes the original `fcj` directly, using a proxy only for the three actor reads. Its input is CSV: `minimum,maximum,modifiable,genericRangeBonus,isCarried,hasProperty2`. It prints one native maximum per case; metadata goes to stderr.

The Python verifier imports the production `effective_range` function. The staging bulk import contains 4,143 definitions and 1,035,078 baseline/conditional level rows. It deduplicates their shared contracts, includes negative/zero/below-minimum boundary contracts and Java integer-overflow bonuses, then compares 7,200 scenarios with **zero mismatches**. Counts and source hash are in [native-range-oracle-20261007.json](native-range-oracle-20261007.json).

```sh
TASK_JDK=$(/usr/libexec/java_home -v 21)
"$TASK_JDK/bin/javac" -proc:none -cp 'client/lib/*' -d .runtime/local/range-oracle-classes sniffer/java/ProbeNativeCastingRange.java
python3 server/tools/verify_native_casting_range.py .runtime/combat-review-20261007/range-flags/native-spell-casting-with-range-flags.json --java "$TASK_JDK/bin/java" --classpath '.runtime/local/range-oracle-classes:client/lib/*' --output docs/reports/combat-inventory/native-range-oracle-20261007.json
```

This proves the shared final range arithmetic. It does not prove conditional table reachability, casting integration, client/server characteristic delivery, AP/MP/WP payment, line of sight, effect outcomes, or category effect lifecycle. Those require their own verification. No Docker or world operations were performed.
