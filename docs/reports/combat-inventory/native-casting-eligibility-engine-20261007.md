# Shared native casting eligibility engine

`combat_casting_eligibility.py` now separates the ordinary `fcj` decision from
resource, deck and usage policy. It returns native `fyJ` field names rather
than converting missing facts into an allowed cast. This is a reusable engine
boundary, not a claim that the runtime producers or UseGateEffect are complete.

The source is `.runtime/combat-review-20261007/fcj.javap`, first public overload
`a(PV,eVo,aBn,boolean,int,int,boolean,boolean,boolean,boolean,amb)`.
The evaluator preserves:

- Null container and current-turn checks before effective range.
- Target fighter resolution before range and QI endpoint checks.
- Independent QI.aK/P/R predicates, LOS versus QI.j, then cell criterion.
- Ordered admissible-PV criterion evaluation, including the fch.fVt exemption
  toggle, whose default true evaluates exempt fighters normally.
- Root shape/selector collision checks before mandatory free-cell QI.g.
- Target sdR identity exception and caster sdG level restriction.
- A second root selector pass, without a shape requirement; a null selector
  accepts immediately, while an empty root list rejects an actual fighter.
- Cell criterion evaluation when the target cell or actual QI is proven null.

`native_casting_distance` implements signed Java subtraction, Math.abs and sum
wrapping, including the INT_MIN special case. It is separate from geometric
diagonal criteria and from any ordinary Python Manhattan-distance helper.

`native_use_gate_effect` evaluates the ordinary eligibility and independent
static alignment/path query, then negates their conjunction. It does not inspect
the GATE roster and does not invoke resource/deck checks or execute effects.

The hooks own actual caster/container/target/QI identities and exact producers;
each requested missing or non-boolean fact raises `UnknownCondition`. Runtime
integration must bind original root iteration order, actual fbX.dC and fbX.a
results, casting criterion raw/parsed presence, native selector results, exact
root collision, current turn, and actual terrain/obstacle facts. Existing
walkability or living actor-center queries do not prove those facts. Missing
hooks do not prevent earlier native rejection, preserving short circuits.

Ten initial lightweight regression tests passed with:

```sh
env PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_casting_eligibility
```

These tests cover short-circuit authority requests, stage ordering, P/R
separation, criterion cell/object conjunction, root collision ordering, null
selector acceptance, empty-container selection rejection, Java overflow, and
evaluation of both UseGateEffect calls. They do not replace an original-client
fcj oracle or complete producer integration. No services were touched.

`ProbeNativeCastingDistance.java` subsequently executes the original range
overload with a PV interface exposing only the two source coordinates. Eight
acceptance rows cover ordinary/self ranges, INT_MIN abs, wrapped addition,
wrapped subtraction and a wrapped zero distance. All eight agree with the
Python helper/evaluator; their retained regression is the eleventh test.
This probe loads no binary catalogs and does not instantiate a fight.

Fresh ePI bytecode confirms an additional distinction for adapter integration:
UseGateEffect invokes the **five-argument** static fcj overload, so its Sn
`path_option` is false. Normal fcO supplies selected cwN to the six-argument
overload. ePI also returns native false before either call when actual runner
is not eZR, container is not fyG, fight is null, caster is not eGj, or resolved
target coordinate is null. Missing emulator facts cannot establish those
native false prerequisites.

## Actual producer and normal cast integration

`combat_casting_context.NativeOwnedCastingContext` now binds the engine to
the current owned actor/QI population, native turn, signed range, exact masks,
published ordered Vy surfaces, captured global PV collection order, root
selector metadata, and the separate fKX collision shape. `UseGateEffect()` is
registered as a boolean criterion with its native empty signature. Its adapter
implements proven non-eZR/non-fyG/null-coordinate prerequisites independently
of missing authority. Casting-only table selection avoids requiring the AP
modifier map because native ePI/fcj never reads resource costs.

Normal `prepare_spell_cast` now consumes the same adapter-owned producer.
Resource and usage checks remain independent; the old walkability membership,
cardinal-only linear check, actor-center occupancy and delegated approximate
LOS block have been removed. Missing owned producer is an explicit rejection.
Native fcO evaluates its static alignment before ordinary fcj; UseGate evaluates
ordinary fcj first and then the five-argument alignment, regardless of rejection.

The fresh source-backed export contains 2,152 unique roots reached by the
current 851-entry class/summoned-ability casting closure at positive and zero
levels. All 2,152 have selectors. 2,149 have an actual null fKX; only 120607,
121253 and 175760 have a collision shape. This proves why using aZP effect
geometry for collision would reject ordinary damage against occupied cells.
Published data is `server/protocol/native-class-casting-roots.json`; the exporter
is `ExportNativeCastingRoots.java`. The extra enum identities were obtained by
`ProbeNativeCastingCategories.java`: txX12, txZ14, tya15, tyb16; rNX19, rNI1.
The field set is distinct from general monster spell installation.

Normal fcO overrides now include category14 same-affiliation GATE/type19 and
category16 direct-owner area/type1 range/LOS acceptance. The source-proven
`combat_portal_casting` evaluator is bound for category12: usable entry/exit
sets, selected entry LOS with an actual null target, selected gate-cell linear
restriction, category15 same-cell rule, and exact ordinary fallback conjunctions.
Raw portal rays use actual caster height at their supplied source coordinates;
they neither implicitly ignore the caster QK nor perform amP-overload cleanup.
Choosing an execution exit identity/path remains separate and unproved.

The Sn producer uses the actual efR snapshot, bcK/bcL/bvz, published physical
columns, exact QI.Z and target biN registration scope. It clears biN after the
query, matching QI.bdK. The amP LOS producer uses exact QI.h and native Sf rays,
then clears biO in the caller, matching fcr's QI.bdM. Neither consults the
walkable set as a substitute for these native consumers.

The eNM IsEnemy cell producer is also bound lazily: native fk IN_PLAY/OFF_PLAY
enemy footprint checks precede the first QI.V eHg affiliation check. Radius0
matches full XYZ; positive radius uses ala.a and ignores Z. It does not merge
all QI obstacle affiliations. Native null and actual Qq targets retain their
distinct true and false results.

The lightweight suites now have 25 passing tests, including conditional cost
independence, source-backed QI recipient resolution, captured admissible-PV
order, native null fKX, normal shared-producer consumption and missing-source
rejection. Full class audits and independent validation remain necessary.
Actual aBn provenance is now carried separately: actor aliases use the exact
QI first-fighter lookup, while coordinates, distance, alignment, area identity
and IsEnemy preserve the raw cell argument. Proven absent fighter aliases have
native direction-1 and no fight property; an unknown lookup remains unknown.
This applies to normal conditional table selection, raw gtP and portal entry
table reselection. Broad conditional-table and gameplay completion is not
claimed by these focused tests. No runtime service was touched.

### Shared eMr visibility and ordered rejection diagnostics

`native_condition_los` now consumes the same actual fcr/QI producer as ordinary casting. It preserves the original aBn singleton argument independently from a resolved fighter alias, expands actual actor footprints in native x/y order, returns false for Qq arguments, and clears QI.biO after each attempted ray. OFF_PLAY actors remain in the actual registry instead of being removed by an HP filter. Negative radii or Java footprint loops that overflow remain explicitly unavailable rather than approximated.

The eligibility helper accepts an optional trace list. It records only consumed callbacks in their existing native order; it never repeats a condition or geometry query. Normal cast rejection exceptions expose `native_casting_diagnostic` with the raw native criterion, spell/level, caster, actual target argument/alias and consumed hook outcomes. Missing-authority exceptions expose `native_casting_trace` and `native_casting_context`. This separates criterion-cell, criterion-PV, sdR, sdG, geometry and root-selector failures without changing result codes or error text.

Focused validation: `test_combat_casting_eligibility`, `test_combat_use_gate_conditions`, and `test_combat_condition_los_native`: **29 tests passed**. The eMr tests verify consumer argument/footprint order and cleanup; they do not claim a new exhaustive original eMr oracle.

### Controller predicates, trigger casting and independent root selectors

Original `eIC` and `eOx` require an actual source eHg and empty BOOL signatures. Their target eHg list is produced by `eII.c`: direct eHg, otherwise actual cell QI fighter plus Qs geometry. `CasterAndTargetHaveSameOriginalController` compares source/target `dTD`; `IsOriginalController` compares source `dTD` to target `PV.Sn`. These consume the existing attested current `eGj.dpr` controller producer, independently from owner/account, master, AI flags and fresh summon caster. Native JVM verification passed 64 identity/controller combinations including zero and signed-long minimum, plus null/non-eHg targets and malformed source.

`ePJ` retains ePI's algorithm but changes two independent sources: its endpoint is the actual `eII.aU` trigger runner `bbd`, while its container is **current runner PN.bah().PZ.baR()**, not the trigger's retained PL. `fcS.baR` delegates to the current `fXw` fyG. The normal transaction's active spell scope now preserves a typed spell/level PL descriptor and restores it across nested scopes. A missing current PZ is false; a present PZ without PL authority remains unknown. Conditional fyP selection keeps the original target argument even while the eligibility geometry evaluates the trigger coordinate. No NPC source was modified.

The native class casting root exporter now includes actual aZF selector class/mask for every one of the 2,152 roots. Casting root selector acceptance no longer depends on an executable effect-tree root record. This closes the structural Jamajam group-root gap: original root 327650 has fcE mask 5. This publication is scoped to existing class-reachable root IDs; it does not export monster spell populations.

An additional source inspection corrected the area type distinction: plain Qq is not eHg, but `faV` extends Qq and implements eHg. Registered faY/faZ condition targets therefore use their actual coordinates and literal Qq.bcK/bcL zero values; their original controller is actual bgZ.PV.Sn. Other area types without an attested contract remain explicit unavailable producers.
