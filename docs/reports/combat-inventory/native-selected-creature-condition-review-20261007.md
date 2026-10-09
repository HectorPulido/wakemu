# Native selected captured creature availability

Original `eON` (`IsSelectedCreatureAvailable`) accepts no arguments. It requires
the actual source object to implement `eHP`, requires a non-null `drI` component,
then reads `fxj`, `fxl` and `Qo`. Its status is -1 when the selected descriptor
is absent, 0 when the selected occupied slot is available, and -2 when occupied
but unavailable. Only status0 is native boolean true. This predicate is distinct
from `eOU` (`IsSummonedFromSymbiot`), which reads `eHg.dTC`.

The actual owned player client actor `biB` explicitly implements `eHP`. Ordinary
actor authority now supplies that attested type and the hydrated, owner-validated
`OwnedCapturedRoster` from the character source. The common adapter resolves the
actual caster and forwards this component to the source-proven roster helper.
NPCs, summons, unknown actor implementations and missing stored components are
not promoted to an empty roster or an available creature. Missing required
authority remains an unknown condition; no owner/controller roster is borrowed.

Tests cover occupied available/unavailable slots, absent selection, signed-byte
out-of-range selection, missing type/component, invalid statuses and incorrect
predicate arguments. The focused condition and roster/store suite passed24
tests. No database migration, service operation or world restart was performed.

## Space in the same owned component

Original token382 (`GetSpaceInSymbiot`) constructs numeric `eLm`. Its declared
signature is empty, but the constructor does not call signature validation and
ignores all parsed arguments. Actual class criterion7348 passes `"caster"`.
The general evaluator therefore accepts and ignores parsed arguments without
evaluating them, including irrelevant selectors and arithmetic expressions.
It resolves caster `eGj` through `eII.a(ePF.qfD)`, requires
the actual `eHP` type, then reads `eHR.fxp`. That implementation visits exactly
slots0 through9 and counts null descriptors. An occupied unavailable creature
still consumes a slot; profile characteristics and the selected slot do not
alter capacity.

The new numeric callback uses the same typed owned roster as `eON`. A proven
non-eHP source returns native-1. Missing type or an unhydrated component remains
unknown, because absent stored data does not establish a native null component.
Tests exercise all eleven occupancy counts with both availability patterns,
missing authority and ignored arguments. An original parser/evaluator probe
passed five argument variants, including a division-by-zero argument that is
not evaluated. The combined focused suite now passes
**25 tests**. Original bytecode evidence is preserved in
`.runtime/combat-review-20261007/eHR-space-source.txt`.
