# Aptitude movement consumer review

The shared aptitude reducer supplies lock characteristic7, dodge8 and the
combined lock/dodge allocation to the owned actor snapshot. This does not yet
establish functional disengagement. The audited implementation previously
validated the path and deducted rail-aware MP without reading either
characteristic. The shared movement implementation now consumes both through
`combat_tackle_movement`, applying to every class.

AP2, MP3 and WP4 have casting/resource consumers; range11 is read by the shared
casting range resolver; initiative35 supplies the original initial turn ordering;
willpower86 is read by the original resource-loss calculation. AP/MP are restored
from owned maxima at turn start. WP is not generically regenerated each turn.
Damage resistance and health arithmetic are reviewed by the damage/health owners.
The capped-build conditional aptitude initializer now uses the same
`validate_owned_sheet` boundary as the flat reducer.

## Original client evidence

Disassembly of the installed `client/lib/wakfu-client.jar`, classes
`fef`, `fel`, `feg`, `feh`, `fei`, `fek`, `fej`, `GS` and `fcb`, establishes a
deterministic disengagement calculation, not a probability roll:

- `fcb.aI(eGj)` selects the in-play fighter population with a different
  master/root team (`frG` reads `dpu`, not `dpr`), excluding carried
  fighters and CANT_TACKLE property15. `fdU`, `fdM` and `fdG` prove these filters.
- `fek.a` bypasses unavailable/out-of-play/carried movers and ESCAPE_TACKLE69.
- `fel.a` performs radius-aware XY contact checks, excludes the same position,
  and excludes the outer diagonal corners.
- `fef` filters missing tackle characteristics and invisible-type guards,
  sorts descending tackle, and sums each tackle divided by its one-based rank
  using integer division.
- With nonnegative dodge D and aggregate tackle T, it evaluates the float32
  expression `clamp((7/3)*(T-D)/(T+D), -1, 1)`, treating equal values as zero,
  then `(ratio+1)*4*min(0.5+level/200,1)`.
- Facing relative to the tacklers adjusts the result by0, -1 or -2. The
  maximum-facing selection and original `Sl.o` enum identities must be
  preserved when adapting this to owned actors.
- `GS.B` floors `max(0, adjusted_result)` to obtain total loss. `GS.C` rounds
  half upward: MP loss is `ceil(total/2)`, AP loss is the remaining half.
- `fei.a` evaluates the departure at the actual origin and every path cell
  except the destination. Positive-radius tacklers already processed are
  removed from the subsequent candidate collection.
- The real movement preview `dbe` sums those AP/MP losses, checks available AP
  against the AP penalty and available MP against path cost plus MP penalty.

Production wiring preserves the actual fighter population, status/property/carry
authority, direction, requested path and rail cost. It validates affordability
and both PA mutations before charging AP and then combined path/penalty MP.
Actual PA setters preserve existing resource listeners. Client movement previews
the full operation and serialization before publishing the original fight.
This AP-before-MP mutation boundary is explicit Wakemu server policy using the
recovered native calculator and preview cost contract, not a claim that an
original server caller or packet settlement sequence was recovered.

## Verification scope

`ProbeNativeTackle.java` invokes original `fef` with its actual `fcP` interface.
Its108 exported cases at levels1/60/200 match the Python calculator exactly.
The golden output is stored under `server/tests/fixtures/`. Focused regressions
also exercise real FSM affordability, ownership/property filters, codec rollback
and actual raw PA observer delivery. No service or database was changed.
