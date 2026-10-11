# Native449 world-property mutation

## Actual representative and source

All six historical monster references2388,2390,2391,3540,3761 and3762 reach effect268501, native449 parameters `[83,0]`. Installed world-property registry83 is `COMPANION_DISABLED_FOR_FIGHT`, without a mapped fight property (`-1`). These were previously paired with missing830; this change does not claim their full runtime qualification.

`eWw.c` resolves the integral `aSg` through `eHQ.Qm`. A null target, a non-eGj target or unknown enum suppresses execution. For actual `PN.bag()==1`, it first adds the optional mapped `ffe`. It then always adds `eHQ`. `bbR` removes the mapped `ffe` whenever it exists, regardless of the original context kind, then removes `eHQ`. The asymmetry is intentional.

`eGj.f/g` addresses separate managers: type0 `pGI` for world properties, type1 `pGH` for fight properties. World add lazily creates the manager; world removal resets it to null after its final entry disappears. An absent fight manager remains absent. Existing `combat_property_stack` preserves signed-byte overflow and `count != 0` presence. `eHN` notifies after each manager mutation, including decrement of an absent property when the manager exists.

Native context evidence is under `.runtime/monster-blocker-recovery-20261011/next-family-runners/`: `eZQ449.txt`, `eVw449.txt`, `eWw.txt`, `eGj-properties.txt`, `eHN.txt`, plus the parent manager-audit receipt. `eGj` constructs `eZQ(this,3)` for SELF descriptor initialization; `eZQ.bag` returns its saved kind. `fbX.fUt` constructs `eVw`; `eVw.bag` returns1. Unknown runtime context kinds reject.

## Notification and timestamp boundaries

Direct `eWw` uses `eGj.f/g` and the PB/eHN manager route. It does not call `eHC.a`, which writes wall-clock timestamps. No activation-age timestamp is synthesized.

Mapped `ffe` mutation does not execute `eWt447.c`. Therefore it must not borrow eWt's explicit resource resets, timeline changes or QI mutations. `eGj.a(PE,PG)` is a no-op; actual client subclasses handle UI notifications (`big`, `bjo`, `biB`). The evaluated native449 packet delivers the same runner to those client callbacks. The server does not invent a Qf gameplay event to stand for this UI notification.

## Implementation and validation

The typed mutation primitive accepts explicit actual manager absence, preserves ordered notification callbacks and delegates arithmetic to the existing counter helper. The handler requires complete source-qualified counter populations from the actor authority, owns captured retained identity and original payload, and reverses both namespaces on removal. Native `bbz=false` uses evaluated application12613; removal uses13560.

New tests cover actual268501 retention/removal, no invented eHC timestamp, constructor asymmetry, mapped fight counts without an invented AP reset, missing populations, lazy/absent managers, notification ordering and signed-byte overflow. Independent focused results are recorded separately. No services, live catalogs or activation were changed.
