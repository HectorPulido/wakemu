# Native Qq area guard provenance

## One native field, three guards

`Qq.baG()` returns `bhi`; `Qq.baK()` calls `baG()`; `Qq.baF()` returns its inverse. Area classes faV/faY/faZ do not override these methods. These flags describe the area object's lifecycle, not fighter HP.

The exact-owner jar field audit found five writes to `Qq.bhi`: both Qq constructors initialize false; `aWs` and `aWr` reset false; `b(PV)` sets true. `Qq.b` first clears its owner relationship and calls `baE`, then sets the flag. `faV.b(PV)` emits event10014 before delegating to Qq.b. Cloning `Qq.a(Qt)` obtains a fresh/reset instance and copies configuration without copying bhi.

Collection membership is insufficient authority. Removing a record through `Qs.b` does not imply `Qq.b` ran. `remove_owned_hour_area` intentionally implements only Qs removal and can retain the actual Qf object after unregistering. A retired row may therefore retain false.

## Proposed general producer and consumers

Store an explicit checkpointed `native_qq_bhi` boolean on each newly constructed faY/faZ row, with provenance identifying the verified construction/reset path. Initialize false only in the actual creation producer. Preserve the value across Qs unregister, spatial removal and retired-manager retention. Update true only in an implemented Qq.b owner-callback producer, after its native cleanup ordering. No field reconstruction from active/retired membership is valid; old/restored rows without provenance remain unknown. `fight_checkpoint_store.snapshot` already serializes plain row fields, so this needs no DB schema change.

Expose baG/baK from that boolean and baF from its inverse through an area PV authority distinct from fighter authority. Clone `eZR.i` checks the retained original target's baG before criteria and probability; `Qe.bbJ` checks baK before and after L2. Apply native bypass behavior when proved. Fighter HP/death registration remains fighter-only. Local event delivery itself is not suppressed simply because bhi is true: Qq.a still forwards to its actual Qf.

## PV and Qf are separate boundaries

An area can be a valid registered PV without a running-effect Qf. `faV.bax()` creates a Qf only with area property12; otherwise the inherited result may be null. `Qq.a(BitSet,Qe,byte)` skips Qf forwarding when null, then continues the area's own trigger predicate. That is a valid native result rather than an absent actor.

For state application, `eWu.bbH()` explicitly returns false when a nonnull target PV has null `bax()`. `eWu.c(Qe,boolean)` also marks unsuccessful execution and returns on missing/null-Qf target. A state must not create a synthetic ledger on such an area.

The own-trigger phase must not be silently discarded: `Qq.bcx()` defaults to 1, so local L1 can activate it when event IDs intersect entry masks and other native guards pass. For a registered null-Qf area whose entry masks are provably disjoint from the produced events, local replay has no receiver. If masks overlap, use a separately audited area-trigger path or retain explicit rejection. The area's own-trigger contract is distinct from replaying subscribed Qf entries.

The separate PV/null-Qf boundary is now implemented: `registered_area_pv` verifies the owned row against its installed prototype, including property12 and actual ledger presence; generic phases distinguish PV recipients from Qf listener managers. A null-Qf area's local phase skips subscribed replay only when its own entry-mask route cannot activate. Overlapping own entry events remain explicitly unsupported. The eWu handler returns false before L2/application and consumes its prepared runner when the actual target has null Qf. Tests cover local recipient order, null-Qf delivery, metadata mismatches, own-entry overlap and fresh applicator cleanup. Corpse/removed guard changes remain owned by the parent agent. Source evidence is in offline javap/ASM audits under `.runtime/local/owner-area-*` and `.runtime/local/guard-area-eWu.txt`. No world, Docker, DB or AI operations were performed.
