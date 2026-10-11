# Native group flags8 and24

Offline representative audit: initialization refs4752/4754 rejected flag24; spell refs5446/5451 rejected flag8.

## Flag24: bounded registration correction

Installed `eVl` names ID24 (`rwU`) RANGED_EFFECT. A complete installed `wakfu-client.jar` class-reference scan found only `eVl`, `eXt`, and `eYE` referencing that enum field. `eXt.bbx` adds native event2217 when it is set. `eYE.a/b/u` classify ranged/melee effects using this flag and distance. Neither reference changes group registration, child arithmetic or event selection in eZR/eYg/eZX.

`validate_group_registration_flags` now accepts24 while preserving the original raw effect metadata and all active/constructor authority checks. Damage and range consumers retain their own native validation; this is not blanket acceptance of24 in unrelated handlers.

Three NEW tests pass for genuine constructor/active contexts, ordinary placement rejection, and continued unknown/health-ordering rejection. Original tests remain untouched. Actual refs4752/4754 must be replayed and fully qualified by the coordinator before activation.

## Flag8: concrete missing authority, unchanged

Installed `eVl` names ID8 (`rwE`) SORT_TARGET_BY_PERCENT_HEALTH_ASC. Its sole consumer is `faK`, which chooses `faI` before flag25 and distance14/26. `faI` first queries actual `PV.a(ffw.sgC)` characteristic presence; a missing first characteristic returns1, a missing second returns-1. For present characteristics it compares Java float32 `(PA.aYS / PA.aYU) * 100` via Float.compareTo. This includes stable ties and Java zero/NaN behavior.

Current ordering only qualifies native distance14/26 and its exported identity metadata. Enabling8 requires actual PA-presence/current/max authority, exact float32 comparison and source-qualified metadata for those definitions. A simple HP/max fallback or registration allowlist entry would silently change target selection. Flag8 therefore remains rejected, including the existing original regression for unknown [8,26]. No guessed HP authority or test modification was introduced.

Source bytecode artifacts: `.runtime/monster-blocker-recovery-20261011/subscribed304/{eVl,faK,eXt,eYE}.txt`; `faI` additionally inspected using installed javap.
