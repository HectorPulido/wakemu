# Native activation and triggering-runner predicates

## Shared contract

The installed original bytecode defines four Boolean predicates. They evaluate the current activation and triggering runner independently; neither spell identity nor critical state is inferred from the listener, selected plan, or display metadata.

- `eNh` / `IsActivatedByElement(long)`: constructor narrows its constant argument to Java `int`. Fourth-context `eII.aS` resolves the fight; absent `fbX.bah()` returns false. The actual activation must implement `fcS`. Its `e(fyU.tyc)` stasis flag overrides `PZ.baP()` and matches native `eVg.rpk.aKg() == 6`.
- `eNi` / `IsActivatedBySpell()` or `(long)`: absent current activation returns false. Default argument `-1` tests actual `PZ.baR() != null`; other arguments compare actual `PZ.ayn()`, with Java integer narrowing.
- `ePd` / `IsTriggeringEffectCritical()`: third-context `eII.aU` resolves `eZR.fSd()` first, then the current `eVt.fLP()` pointer. Missing source or definition returns false. Actual source `eVn.dd(1L)` tests definition variant bit 1.
- `ePc` / `IsTriggeringEffectBlocked()`: same source selection; missing source returns false. The actual runner's `cYh()` must equal byte 7. Unknown status is not treated as false.

The condition parser accepts their native Boolean signatures only. Dynamic/string constructor arguments, excess arguments, and numeric comparisons are rejected.

## Producers and bulk metadata

The existing owned-cast `active_spell_scope` publishes current activation identity and its evaluated `fyG` container and restores both on exit. These predicates use that producer rather than a guessed spell ID from the triggering effect.

`ExportNativeSpellActivation.java` loads installed `aNr/bPK` records offline and exports actual `fyF.gtQ()` and `fyF.g(fyU.tyc)` for **4,143 spells** into `server/protocol/native-spell-activation.json`. Stasis is exported independently of element. This is read-only native data extraction; no database, service, or container was changed.

Event source descriptors carry actual definition presence/variant and optional observed execution status or the proven `status == 7` predicate. `OrdinaryDamageEvents` publishes the real block outcome after native damage evaluation; its level-one phase precedes that roll. Native `eXt` only sets `fc(7)` when its real block roll succeeds. Other runners keep unknown status unless their producer proves it, so their blocked predicate remains an explicit unsupported context rather than invented false.

The sealed synthetic collision definition publishes its actual variant 0. Its negative reference does not grant generic synthetic source authority.

## Validation

- Offline `ProbeNativeActivationPredicates`: **PASS** against original `eNh/eNi/ePd/ePc`. Covers absent activation/source, normal versus stasis element, null activation container versus explicit ID, long-to-int narrowing, variants 0/1/2/3/-1, and statuses -1/0/7/8.
- `PYTHONPATH=server:server/tests python3 -m unittest test_combat_activation_conditions test_combat_conditions test_combat_collision_resource`: **52 tests passed**, 0.131 seconds. Nine new tests cover strict signatures, missing authority, metadata propagation, current activation nesting/restoration, native bulk normal/stasis metadata and existing collision compatibility.

These checks establish the shared predicates and their explicit producers. They do not certify every class spell, arbitrary non-spell activation, unobserved runner execution status, or gameplay behavior in a running world.
