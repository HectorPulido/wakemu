# Native family 1099: cosmetic death script

Family 1099 changes the target fighter's client death-presentation script. Native `eVi` selects `eWE`; the actual shared class ancestry is cosmetic and conditional. This is not a missing damage, summon AI or monster-spell mechanism, and structural inclusion under each class innate does not imply that every class spell currently fails.

## Native contract

`eWE.C` evaluates only parameter 0 using native integer evaluation. It does not call `eZR.n`, so an execution-context forced amount must not replace the script ID. Application on an actual `eGj` calls `PI(aSg)`, a direct assignment to integer field `pGU`. Null targets call `fRS`; non-fighter `PV` targets return without assignment. These branches must not fabricate an actor.

`eWE.bbR` resets an actual fighter's script to **-1**, without restoring the previous script or recomputing overlapping retained assignments. Thus removing an older retained death-script effect still resets the field even after a later script assignment. The original `eGj` constructor initializes this field to -1. Unverified/restored actors retain unknown authority until populated.

Actual prototype methods report events `[0]`, `bbz=false`, `bbA=true`, `bbB=false`, and `bcd=true`. The latter allows a corpse target; the handler does not add an unrelated living-target restriction.

`ProbeNativeDeathScript.java` invokes original `eWE.c`, original concrete `bje` inherited `PI`, and original `eWE.bbR` offline. Signed boundaries, -1, zero, positive script IDs and removal after an overwritten assignment passed. Its `Unsafe` allocation isolates direct field mutation; it does not exercise complete actor construction, guards or GUI rendering. Abstract non-fighter classes could not be instantiated by that fixture; their no-op branch is bytecode evidence only, not an executed native probe.

## Structural reachability

The 38 class-linked effects sit under shared group 185727. Its guard requires turn index greater than 3, the relevant ally/summon count condition, world-property/random policy, and expired KO time or PvP. Each child additionally requires `HasActiveCosmeticId(5, cosmeticID)`. The full native compact graph has 54 instances of family 1099; other instances do not establish class gameplay reachability.

The new `NativeDeathScriptHandler` handles proven non-null actual fighter targets with shared lifecycle ordering: one UID, L1, parameter evaluation, mutable L2, live guard validation, assignment/retained ownership, completed `aVo`/opcode12613 delivery, L3/L4 and final runner observation. Removal produces opcode13560 and native reset semantics. Unknown/non-fighter/null-target delivery is rejected explicitly because area-manager registration/delivery has a separate contract.

`Actor.native_death_script_id` preserves authoritative state in the ordinary actor model. The verified fresh snapshot install initializes it to constructor -1 before passive effects. The handler overwrites it without pretending unknown previous data is needed for an assignment.

## Limits and evidence

Tests cover signed assignments on dead actors, reset rather than restoration, live L2 changes, distinct L3 runner observation, L2 cancellation, ignored forced-context/unused parameter pairs, unsupported target identity rejection and prepared-runner cleanup. Automated test results and factory integration are recorded separately by the validation owner.

[Machine-readable evidence](native-death-script-1099-review-20261007.json) preserves native probe results, cosmetic references, guard ancestry and selected source hashes. Source hashes are captured after implementation; a whole-checkout frozen pre/post manifest is not claimed. The cosmetic inventory producer, actual activation of each guard, non-fighter delivery and GUI death-script execution remain unverified.


## Factory integration and shared cancellation correction

The production factory registers family 1099, uses the native timing/stat context, attaches ordinary lifecycle events, and retains the effect through the central manager. Shared stat removal dispatches family `eWE` to native reset/removal handling. Removal validates its exact codec before mutating the actor or owned identity.

A review found a broader cancellation defect: `NativeRetainedRuntime.wrap` preserved the runner-value attestation but dropped `cancel_prepared`. The dispatcher therefore could not clean prepared runner scopes when a retained effect failed its criterion or probability before application. The wrapper now forwards any callable cleanup method generically, covering eWE and the other prepared handlers.

Two additional integration regressions use the real factory, original eWE definition metadata, production native timing and actual ordinary lifecycle events. They exercise central manager registration, shared UID/event ordering, exact opcode13560 removal, and wrapper cleanup on criterion, probability and criterion-error rejection. Activation is explicitly synthetic: the original cosmetic criterion is preserved in the installed catalog and asserted by the test, while the isolated unit substitutes a declared activation condition. These tests do not attest account cosmetics, actual KO/PvP ancestry or client death rendering.

Native `HasActiveCosmeticId` is `eLX`: it reads only the caster, resolves its account/character IDs, converts the numeric type with `fn.ce`, and searches the active cosmetic list returned by `eSP.a` for matching `fC.AK`. The current combat condition provider lacks that account cosmetic producer; absence must remain unknown rather than becoming an invented false or true result. No cosmetic predicate or account state was changed by this implementation.
