# Native aptitude allocations

The observed build12772 rejection for character7 at level6 was local: `builds.validate` rejected every allocated aptitude entry. The client did not require filling every category before saving.

Native protobuf `eb` uses field3 (tag24) for sheet level and repeated field4 (tag34) of `dX` entries with bonus ID field1/tag8 and point count field2/tag16. Native `eQx.f` serializes sheet level-1 plus HP bonus1/points2 as `18ffffffffffffffffff01220408011002`. `eQr.cmZ` passes the assigned point count as the native effect level, independently of character level.

Installed bdata exports contain31bonus definitions and5categories. `eQI.QI` sums assigned points by `eQu.QC` category; `eQI.t` subtracts them from `eQv.QF`; `eQH.dF` counts grant thresholds at or below effective sheet level. `eQZ.a(eQI,short)` validates known bonuses, nonnegative points, category budget and optional `eQG.bWy` maximum. Zero maximum means no separate bonus cap. Our validation also rejects duplicate protobuf fields/bonus IDs and unknown fields rather than accepting ambiguous assignments.

Level6 grants intelligence2, strength1, agility1, luck1, major0. Level200 grants intelligence50, strength50, agility50, luck49, major4. These are read from native thresholds, not race-specific formulas. Partial category allocations are accepted. SQLite persistence uses the existing owned generation lease and atomic build save.

Native bonus1 effect136429 is generic986, registered as `eZI(ffw.sgC)`. Two points evaluate to `[8,1,0]`: +8% HP maximum, adjusting current on application. `eZI.c` calls `PA.om`; `fff.om` accumulates percentage and `fff.aYU` computes flat maximum plus integer division of flat×percent/100. Actual native Java verifies110+8%=118 and116+8%=125. Flat HP includes equipment and unconditional flat aptitude effects. Persistence keeps full HP full when maximum changes, otherwise keeps/clamps current HP according to the existing save-build policy.

The common equipment/stat evaluator now includes verified unconditional aptitude `eWN` flat current/max effects, scalar `eWQ` effects and this exact HP percentage case. Grouped `eYg`, criteria and any unverified effects are recorded as unsupported; they are not converted into invented bonuses. Metadata evaluation of a scalar does not imply every characteristic has been added to every combat snapshot or damage calculation.

Four aptitude tests passed (level6, level200, malformed/overspent sheets, save/reconnect atomicity, HP percentage+amulet and major AP); twelve equipment tests passed. Native verifiers/exporters are in sniffer/java. No deployment, restart or GUI interaction was performed by this change.
