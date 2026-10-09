# Native distance child-level family1080

Original final `eYi` extends `eWd`. Its C calculation reads native float
parameter0, computes `aBn.A` Manhattan XY distance from the actual caster PV to
actual runner cell, multiplies in float32, then floors and narrows to Java int.
Z does not contribute. Native signed-int subtraction, abs(MIN_VALUE), addition,
float rounding, NaN and saturation are preserved. This is not a damage formula
or a per-spell rule.

`eYi.j` has the same eVt builder as eYx1076: false/false flags, actual source,
and SP set to the calculated full int. Children receive that SP through their
actual context, using native short narrowing or actual container-level fallback
for sentinel-1. Parent flag16 does not replace the explicit family override.
The common eWd child iterator preserves child order and actual caster/PV/cell;
it does not expand the parent area, force a fighter target or use eYg rebind,
limit or success-count rules.

The runtime factory installs the actual runner. The shared eWd dispatcher now
executes family1080, and grouped subscription/retention and exact cell ownership
recognize it. Fresh preparation runs L1 before C/context transfer, then L2 before
child execution. The prepared UID is the actual retained parent UID; children
receive their own runner identity. Group registration happens after children,
followed by L3/L4 and the runner value callback. Event activation recalculates C
before L1 and uses exactly the clone UID allocated by Qe.k's dispatch boundary.
Rejected criteria and failed transactions clean up prepared runner state.

Published class closure contains32 definitions in class component13. Its only
raw parameter pairs are[0.5,0] and[1,0], with no parent criteria or subscriptions.
The source implementation has no reference-ID branches. The original Java
probe executes eYi.C/j and inherited owner predicates across48 cases:96 native
assertions pass, with zero differences against Python. Tests also execute the
actual EffectDispatcher, checking nullable PV/cell preservation, child ordering,
short context behavior, lifecycle phases, criterion rejection and single-UID
activation. With1076 sibling, area-property/group and summon initialization suites,36 tests
pass in0.085 seconds.

Actual class32 Ready execution and catalog-backed factory testing are delegated
to validation. These results do not assert manual client acceptance. Native
exception-catching versus local atomic rollback remains the existing explicit
server transaction policy. No service, database or AI runtime was modified.

Original eZR.fRR independently confirms level routing: PS.Oh other than-1
returns its signed-short narrowing immediately, without reading mb. Sentinel-1
uses actual PL.cmZ or zero for null PL. Regression cases verify actualPL123,
nullPL0 and explicitSP65535 narrowing to short-1.
