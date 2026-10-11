# Finite child effects under native descriptor initial states

Representative proposed:2555 LinShi; historical active-turn timing cluster26. Recovery is not claimed until actual native replay succeeds.

## Source authority

Bytecode captured read-only from `client/lib/wakfu-client.jar` under `.runtime/monster-blocked-recovery-20261011/`:

- `eGj` constructor creates `pGD = new eZQ(this,3)`.
- `bje.aQc` invokes inherited `big.a(eGH)` after descriptor hydration.
- `big.a(eGH)` passes that actual `pGD` context to `eWu.a(PN,PV,short,short,bool)` for each `cle` initial state; caster and target are SELF.
- `eZQ` extends `PO` and does not override `bac`. `PO.bac()` returns null.
- `eZR.bbT()` offsets23–35 explicitly returns if `PN.bac()` is null, before computing or installing the turn expiration timer.
- The runner retains its native `Ty` retention decision independently. Its untouched `rIX` starts as `Ts.biM`.

Consequently a positive-duration eVy child of an indefinite descriptor state can execute and remain owned without a turn timer during this exact constructor boundary. No first-turn timer or deferred scheduling should be invented. A preliminary SU-only reading suggested constructor scheduling could use index-1, but the full PN producer chain disproved that for this actual eZQ constructor; that hypothesis was discarded before implementation.

## Narrow implementation

`NativeEffectTimingProvider.stat` skips finite turn timer construction only when the existing `constructor_stat_context` proves actual fight-scoped detached SELF. Definition parsing and unsupported-delay rejection still run first; positive real-time timers remain unsupported. Container identity is still resolved. Ordinary registered active execution still calls the unchanged native timeline/scheduler. No finite state-carrier guard was relaxed.

New focused tests cover retention and sentinel payload, no roster insertion, missing scope, cross-actor target, delayed effect rejection, forged state-container rejection, and ordinary active finite-child scheduling. Existing tests were not edited. An eager constructor probe initially affected the existing mode0 minimal fixture; source was corrected to probe only the positive-duration mode2 branch, preserving zero/indefinite paths.

The final focused command and count are recorded in `.runtime/monster-blocked-recovery-20261011/maximum-tests.json` and `maximum-tests-final.log`. No service or database mutation occurred. Full heavyweight matrices remain deferred to final verification.
