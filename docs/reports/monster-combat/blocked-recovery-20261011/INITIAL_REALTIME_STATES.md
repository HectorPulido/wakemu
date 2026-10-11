# Initial realtime state dependency audit

This offline audit concerns the four constructor failures reported as `Initial summon state requires an audited finite timeline`. No runtime guard was relaxed and no monster was activated by this audit.

| Monster reference | Monster | Blocking initial state | Native initial triple |
| --- | --- | --- | --- |
| 2661 | Guawdia del templo | 1409, Luminescencia Belíade | `(1409, 1, 0)` |
| 2811 | Minero bwork asustado | 1625, Luz tenue | `(1625, 1, 0)` |
| 3835 | Arakna espectral debilitada | 1697, Luz Radiactiva | `(1697, 1, 0)` |
| 3837 | Araknoplasma parásito | 1697, Luz Radiactiva | `(1697, 1, 0)` |

All three state definitions have turn duration `-1`, realtime duration `600000` milliseconds, and `cxj=true` (skip turn timer). The installed native classes were loaded against the actual local binary data; the witness additionally establishes `cxn=false` for all three states. Their child effects are respectively 69817, 82484, and 86458.

## Native lifecycle evidence

`eZk.a` initializes the running state's `rIY` from `fyW.guH`. The null `PN.bac()` branch in `eZk.bbT` returns before creating a turn scheduler. It does not establish that realtime duration disappears or is infinite.

`eZk.fQY` distinguishes two realtime authorities. When `fyW.cxn()` is true it computes elapsed time through `fQZ`; otherwise it returns mutable `rIY`. The actual three states select the latter branch. Treating them as a global elapsed-clock state would therefore use the wrong native authority.

`eZR.qX(long)` can write that remaining value. A bounded scan of client class references found `eZV` call sites that restore the value from serialized running effects and saved state records. Those sites prove persistence/restoration, not the producer that decrements the value or dispatches expiration. The audited evidence does not yet identify that producer and its ownership/lifecycle boundaries.

## Remaining implementation requirement

Recover the source-qualified mutable realtime duration producer and expiration dispatch before implementing these initial states. The state catalog also needs to preserve the native `cxn` distinction if both timing branches are supported. Neither `skip_turn_timer=true` nor absent SU permits silently dropping a positive realtime clock.

The existing realtime rejection in `combat_summon_initialization.py` and `combat_native_timing_context.py` remains appropriate until that authority is implemented. This pattern is shared by four monsters, but this report does not classify them as ready.

## Reproducible evidence

Private generated evidence is under `.runtime/monster-blocker-recovery-20261011/`:

- `finite-initial-realtime-source.json`: actual initial-state triples, timing fields and child effects.
- `ProbeNativeRealtimeInitialState.java` and `native-realtime-initial-state-witness.log`: installed native flags for all three states.
- `eZk-realtime-state.javap`, `fyW-realtime.javap`, and `eZR-private-area-audit.javap`: timing branch and setter bytecode.
- `realtime-clock-producers.javap`: bounded caller audit, including `eZV` restoration sites.

No production code or existing test was changed for this pattern.
