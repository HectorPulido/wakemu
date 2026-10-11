# Ecaflip card and dice passive evidence

This review distinguishes actual transaction assertions from native graph reachability. It does not activate disabled criteria or add gameplay policies.

## Confirmed actual transactions

- **2059**: playing a naturally held card selects its native indexed Racha contribution; without the passive the contribution is seven. The card grant is consumed.
- **5251**: the first actual played card redraws once and retains marker359838; the second consumes the replacement without a second redraw. Canonical retained lookup is necessary: plain400 markers are not group-runner rows.
- **5246**: two naturally held cards from the same native class exercise the once-per-turn reward; both card classes passed. Bounded7939→7941 trace retains359829 then359835 on manager7; the Racha class adds25 beyond the ordinary card7.
- **2080**: actual unplayed optional7949 yields600 TACKLE at actor level200; playing it before the real turn removes that reward. This real positive/negative transaction passed after the shared replay corrections below.
- **7957**: actual turn progression reaches Racha100; a naturally held7944 is then cast, spends the streak, and the conditional postcast modifier grants resistance50. The separately qualified fight-start1003 test also verifies positive DODGE derivation from the actual aptitude sheet, with passive-off and zero-allocation controls.

## Source corrections to earlier scenarios

- **2076/2050**: +50 effects359776/359781 are descendants of native False groups359819/359820. A successful2050 cast is not evidence that this disabled branch ran. Turn/card contributions must be measured separately.
- **2080**:162572 uses999 ratio100 percent of actual actor level. At level200, child371494 coefficient3 therefore gives600 TACKLE, not300. The actual unplayed optional-card grant is required; the played-card negative is checked separately.
- **7958**:361057/361060 are children of state7999 Buena Estrella, not3683 Racha.359750 derives FEROCITY characteristic9 and applies7999 through361064 on1002/1005 or221/222. The actual initial-movement test is negative: it produces no7999 and no bonus. The later equipped-build test below qualifies the positive characteristic-derived branch.359897 remains disabled by its native False criterion.
- **7959**: the published Ecaflip closure contains only plain marker359898. No consumer was found in Python runtime or the existing global condition-call inventory. This bounds the evidence; it does not establish that every original client/server catalog has no parameter-based consumer.

## Verification still pending

Positive7958 FEROCITY/Buena Estrella,7957 DODGE, and5250 actual draw-universe/round-exclusion checks have passed. Owner range_oracle also reports actual7954 healing/turn consumption,7955 postcard target movement and5249 incoming-hit adjacency PASS; see their focused passive module for scope.2068/2080/5250 optional cards were previously drawn and legally cast. The new5250 check additionally validates the actual eligible lottery universe and native weights, without claiming a statistical-frequency test.

Tests: `test_ecaflip_card_passive_semantics` and `test_ecaflip_dice_passive_semantics`, native runtime opt-in. Catalog-heavy execution is serialized through the shared validation agent. No production change follows from a test setup error.

## Shared native trigger-history correction

The actual2080 played-card negative exposed a general replay boundary defect. State7975 listener359737 derives FEROCITY9 through359743 and applies loss359745; its phase221 notification reenters359737 while the original activation remains on the stack. The original Qe.k checks thread-local Qj.b(generic,caster,target) before clone allocation (bytecodes46–68), pushes Qj.a around execution (377–393), and pops Qj.bcm afterward (498–507). Existing Python history used the correct triple but kept it on each NativeEventReplay instance, allowing nested newly constructed runtimes to miss the active key. It now uses an immutable ContextVar set shared across nested replay instances. The independent immediate-tree recursion guard remains intact. Focused replay and actual2080 passed; no deployment claim is made here.

The real continuation also demonstrated two further integration boundaries: triggered Qe.k clones require their own immediate-tree ancestry (the shared Qj triple guard still suppresses same-triple reentry, and a context-local128 activation-depth bound remains); and a notifying retained-stat source may be removed by its own L3 listener before the final payload refresh.359737 explicitly removes359745 through359741 before recalculating it. The consumer now refreshes only a still-registered row, without recreating the released runner. Actual2080 positive/negative passed. The replay module passed16 tests; the affected stat/retention gate passed66 tests, the prior-class gate passed43 tests, and the AI gate passed38 tests. Subsequent cast-context changes have a separate rerun queued.

## Remaining7958 prerequisite experiment

The positive setup now uses only active2049 Batalla, normal Ready, legal casts and actual turn changes. Its enabled success branches359810/359811 or412837/412838 add20 FEROCITY9. Original ffw declares FEROCITY bounds−1000..1000 and events222/221; this is not a100-capped characteristic.359750 derives the excess above100 into7999, whose361057/361060 children select damage/healing at coefficient0.5. The regression records numeric changes around the qualifying actual cast and retains the disabled359897 negative assertion. The attempted actual sequence did not reach the prerequisite: both equipped variants left characteristic9 at3 and state7999 absent after legal casts. This is not a positive acceptance result and does not establish a production defect. A bounded single-cast diagnostic now records the gain branch and native current/minimum/maximum snapshot before deciding whether the fixture can lawfully reach the prerequisite.

Reproduce the source declarations with `javap -classpath 'client/lib/*' -c -p ffw eYn`. The global7959 scan is reproducible with `python server/tools/inventory_native_reference_consumers.py 7959 359898 --output /tmp/ecaflip-7959-global-consumers.json` under the established read-only database environment. It scans all published indexed records, emits exact numeric/text structural occurrences and lists unindexed documents separately. A numeric occurrence in a different namespace, such as state7959, is not automatically a consumer of passive7959.

## Bounded global consumer scan for7959

The read-only scan completed against published revision `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`: 1,227,366 indexed records, 31 matching records. Exact359898 occurrences were spell-root/closure references and the native preflight null-exclusion reference list; none was a condition or effect-parameter consumer. Numeric7959 occurrences include the separate state namespace and unrelated recipe/identifier fields and do not establish passive behavior. This strengthens the marker-only classification within indexed gameplay data. The tool separately lists 5,832 unindexed documents; it does not claim to have parsed those documents or recovered an unavailable original server implementation. Private output: `.runtime/combat-review-20261010/ecaflip-7959-global-consumers.json`.

##7958 positive-route limitation after actual casts

The initial Batalla experiment used the ordinary injured fixture (`hp=60`) against a full-health target. Its native success condition (`random100 + casterHPpct - targetHPpct >=50`) selected only the failure branch162490=false/169494=true. A test-only fresh-full-health option now supplies the normal maximum before character/Actor/native snapshot construction; it does not write resources after Ready and defaults remain unchanged. With that option, actual success359810 executes (caster7,target−7), but observed caster characteristic9 cycles3/23/43 and7999 remains absent. The native gain definition has duration2 on the caster clock. These casts do not establish a value above100, so the positive7958 prerequisite remains unverified. No production defect, dormant declaration, or100% passive acceptance is inferred from this unsuccessful experiment. The scenario is now named `test_actual_battle_gain_below_threshold_does_not_create_good_star`: it asserts a real enabled gain branch and absence of7999 below100, rather than requiring a threshold this fixture never reaches. Its focused rerun passed1/1 (15.830s), covering both equipped variants; positive7958 acceptance remains unverified. The accepted initial-movement negative is separate.


## Remaining semantic qualification — current focused run

Three additional production-runtime scenarios are frozen in
`test_ecaflip_dice_passive_semantics.py` and delegated for serial validation.
They do not modify production handlers or inject characteristics/states.

- **7957 / positive DODGE:** an actual level200 aptitude sheet allocates native
  bonus19 (six DODGE per point). With and without the passive, the test captures
  pre-Ready PA, runs production fight-start1003, and observes913/176 execution
  with the actual DODGE-derived child level and resulting characteristic8.
- **7958 / positive Buena Estrella:** a complete owned equipment sheet uses
  normal published gear in ten distinct native slots plus legitimate Luck
  bonus9 allocation20. Native equipment validation and `effective_character`
  run before actor snapshots and Ready. The intended native characteristic9
  is114; actual movement1005 must produce state7999 at the excess above100.
  Passive-off/on controls then compare damage48 versus healing114 conversion.
  This uses neither the disabled359897 branch nor invalid cross-turn Batalla
  accumulation. Native characteristic9 is distinct from critical-chance UI
  presentation/clamping.
- **5250 / distribution and turn:** the actual eXR lottery is observed without
  changing its RNG or candidate criteria. Ready compares the optional7973
  carrier's membership and native equal100 weights with passive-off/on.
  Real turn/end/ACK progression changes periodic7961 parity; a normal owned
 2060 cast then verifies actual autoplay lottery exclusions and one selection
  per draw. This qualifies the source-defined distribution, rather than
  estimating probability from a few lucky hands.

All three scenarios have delegated passing results. Existing negative7958 Batalla
and initial-movement regressions remain intact. No manual-ready claim follows
from these source-derived expectations before their runtime results.


The first delegated run qualifies **7957 positive DODGE** and **5250 exact
lottery/round exclusions**. The7958 equipped scenario correctly rejected two
items containing unrelated unsupported equipment effects before actor creation.
Its fixture now uses native Charon cape31319 and Grugalorasalar helmet23975,
whose equipment effects are supported flat characteristics; the remaining
production equipment guard is unchanged. Revised7958 runtime validation passed1/1 against pinned published revision
`13c8122abba26ca40757c48df137540a5f0e6defdc6676cde6fd19ac6b84b33d`. The expected equipped characteristic9 is114 (native GoodStar7999
state level14); this state is unrelated to passive spell7999 **Seven**.


## Final focused result

The corrected positive7958 test passed both passive-off/on subcases in one
method, with no skips or errors. Together with the previous six-method run
(only the two superseded equipment subcase setup errors), all six
current dice-passive methods have passing terminal evidence. No production
behavior was changed by this qualification. Native False359897 remains
inactive, and passive7959 remains bounded marker-only evidence.

Frozen test source SHA256:
`e92ef237238db2ac501f6038470f003eba5f2acd80e9e5e3bd3208f32831d5d0`.
This is offline runtime evidence, not a live-world deployment or a guarantee
that every equipment effect is supported. The independent copied-book catalog
patch remains staged and unactivated; see the class-book regression report.

## First-round policy regression follow-up — 2026-10-11

The current authoritative release548e1468… initializes the actual table counter to1 before initial effects. The equipped critical-excess7958 regression passes again: Buena Estrella7999 can already contribute its permanent derived modifier during initialization, so subsequent real movement refreshes the modifier rather than adding a duplicate. The regression checks the actual positive excess, successful361058/361061 execution, positive resulting stat, and the change in source-derived contribution between the old and new state levels. Evidence: `enutrof/ecaflip` serial validation artifact `.runtime/remaining-six-refresh-20261010/ecaflip-dice-final.log` (the7958 method passes; the separate Destiny method was still under correction in that run).

The native Destiny draw criterion359554 permits7973 only when5250 is equipped and the current table is even. All card35954x candidates also require absence of their own card state on the recipient. The corrected draw regression therefore checks parity, owned passive, and per-draw existing state exclusions, including exclusions created by earlier draws within the same2060 action. Its final rerun passed1/1 in `.runtime/remaining-six-refresh-20261010/ecaflip-destiny-final.log` on test source5876ec7c…; the only change since the passing7958 run was this Destiny test correction. These are test-oracle corrections from published criteria; no Ecaflip production mechanic was changed.
