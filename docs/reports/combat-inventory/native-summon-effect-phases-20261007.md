# Native eZl307 running-effect phases

## Calculation and identities

The fresh Qe clone has its running-effect UID before L1. Fresh local L1 precedes `n(null)`; `eZR.n` calls `C`, value callbacks (`fRV`) and finally context value transfer. Reactive `Qe.k(source)` instead calculates the clone before L1/L2, as with other runners.

`eZl.C` reserves the **creature UID first**, through `PN.bae().baj()`, into rGF. It then evaluates parameter0 into aSg (the running value), selects level/control/orientation/timeline parameters and builds eHD using signed-short aSg as the creature reference. This descriptor precedes callback/context mutation of the running value. Therefore descriptor reference and subsequent running value are distinct facts: transferring/changing aSg after C must not reinterpret the breed or rebuild the descriptor.

Expected ordinary fresh lifecycle: prepared effect UID → L1 with fresh value0 → C reserves actor UID and builds descriptor → calculation callbacks/context value transfer → native executable/criteria/probability checks → L2 → eZl.c creation/registration → L3/L4 → value callbacks. A reactive clone needs the audited Qe.k ordering, not the fresh ordering reused accidentally.

The current handler allocates creature UID then effect UID during application. Adding events requires a prepared runner and reuse of its effect UID; actor UID reservation belongs to C. Both reservations remain transaction-owned and must roll back together on unsupported later execution. Packet additional data carries actor UID separately from effect UID.

## Events and guards

`eZl.bbx` calls the base implementation (event0) and adds 2130. PK produced-event masks join those IDs. `bbz=true` requires a caster, `bbA=false/bbB=true` select cell application, and common eZR.bbH/bcd/Qe.bbJ gates still apply. The cell target is null; do not invent a recipient actor from the summoned creature before it exists.

Running value after C is the evaluated raw integer parameter0, with signed-short narrowing only for descriptor reference. L1 starts at0. L2/L3/L4 use the current running value; eZl.c does not itself replace it with spawned HP, creature UID or a success count. The current codec's field4 uses specification.reference, so support for callback/context-mutated running values requires an explicit value input while preserving the descriptor reference.

`eZl.c` performs creation only when its descriptor is nonnull and caster is eGj. Missing required actor/descriptor sources must remain explicit unsupported paths in the server. Native eZR execution catches c exceptions, records its internal error flag and still performs parent completion machinery; that is not evidence that the server should accept malformed creation or commit partial state. The verified ordinary eGj/fresh descriptor path avoids those ambiguous cases.

`Qe.a(Qe,boolean)` runs postapplication L3/L4, callbacks and completion; eligibility failure before L2 does not create an actor. eZl.bbF clears descriptor/control fields after parent cleanup and does not unsummon the creature. Retained/subscribed creation still requires a separate central Qf record before the handler's guard can be removed.

## Immediate persistent delivery fixture

Effect reference308267 (family400/eXE) is immediate persistent without subscriptions. Native aTR registration requires `(Ty || bbW) && (aZN || bbW)` plus a resolved owner Qf. With Ty=true, aZN=false and bbW=false, observation registration is false. Its actual retained Qf therefore requires full application **12613**, with eIK=false, rather than observation13497. The existing shared choose_delivery result is correct; assertions expecting13497 for this child need correction based on that explicit contract.

## Proposed common module

Use one prepared Qe runner contract shared by nonnumeric creators: running UID/current value, immutable calculated descriptor, transaction-owned creature UID reservation, source context, common event masks, phase ordering and completion callbacks. The summon builder consumes the descriptor; it must not read a later mutable value as the breed. Local events use the newly completed registered actor authority, while global order and retained clone creation stay explicit until verified. This needs no monster spellcasting or AI implementation.

This investigation changed documentation only. Native evidence is in targeted eZl/Qe/eZR/aTR bytecode dumps under `.runtime/local`. No world, Docker, DB, AI or heavy catalog audit was run.

## Implemented fresh local boundary

`NativeSummonHandler.prepare` now reserves the running-effect UID before L1, forwards native event masks0 and2130 plus produced masks through the shared registered recipient authority, then calculates an immutable descriptor and reserves the distinct creature UID. The runner starts at0 and retains the evaluated raw signed integer after calculation/context transfer. Application consumes its prepared identity, checks eligibility before and after L2, registers the creature during application, and completes L3/L4 and the existing synchronous value observer.

The codec accepts a separate signed `running_value`; its field4 no longer has to equal the immutable signed-short descriptor reference. Source mutation owner307 is `Qe`, whose trigger amount mutation is a native no-op. Direct applications without an event provider retain the same identity/descriptor/context separation. Retained/subscribed applications and reactive clones without a fresh prepared identity remain explicit unsupported boundaries; this change provides no monster spellcasting or AI.

Validation: changed Python modules compile. Automated regression verification is delegated to the testing agent; service processes were not touched.
