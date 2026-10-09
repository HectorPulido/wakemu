# eWN lifecycle and delivery: remaining shared gaps

This read-only review follows the minimal amount-source correction. Its 22 passing focused tests verify that correction and existing arithmetic; they do not accredit complete eWN semantics, event ordering or client delivery. No Python or catalog changes were made here.

## Exact native contracts

`eWN.bbx` calls base Qe event construction, which inserts event 0. If its characteristic is an ffw with fZv true, it adds that characteristic's actual fZr event. No generic resource event ID can replace this producer.

`eWN.C(Qe)` selects actual definition parameters at native fRR level, writes applyCurrent/removeCurrent booleans and aSg amount, and handles its separate -2 context-source transform. `eZR.n(Qe)` executes C, then fRV context callbacks, then actual forced-value context if fLR. Thus callbacks and context follow C rather than application-time -1 substitution.

The inherited Qe execution path emits phase 1 before calculation, invokes n, and phase 2 before application. `eZR.a(Qe,boolean)` calls c; sets applied state; invokes PR notification only when rIW is false; resets rIW; then calls inherited Qe.a. That inherited method emits phases 3 and 4 through dr, then bbK and aX lifecycle accounting. Qe.L has separate routing for phases 1, 2, 3 and 4; equivalent values do not establish equivalent event recipients or suppression.

In eWN.c, application-time -1 with an actual Qe copies its current getValue. PA raw maximum changes independently of effective maximum; server-side bbs rewrites aSg to actual raw delta and rCn to effective delta. Current-resource application uses rCn, not requested/raw delta. The native AdditionalDatas writer encodes applyCurrent, removeCurrent and effective delta through ij; removal uses these distinct values.

The actual eWN owner methods return bbz=false, bbA=true, bbB=false. The exported registration-owner catalog confirms static and prototype-clone values for family 41. Existing NativeRunnerAmount supports owner-specific eWN mutation and sticky notification suppression when mutation reaches zero. That object must be attached to the actual running UID throughout synchronous event processing; application must read its current value after phase 2 and expose actual applied amount to phases 3/4 and eYz transfer callbacks.

## Current implementation gaps

The maximum handler still performs calculation/application in one call. It has no prepare method, prepared UID table, mutable current runner table, phase-1 or phase-2 delivery, phase-3/4 delivery, or final runner observer. Runtime prepare dispatch currently routes summon, state, armor, displacement, movement-link, loss, current-stat, healing and damage; eWN families 20/31/41/191 are absent. UID allocation happens after resource arithmetic, so no actual source UID exists for earlier listener phases.

The minimal amount resolver reads an actual scoped triggering source for -1, but does not make the maximum runner itself a mutable event source. A maximum runner targeted by a phase-2 eZL modifier therefore still lacks its own live NativeRunnerAmount. The current handler emits its application packet unconditionally and cannot preserve sticky rIW suppression/reset after notification. It stores reversible raw/effective deltas, but no final observer reports its final running value to eYz. Merely adding events around the existing arithmetic would leave these source and ordering contracts incomplete.

Definition flags, source/container identity, characteristic event IDs, target PA presence, phase recipient/suppression rules, actual timer and registration must be validated before event delivery. Inactive/missing/frozen characteristic branches and explicit -2 context-source behavior need native tests; the minimal fix continues to reject -2. Prepared resources must be cleaned on every no-effect/error path without leaking running sources.

## Delivery contract and existing wrapper

Native `cvX` opcode is 12613; native `cvY` opcode is 13497. aVo is the complete/evaluated action and aTR is the observation action in existing actual-client action probes. Consequently, “aTR12613” should not be used as a verified mapping. The Python `owned_effect_delivery` represents 12613 by adding its explicit false eIK byte to the owned application layout, retaining evaluated amount without a second gameplay execution.

The maximum handler currently appends 13497 directly. However, `NativeRetainedRuntime.route_owned_deliveries` can convert retained matching packets to 12613 according to original owner and visibility policy. It checks actual retained manager, family, generic reference and UID before selecting the wrapper. This means a blanket claim that every maximum packet uses the wrong opcode would be unsupported. The gaps are handler-level notification suppression and complete integration/selection validation, including Ty=false and nonretained paths not covered by this retained rewrite.

Both wrappers must preserve UID, generic definition, characteristic target, timing, raw applied amount, effective delta and the booleans. Actual client decode/apply probes are needed to show that each policy-selected wrapper yields the intended maxima once, and that observer delivery does not reapply it. Current arithmetic/unit tests do not prove this.

## Concrete next implementation and verification

Use the existing current-stat shared prepare/apply lifecycle as the structural reference, with eWN-specific calculation, characteristic events, mutable value, raw/effective application and AdditionalDatas. Wire eWN preparation explicitly, keep the same UID across all phases, read live amount after synchronous mutations, register actual applied retention, route policy-selected delivery, reset notification suppression at the proven boundary, and report final amount after phase 4. This should be one shared family implementation, not individual spell repairs.

Required regressions cover phase sequence and values, correct recipient/event IDs, phase-2 mutation, zero notification suppression, raw versus effective delta under percentage/cap/minimum, -1 actual application source, -2 fLP source semantics, final eYz observer, timers/removal and exception cleanup. Add actual-client complete/observation packet probes with expected maximum before/after. Keep client verification pending until an integrated client test establishes receipt and behavior.

Evidence was read using `javap -classpath 'client/lib/*' -c -p`: `/tmp/wakemu-{eWN,eZR}-lifecycle.txt`, `/tmp/wakemu-Qe-maximum-lifecycle.txt`, `/tmp/wakemu-{aTR,aVo,cvX,cvY}-maximum.txt`. Existing native probes `ProbeNativeMaximumAmountSource`, `ProbeNativeCharacteristicMaximum`, `ProbeNativeOrientationDelivery` and state delivery probes establish narrower contracts; none is presented here as complete eWN lifecycle coverage.

## Implementation preparation during Ready freeze

A small actual eVi prototype exporter was run privately from `/tmp/ExportNativeMaximumEvents.java`. Proven fixed characteristics and bbx events are: family20/stat1 `[0,3]`, family31/stat2 `[0,53]`, family41/stat3 `[0,63]`, family191/stat4 `[0,69]`; every runner is eWN with bbA=true/bbB=false. Private output: `.runtime/combat-review-20261007/maximum-lifecycle/native-maximum-events.json`. No runtime source was modified during the freeze.

The planned shared implementation separates C/context from application-time -1 resolution, because a phase-2 listener may replace the current runner amount. It uses NativeRunnerAmount and the existing generic event lifecycle, with one UID and live resource snapshots after phase 2. Qe.bbJ bytecode also rechecks current target guards after phase 2; the application must revalidate supplied authoritative execution context before mutation. Raw applied delta and effective delta stay separate, while post-phase final aSg and final observer delivery reflect actual native mutations.

The dispatcher currently calls prepare before checking criteria/probability and has no generic cancellation hook. Skipped criteria/probability therefore require explicit prepared-runner cleanup coordination; a handler-only patch cannot claim those cancellation paths are complete. Preparation may remain transaction-local, but that is not a substitute for proving cleanup when a dispatcher is reused. Source ownership and the final factory wiring remain coordinated with root.

## Implemented shared eWN lifecycle

After Ready54 released its source freeze, the maximum handler, factory and dispatcher were updated. The four eWN resource families share a prepared UID and NativeRunnerAmount, phase 1 before C/context, phase 2 with synchronous mutation, live guard revalidation and live resource snapshot application, notification suppression/reset, retained registration, phases 3/4 and final runner-value observer. Native fixed characteristic events are exported in `native-maximum-resource-events.json`; `ExportNativeMaximumEvents.java` reads actual eVi prototypes rather than assigning spell-specific events. Original targets/masks contribute their explicit additional events.

The dispatcher now owns a nested execution-local list of prepared invocations and releases them through an optional handler `cancel_prepared` method in its finally boundary. Criteria rejection, probability rejection and post-preparation exceptions therefore release eWN prepared memory. Handlers without this optional method remain unchanged. UID reservation and already-delivered phase-1 events are not rewound. Preparation failures also clean their own partial runner state. Ordinary transaction rollback remains responsible for reversing failed preview mutations.

Six new lifecycle regressions plus the previous source/arithmetic/reduction suites pass: 28 tests, 0.557 seconds. They verify phase sequence/one UID/final observer, phase-2 value replacement changing application, cancellation after phase 2 before maximum/current mutation, zero notification suppression with post phases, distinct raw/effective deltas under percentage maxima, and criteria/probability/exception cleanup without UID rewind. Command: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python -m unittest server.tests.test_combat_maximum_lifecycle server.tests.test_combat_maximum_amount_source server.tests.test_combat_maximum_resource server.tests.test_combat_maximum_reduction server.tests.test_combat_parameter_maximum`.

Broader integrated factory/retained-event validation and actual-client wrapper decode/apply remain pending. The phase-2 revalidation uses supplied execution/guard authority; it does not synthesize native removed-state facts from team or HP. The -2 calculation transform still rejects explicitly because its separate actual fLP source producer is unavailable. Retained post-phase amount can change the stored raw removal value, matching native mutable aSg; effective delta remains separately retained. These regression results are not complete client or per-spell semantic accreditation.
