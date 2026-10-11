# Native HP maximum reduction (family 21)

This is an offline implementation and source audit, not monster activation.

The installed registry resolves effect 21 to `eWO` with `PC` ID 1 (HP), the same runner used by maximum AP/MP/WP reduction. It is not a damage or healing runner. Previously the reduction adapter registered only families 56, 57 and 192; applying its effective-current fallback to HP would lose the original expandable raw current and native event lifecycle.

## Representative and shared scope

Escorpico 2967 is native level 115 with spells 4229 (`content.3.4229`, Pellízcame) and 4230 (`content.3.4230`, Pikoletazo). Their descriptions are respectively `content.4.4229`: “Pellizca con sus pinzas al adversario en las piernas.” and `content.4.4230`: “Da un golpe salvador con la cola.” Names do not determine effect semantics.

Its sealed dependency closure contains effects 111893 and 111897: family 21, execution mode 2, selector `fcE` mask 9, empty criterion, parameters `[250,0,-1,0,0,0,0,0]`. Native interpretation is amount 250, default chance 100 (negative chance parameter), and **both current flags false**. Maximum changes may still change effective HP while preserving raw HP. Do not replace this with direct damage.

The historical family-coverage inventory reports ten references with missing family 21: 2519, 2520, 2521, 2648, 2967, 2990, 3399, 4966, 5418 and 5551. This is a structural scope, not ten newly qualified monsters.

## Exact native behavior

`eWO.C` evaluates amount and optional chance, restore-current and reduce-current flags. Amount -1 takes the triggering value; -2 takes actual current HP. `eWO.fb` caps requested reduction to effective maximum minus one when `PK.aZD != 2`. This protects the maximum, **not current life**: the actual native oracle reaches current HP zero with maximum HP one.

`eWO.fNL` shifts minimum first, maximum second, then optionally subtracts the amount remaining after the effective current movement caused by bound changes. `bbR` reverses maximum first, minimum second, then optionally restores current by the retained requested amount. Negative amounts, hidden raw HP and Java integer arithmetic matter.

The original HP runner declares event 4. A changed effective current adds event **2**, independently of the sign; a zero applied runner amount removes event 4. These are Qe source events, not damage/healing events. An earlier bytecode-reading hypothesis of event 3 was rejected by execution of the actual installed runner.

## Implementation and validation

`combat_hp_maximum_reduction.py` reuses the existing HP raw authority and its min/max/current setters. It adds an exact family-21 handler with native prepare/apply/post phases, chance, amount mutation, retained payload and owned removal. The runtime registers family 21 separately; original maximum-resource reduction handlers remain unchanged. Missing raw HP authority and unknown definition modes fail closed.

The actual Java oracle `sniffer/java/ProbeNativeHPMaximumReduction.java` executes seven installed-runner application/removal cases, including mode-2 bypass, disabled current flags, negative amounts and current zero. Private output: `.runtime/monster-blocker-recovery-20261011/hp-maximum-reduction/native.json`.

Focused validation: **25 tests pass** (14 new HP tests, including factory dispatch, and 11 original maximum-reduction/lifecycle tests). New tests cover exact oracle outcomes, hidden raw HP, frozen current, missing authority, chance failure, phase order, retained removal, synchronous amount mutation and phase-error cleanup. Original assertions were not changed. The four original maximum-event metadata prototypes were reproduced using the existing tiny `ExportNativeMaximumEvents.java` exporter for the offline fixture; no catalog was published.

The separate new full-factory test now passes against the exact existing native direct-target and fixed-current registry documents, without mocked catalog authority. The test checks family-21 dispatch and isolation of the other actor; it is **not** full monster qualification. An additional regression preserves literal -1 for a genuinely fresh null triggering Qe and reuses the existing strict actual-Qe amount provider for triggered applications. Independent validation passed the final 14 new tests with current stable hashes; the unaffected 11 original tests passed in the preceding gate and were not repeated. Full monster level/book/initialization/AI qualification remains pending. Areas require their own native PA authority; this adapter currently admits registered or genuinely detached actors only.
