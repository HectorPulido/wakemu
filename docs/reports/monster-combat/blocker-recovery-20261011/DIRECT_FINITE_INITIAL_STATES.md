# Direct finite initial states without a native timeline

The finite initial-state gate was separate from finite child-effect timing. It rejected every positive turn duration before executing a descriptor's initial states, including genuine detached constructors whose native context has no SU.

Native proof, independently traced through the state-specific implementation:

- `eWu.a(PN, PV, short, short, boolean)` stores the supplied construction PN in bfw.
- `eWu.D(Qe)` calls `eZk.a` with that same PN, its caster PV, PL, and packed state ID/level; subsequent `eZk.g(PV)` and `bal()` follow normal carrier application.
- `eZk` overrides `eZR.bbT`. It first resolves the state definition, then returns if bfw is null or `PN.bac()` is null, **before** reading `fyW.guG()` or calling the scheduler. Therefore the generic eZR timing proof alone was insufficient; the state-specific override now supplies the missing proof.
- The existing constructor PN is eZQ/PO, whose bac() is null. Its initialized timer remains Ts.biM, with no invented first fighter or round.
- Realtime duration is independent: `eZk.a` initializes rIY using `fyW.guH()`. Positive realtime duration remains unsupported and rejected.

Evidence: `.runtime/local/state-registration-eWu.txt` (factory and D), `.runtime/local/state-registration-eZk.txt` (factory and bbT), and previously qualified eZQ/PO construction evidence.

The implementation allows a positive turn duration only when `detached_actor_authority(fight, actor)` confirms the actual source-qualified construction scope. A detached lookup alone does not attest an absent SU. Existing strict source/target, descriptor plan, runtime ownership, resistance bypass, protection, and child execution checks remain. Native duration is retained in the carrier and ledger; its timeline stays null and the wire contains the existing no-clock sentinel. Registered ordinary active applications retain their real timers.

Five new tests exercise the real constructor scope, NativeStateHandler, Fight.apply_state, StateLedger, and emitted carrier wire; reject a fake lookup, foreign scope, and positive realtime; and preserve registered active finite-state scheduling. All four original zero-duration tests remain unchanged, including the fake finite-constructor rejection. Combined focused run: nine tests passed, no failures or errors, logged in `.runtime/monster-blocker-recovery-20261011/direct-finite-focused-tests.log`.

This is source readiness, not monster activation. Affected-reference replay and final complete-book validation belong to the coordinator. No services, catalog revisions, or database values were modified.
