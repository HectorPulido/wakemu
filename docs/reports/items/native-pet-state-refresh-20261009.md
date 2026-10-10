# Native pet state refresh

The native pet panel (`bLK`) retains its original item and observes that item's `fvH` instance. Replacing inventory items with authoritative packets 12471 or 13078 does not transfer these observers. As a result, committed feeding XP becomes visible after reconnecting while the open panel continues displaying the old level.

`CaptureAgent` now instruments the two native pet assignment paths on `fnR`: `f(fvH)` (ProtoItem hydration used by 12471 and 13078) and `a(wS)` (binary inventory hydration). `NativePetStateRefresh` looks up the existing local inventory item by UID and updates its original `fvN` through native mutators before attaching that same state instance to the replacement item. Native health, XP, name, timestamps and ancillary fields retain their normal observer notifications. Incoming timestamps are respected, including the zero last-meal projection used by the server when the daily feeding limit is disabled.

Non-pet items and missing local inventory entries retain the original native behavior. Initial client startup without an active context is also unchanged. This patch does not calculate rewards or infer success from chat: the server snapshot remains authoritative.

Build with `bash sniffer/build-capture-agent.sh`. The normal local launcher already builds and loads this agent. The client JVM must be fully closed and relaunched; disconnecting and reconnecting within the same client process does not load a changed premain transformer. No world restart is required for the client hook itself.

Manual acceptance: equip an existing pet, keep its feeding panel open, feed once, and verify immediate XP/level and food count changes. Feed again with the server daily-limit flag disabled and verify another durable reward. Close and reopen inventory, mount/dismount, then reconnect and compare the same values. Attribute scaling remains a separate server responsibility.

## Follow-up: remove/reinsert gap

Feeding removes the prior inventory entry before hydrating its replacement. A registry-only lookup can therefore miss the state retained by an open panel. The refresh helper now remembers authoritative pet state by globally unique item UID using weak references and discards cleared entries. Replacement hydration reuses this state even during the removal gap. A native regression verifies an initial snapshot followed by a replacement with no registered item, preserving identity and updating XP to 50. Weak references do not keep closed panels or removed pets alive.

The native verifier also executes with the actual capture javaagent, explicitly loads transformed `fnR`, and invokes both empty snapshot and binary hydration methods. It verifies object identity, XP, health, name, dates, observer callbacks and the detached-registry case.
