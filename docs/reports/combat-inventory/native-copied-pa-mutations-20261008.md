# Copied PA mutation and wire contract

The eHI constructor copies the actual ordered ffh PA operands. The installed
source contains all 92 raw current values, raw bounds and percentage modifiers;
it is separate from the actor's effective current snapshot. Restored or unknown
actors do not acquire this source by copying their effective values.

Original `fff.aYT()` returns raw current. `aYS()` clamps it to effective minimum
and maximum, independently of `ffw.fZB`. `fff.on` uses fZB to select its raw
upper bound; `or` preserves raw current when fZB is true or the PA is frozen.
AP/MP are expandable but have fZB false. HP has fZB true. Expandability alone
cannot select the mutation policy.

For example, raw HP125 with maximum82 has effective HP82. Native `oo(10)`
leaves raw115 and effective82. A subsequent `nG(1)` collapses raw to82 and
returns -33, since nG's return is the raw delta. These setters cannot be
emulated by subtracting from effective HP. The raw tB wire current remains125
until a genuine setter changes it; serializing effective82 would lose state.

The original getters and mutations are reconstructed in `combat_copied_pa` and
`combat_hp_raw`. Snapshot wire validates both representations before encoding.
Known ordinary fresh HP records the actual initial constructor setter operand;
unknown restored snapshots fail closed rather than reconstructing raw HP from
a value that happens to lie within the bounds.

## Actual class 8559 boundary

The real class-14 Ready/grant/transaction audit reached native1002 creation and
its subsequent sibling effects. Family952 (`eYO`, effect413083) then assigned
WP6 while its generic effective-only writer left the copied raw WP at5. The
strict wire check correctly rejected actor288, PC4, raw5/effective6/max6.
This was a subsequent writer defect, not evidence of failed constructor setup.

The forced-characteristic handler now uses source-backed `or` followed by `on`
for every copied PA. Its generic maximum helper preserves fZB/frozen current,
updates the complete copied raw cache and the effective mappings, and retains
the existing live HP/AP/MP aliases. WP remains the authoritative PA4 snapshot;
no unused actor WP field is introduced.

Focused regressions execute the actual952 assignment against a complete typed
copied pool and verify repeated tB serialization, plus mutable WP versus frozen
WP and HP raw preservation. The actual audit `class-character-copy-8559-rawfix-01`
now passes constructor, normal transaction commit, damage/healing mutations,
checkpoint serialization and repeated stats for all three ratios, preserving
the source fight. Ratio100 is the actual native class route; ratio33/50 fixtures
explicitly stress constructor mechanics and are not claimed as alternate native
class branches. This does not yet establish allocated copied-book casting or
cleanup; those are a separate lifecycle audit.

## Ordinary forced assignments

The ordinary eYO scalar transition also previously selected its bound policy
using `isExpandable`. It now reads the exported original `ffw.fZB` field
(`over_max_current`) for the selected PC. In particular, ordinary WP remains
expandable while fZB is false: assigning5 after its maximum becomes2 must clamp
to2, even though the hard bound is20. A focused handler regression covers this
actual WP schema. The HP fZB-true case remains separate. The serial validator
passed all 13 focused forced-characteristic/copied-PA tests, including this
ordinary branch and the complete copied WP wire regressions.
