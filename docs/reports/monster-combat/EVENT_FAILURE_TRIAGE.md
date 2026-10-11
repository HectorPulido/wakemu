# Event and amount regression triage

The October 10 read-only discovery reported four failures investigated here. These failures expose conflicts between historical expectations and the current source-backed contracts. The original assertions have been preserved. No production implementation was changed. Proposed expectation changes were saved privately for review and reversed when Hector requested caution; the failures remain visible. Independent native verification is required before deciding whether code or tests must change.

## Armor: local delivery versus global delivery

`test_armor_real_lifecycle_passive_and_post_application_failure_rollback` expected eight observations. The runtime emitted sixteen: local caster/target channels 10/1, 20/2, 30/3, 40/4, followed in each phase by global channels 11, 21, 31, 41 delivered to both registered fighters. These are separate manager deliveries, not repeated armor application.

`combat_ordinary_events.py` implements `Qe.L` local caster-before-target delivery and subsequent `eZR.L` / `PN.bab().m(caster)` global iteration. The contract is documented in [native area event managers](../combat-inventory/native-area-event-manager-contract-20261007.md) and [summon lifecycle](../combat-inventory/native-class-summon-lifecycle-contract-20261007.md). `ProbeNativeGlobalPVIterator.java` exercises the original iterator. The proposed repair would check the exact complete sequence of channel/manager pairs, verifies exactly the two expected recipients, and retains its single-UID, armor delta, source immutability and rollback assertions.

## Displacement: nested child lifecycle

`test_original_movement_listener_activates_and_removal_stops_reaction` captured all replay sources, including the listener's executed child 353390. That child now correctly emits four phases with event mask `(0,)`. The root 326111 still emits the expected displacement masks `(0,185,188)` and activates the reversed listener exactly on channel30.

The proposed repair would separate sources by `generic_effect`, checks the child identity and its four exact manager-channel/mask pairs, and applies the original exact selection trace to the root. Existing strict packet assertions remain: three distinct child running packets, original source/target rebinding, no observer packet for the unsubscribed child, and no further execution after listener removal.

## Maximum amount: implemented -2 transform

The old test expected every `-2` amount to reject even with a forced context. `maximum_calculated_amount` now implements original `eWN.C` offsets92..153: a positive actual triggering value doubles with Java signed-int overflow; absent/nonpositive source leaves literal -2. The later forced context overrides that calculated amount.

The bytecode contract is recorded in [maximum runner amount sources](../combat-inventory/native-maximum-runner-amount-contract-20261007.md). Its older implementation-status paragraphs describe the earlier unsupported state and must not be read as the current implementation. `test_combat_maximum_trigger_transform.py` already checks positive, overflow, null/nonpositive, forcing, live source and identity rejection cases. A proposed additional contract test would explicitly check literal -2, forced7, actual9 becoming18, and rejection of an incomplete supplied source. Existing -1 authority checks remain unchanged.

## Wall: a Qq area has no fighter-facing locator

The wall test expected `BACK` and event29 from an area target. Original `Qq.baB` returns null, unlike fighter `Sl` facing. The runtime therefore correctly supplies FRONT as the no-back localization and omits event29. The source-backed contract is documented in [turn control and area targets](../combat-inventory/native-turn-control-families-20261008.md); `ProbeNativeFacing.java` tests original fighter thresholds independently.

A proposed additional contract test would explicitly assert FRONT and absence of event29 for the wall, and separately verifies BACK for a genuine fighter with direction2. Wall HP arithmetic, area identity, obstacle retention at HP0 and absence of fighter death events are unchanged.

## Independent installed-client evidence (October 10)

This follow-up reads and executes the installed original client, independently of the Python runtime and historical reports. No test assertions were changed. All Java processes used `-Xmx256m`; no services, catalogs or network endpoints were used.

Client artifact: `client/lib/wakfu-client.jar`, SHA-256 `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`.

Evidence is preserved under `.runtime/monster-local-unit-20261010/event-triage/native/`:

- `bytecode.txt`, produced by `javap -c -p eWN Qq eZR` against `client/lib/*`. Original `eWN.C(Qe)` offsets92–153 compare amount to -2, require non-null actual `bbf()`/`eVt.fLP()` and positive source `getValue()`, then apply `iconst_2; imul`. It does not throw an unsupported-transform exception. Original `Qq.baB()` is exactly `aconst_null; areturn`. Original `eZR.L(byte)` calls superclass `Qe.L` first, maps phases1/2/3/4 to11/21/31/41, then visits `PN.bab().m(caster)` and dispatches to each PV manager. This directly confirms that extra global-channel deliveries are a native contract distinct from the local route.
- `eXt.txt`, produced by `javap -c -p eXt`. Original `eXt.fOF()` returns immediately if target `PV.baB()` is null (offsets0–21). Event29 is added only after a non-null `Sl.o` result equals `Sk.boq` (offsets50–64). Thus a Qq area cannot supply the asserted back event through this path. The Python sentinel name FRONT is a representation choice; absence of native back29 is the directly established contract.
- `ProbeNativeGlobalPVIterator.log`: original `ayT` combines segments as `[9,2,-4,-1,9]`; original Trove values have their own order. Probe exits0. It proves segment composition, not fighter filtering or the complete live battle iterator producer.
- `ProbeNativeFacing.log`: original `Sl.o` executes all eight fighter directions, confirming that genuine fighter orientation remains distinct from the null area locator. Probe exits0.
- `ProbeNativeMaximumAmountSource.log`: original `eWN`/PA application confirms literal -1, actual Qe substitution, forced7, and forced0 precedence. Probe exits0. This probe does **not** dynamically exercise -2; the current independent -2 evidence is the installed bytecode above.

Reproduction: use JDK22 `javap -J-Xmx256m -classpath 'client/lib/*' -c -p eWN Qq eZR` and compile the existing `ProbeNativeFacing.java`, `ProbeNativeGlobalPVIterator.java`, `ProbeCombatArithmetic.java`, `ProbeNativeMaximumAmountSource.java` into a private output directory with classpath `client/lib/*`. Run each probe with classpath `PRIVATE_OUTPUT:client/lib/*`. These probes are offline original-class checks, not successful player/mob gameplay certification. The four original failing regression tests remain unchanged and visible pending review.
