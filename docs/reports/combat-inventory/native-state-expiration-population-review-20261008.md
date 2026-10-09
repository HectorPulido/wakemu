# Native state expiration population review

The runtime could leave valid temporary effects alive because its early timer
check covered fighter state ledgers and stat effects only. A group with the
only timer never reached expiration. Area state carriers had a second omission:
the expiration collector and target resolver required a fighter, even though
registered area Qf managers can hold states with clocks on their actual caster.

The shared producer now checks all actual state managers and owned group timers.
The expiration transaction collects their existing timers and resolves their
actual manager. This includes retained area Qf objects only when they still own
a scheduled carrier; removal of an area does not create a timer or an area turn.
An exact matching caster clock removes the carrier from either active or retired
manager. A different actor, phase or round leaves it intact.

Original client `TC.a(long,short,SU)` and `TC.b(long,short,SU)` select the absolute
short round bucket. `TC.a(long,SU,List<Th>)` filters by `Th.biD()` actor identity,
checks callback membership and dispatches through `SU.a(Tz)`; it does not filter
callbacks by fighter versus area manager. `TC.c(short,SU)` visits the previous
round start/end buckets using identity zero. Existing `StateTimer` arithmetic
and caster/target routing remain unchanged. The local turn event delivery order
is an explicit server policy, not a newly claimed native server callsite.

State-owned children are removed before their class310 carrier. The regression
uses an actual class649 ownership record: its eWn removal deletes the temporary
spell registry entry and records the raw spell UID tombstone before the carrier
unapplication. Existing retained records/order cleanup remains in the same
unpublished expiration transaction. Missing carrier bytes abort without changing
the original ledger or action counter.

The initial three regression methods produced four assertion failures (the area
case checks both active and retired managers). After the fix, the four new
methods plus the existing state timer suite pass: 11 tests, 0.088 seconds.
Catalog-dependent expiration/grant regression testing is delegated to validation.
The companion JSON records source hashes and the exact verification scope.

Positive realtime durations and delayed effect scheduling retain their existing
source-specific guards. Consumable state changes use explicit native321 level
reduction/reapplication logic; this change adds no guessed consumption, blanket
decrement or refresh rule. The native round producer under dynamic timeline
changes remains a separate source audit item.
