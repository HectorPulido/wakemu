# Sublimation review — 2026-10-09

Identification UI on r55 is accepted by Hector: fresh La Cola lost its question
overlay, showed three sockets, and displayed AIR mastery 23. Reconnect
persistence remains unconfirmed by that graphical acceptance.

## Inventory and native installation

The active database has 388 enabled BASIC native sublimation patterns. At the
start of this review no player inventory owned a matching scroll; an empty
sublimation list alone therefore does not demonstrate a UI defect.

Audiluna's newly identified La Cola, UID 1099511633623, has socket colors
BLUE/GREEN/BLUE (3/2/3). Scroll 27123, **Topología II**, matches that exact order.
Give one with `!item 27123 1`. Keep the target unequipped, open its enchantment
window, select the Sublimations tab, choose the compatible scroll, and apply.
Expected: one scroll consumed, sublimation shown on the target, socket colors
unchanged. Reopen inventory and reconnect: the attached sublimation persists.
Native removal destroys the attachment without refund under the explicit local
policy; do not expect the scroll back.

Use this acceptance after the complete image includes the source changes below.
It accepts installation and persistence, not combat effects.

## Source corrections, not yet deployed by this reviewer

- Every socket-mutation success response now initializes required empty-slot
  item references before native protobuf decoding, including sublimation apply
  and removal.
- Applying a sublimation accepts a scroll stack and consumes exactly one unit.
  Sacrificing equipment still requires an unstacked UID.
- Replaying the same already-attached sublimation is a no-op even after the
  short network deduplication window; it cannot consume another scroll.

Luna verified seven codec/dispatcher tests and three isolated SQL integration
tests covering compatible/incompatible patterns, single consumption, removal,
stack 3 to 2, and late retry remaining at 2. The real SQL apply response 13983
was captured privately and accepted by the native parser with three sockets and
the installed sublimation 27111. Runtime inventories/services were not modified.

## Actual effect coverage

All 388 active scrolls have native equipment-effect definitions. All 388 use
generic 304 (`eWu`), applying a state; none is an ordinary flat bonus. For
example Topología II applies state 5992 at level 2. Merely storing its item
reference in ProtoShard field 3 (wire tag 24) does not execute that state.

Before this work, `equipment_stats` and `shard_bonuses` ignored attached
sublimation fields 24/32. Native bytecode proves that `fnR.ggP` obtains the
scroll's effects and appends them to the owning equipment iterator after
compatibility checks. `eHi.bY` applies passive variant-zero effects with the
**parent gear** as container: type 12, ID equal to gear reference, level equal to
the gear's native evaluation level; owner is both caster and target.

Reusable native effect-source mapping is available in source, with no automatic
combat hook. Installation is the bounded functionality verified in this review.
Do not claim combat effects work. Unknown state closures or native context must
remain explicit rather than becoming invented characteristic bonuses.

The reusable source planner is now in
`server/wakfu_server/combat/combat_equipment_initialization.py`. It selects the
owned active equipment sheet, reads attached fields 24/32, requires an explicit
boolean eligibility callback, validates complete native effect closures, and
retains the parent gear container. No existing runtime path imports or calls
this planner; it does not activate states or change current combat behavior.
Luna verified five additional planner tests: both attachment fields retain the
parent gear context, explicit eligibility is required, passive filters are
preserved, and malformed closures reject. Together with installation tests,
this review has 15 directed passing tests plus native response decoding.

The next general integration must resolve these together:

1. Classify ordinary equipment state roots separately from flat bonuses without
   bypassing the existing unsupported-equipment diagnostics.
2. Merge the full equipment/scroll effect closure into the compiled runtime
   catalog before constructing the runtime factory; evaluated stat summaries
   alone omit targeting, children, criteria, flags, and trigger metadata.
3. Validate owned gear container identity and evaluation level, attachment
   compatibility, enabled/disabled authority, state resistance/timing context,
   and complete child-state dependencies. State 5992 is a verification example,
   not a special-case implementation.
4. Establish the initialization ordering relative to breed/deck/aptitude setup
   and fight-start subscriptions from native evidence. Native `eHi` equipment
   effects already exist before battle setup; adding them at an arbitrary hook
   could change conditions and resource snapshots.
5. Carry the existing explicit development fallback and diagnostics through the
   initializer. A skipped source must restore its transaction, outbox and RNG;
   unsupported effects must not silently become zero or partially execute.

Root chose to preserve combat and deliver verified installation plus reusable
mapping first. No global combat hook is introduced by this review.
