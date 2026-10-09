# Gate predicate contracts and shared implementation boundaries

Read-only targeted `javap -c -p` inspection used the original client classes eQb/eQd, eMT, ePI, fcj, fyJ, fbp, faX, bcS, Qs, QI, faV and ala. No runtime process or database was accessed.

## HasValidGateForTp

Lexer token231 maps to eMT. Its only signature is `(string selector, numeric minimum, numeric maximum)`. Only case-insensitive `target` selects target center; other strings select caster center. Numeric expressions evaluate to Java long.

Native prerequisites have unusual boolean results: an actual absent/non-fight context, absent caster eHg, or absent selected center returns0, hence true. An unavailable emulator snapshot is not proof of those native absences. Actual contexts fbX or eVw wrapping fbX expose the active Qs manager. Target center can be an explicit aBn cell or actual target eHg; caster is always separately resolved.

Once prerequisites exist, eMT scans the full active `Qs.bdm` collection and counts candidates in this order:

1. Skip the same native PV object as caster and null entries.
2. Require native area type `fbp.rNX`, GATE, numeric19.
3. Require **captured area `Qq.bcM`** equal to caster eHg.bcM. Direct ownership is irrelevant.
4. Require `QI.U(gate.x,gate.y)` null or empty. Any byte affiliation in this complete native occupied-cell set rejects the gate.
5. Compute `ala.c(Qq,aBn)`. Qq.bcL is0, so this is XY Manhattan distance with native signed-int subtraction/absolute/addition; height is not compared.
6. If maximum is negative, ignore both bounds. Otherwise require minimum≤distance≤maximum.

It returns true iff final count is positive. It evaluates every candidate even after a match; missing later authority must not disappear through Python short-circuiting. A complete empty manager can safely return false without an occupancy query.

`combat_gate_conditions.has_valid_gate_for_tp` implements this core with explicit captured affiliation and QI.U callback inputs. Its occupancy callback must return a complete frozenset of signed bytes; a proven native null set can be represented by an empty set because the predicate treats both identically. Missing facts raise. Seven tests cover empty population, captured affiliation versus ownership, occupied cells, negative maximum, missing facts, complete scan and caster/type exclusion. Condition/runtime adapter integration is deferred until the in-progress class audit finishes.

## UseGateEffect

Lexer token391 maps to ePI; its signature is empty. **It does not read gates, select a destination, or require a portal in the manager.** It resolves caster eHg and the actual current running context eZR. `g(eZR)` reads its actual `bbe` container; only a real fyG spell container proceeds. Missing spell container, fight, typed caster eGj or selected target coordinate returns native false. The non-eZR branch in the original bytecode falls through to a cast; it is not a safe generic null-false contract for arbitrary contexts.

From that actual fyG it evaluates selected fyF casting data against the current caster, target and fight: range modifiability d, maximum i, minimum j, LOS a, free-cell f, fixed terrain flag gjl, allow-self flag l and casting criterion gtP. It computes both:

- `fcj.a(caster,spell,target,modifiable,min,max,LOS,freeCell,terrainFlags,criterion)`, returning fyJ;
- static `fcj.a(caster,target,spell,typedTarget,fight)`, validating linear/path/diagonal requirements.

It returns **false only when the first result is fyJ.OK and the second result is true**. Otherwise it returns true. Both calls run before the final comparison; neither is skipped when the first fails.

The first fcj contract includes effective native range, terrain aK/P/R, LOS or height j, cast criterion evaluated against cell/actual candidate PVs, shape-versus-terrain collision for definitions with fKX/aZF, free-cell g, target fight properties sdR and caster sdG with level comparison, and at least one admissible native target selector. Constructor fch toggles current-turn and invisible-target branches and must be explicitly preserved. Resource cost, owned deck validation and use-per-turn limits are absent from this function. The second contract reads fyF linear b, diagonal k and path requirement e; it can temporarily unregister the actual target obstacle while using Sn path validation, then restores QI occupancy. Its diagonal branch compares absolute X/Y displacements.

Do not reuse `prepare_spell_cast` or `_validate_target`: they add resource/deck/usage gates and currently implement a different subset of fcj. Do not execute effects or evaluate their effect criteria to answer this predicate: native checks casting criteria/selectors, and such execution would recurse into UseGateEffect and mutate the preview. A future shared callback must attest the full ordinary fcj result and independent path result from the actual source fyG container. Unknown cast restrictions or conditional-definition ordering remain explicit unknowns. Capturing a previous request's successful validation would also be wrong if synchronous effects changed caster or geometry before this predicate.

## Gate producers and area lifecycle

Installed prototypes823 and2131 have type GATE19, native client subtype `bcS extends faX`, property3, infinite activation marker-1 and empty child/entry/exit lists. This identifies the installed data, not implementation exceptions. Shared eYQ creation chooses their prototype in the same way as other areas.

`faX.c/n/d` returns null, `faX.e` returns false and aQc is a no-op. Thus it supplies no generic child callback targets; it must not be relabeled glyph faY or aura faN. It inherits stationary Qq coordinates and the common faV/Qq lifecycle and optional property12 Qf behavior. bcS supplies client visual clone/registration metadata, without a server state/AI execution requirement.

The needed producer records native contract faX, static geometry and captured `native_fight_affiliation`: faV constructors initialize ebh=-1; `faV.j(owner)` copies actual caster bcM only when owner.bav is20 (eGj). Subsequent owner team changes do not recompute the area affiliation. A complete active area manager and complete current QI.U occupancy source then suffice for HasValidGateForTp. Area creation/removal, retained effects, registered PV predicates and guard consumers should share this subtype contract. No destination order is needed for this predicate; actual portal teleport execution remains separate and must establish its own native selection order before implementation.

Exact ePI constructor refinement: `new fcj(fight)` creates untouched `new fch()`, whose two constructor booleans are both true. Thus this predicate's fcj enforces the actual current-turn fighter check (`fVs=true`) and does not enable the special invisible-target autoaccept branch (`!fVt`). The proposed callback must represent these exact defaults.

## Predicate integration completed

After the audit source freeze ended, ConditionContext and RuntimeConditionAdapter were wired to the pure HasValidGateForTp helper. Native eZR.I explicitly passes its actual target PV or, when null, bft as an aBn; this proves the adapter's target-cell center without inferring an actor from a failed lookup. Missing caster affiliation, unknown target PV or needed gate occupancy still rejects. The complete empty active manager requires no occupancy callback and yields false. A future exact occupancy producer is accepted only through `cast.gate_cell_affiliations(preview,plan,x,y)`, returning the complete signed-byte affiliation set described above. No GATE area creation support or UseGateEffect approximation was added in this phase.

Nine gate helper/predicate tests and13 closest-area/null tests pass (22 combined). The earlier closest-area integrated verification passed66 tests with unchanged source hashes.

## Corrected bulk casting metadata

Original bytecode and complete original-JAR call-site inspection distinguish mandatory empty-cell `fyF.f -> fyP.cwU` from path option `fyF.c -> fyP.cwN`. The only external consumer of fyF.c is fcO, which passes cwN as the sixth argument to static fcj path validation. ePI instead uses that overload default false. No empty-cell consumer uses cwN. `FindNativeCastingFlagConsumers.java` reproduces that call-site evidence.

`ExportNativeSpellEligibility.java` exports all 4,143 installed definitions, baseline and 800 conditional tables. The primary casting exporter/catalog now set `free_cell=cwU` and preserve `path_option=cwN` separately, together with `diagonal=cwT`, `linear_path=cwV`, `allow_self=cwE`, raw definition `forbid_QI_P`, casting criterion text and native parsed-criterion presence. The latter two distinguish native null parse results from nonempty raw text. The consumer retains explicit level-zero sourcing and selects all table flags together.

The correction changes 182 baseline and 18 conditional empty-cell flags. Structural comparison against the pre-import backup confirms every existing cost, range, root tree, category, protected field, conditional order and criterion remains identical. The separate level-zero exporter/catalog applies the same contract to 813 scoped definitions (21 baseline and 13 conditional empty-cell corrections). This is a local data/code correction; no service or protocol deployment was performed.

The runtime adapter now supplies the area creation affiliation callback. `faV.j(PV)` copies actual live bcM only for native eGj (bav20); all other verified owner PVs preserve constructor ebh=-1. The adapter uses explicit current fighter affiliation, or the documented ordinary fcb/eGj creation team's live value behind the exact ordinary roster authority. It does not substitute obstacle bcN or copy a nonfighter area's captured affiliation. Unknown type, non-null unknown identity, missing fighter affiliation and invalid signed byte fail explicitly. Five pure adapter tests pass. Casting range/cost tests pass7 and metadata/class-initialization tests pass9; the latter process exited normally after reporting OK.
