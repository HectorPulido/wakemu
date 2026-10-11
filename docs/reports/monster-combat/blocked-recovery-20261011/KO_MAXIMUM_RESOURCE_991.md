# Native KO maximum characteristic (family 991)

This is an offline structural recovery, not monster activation or encounter qualification.

The installed registry maps effect 991 to the existing `eWN` runner with characteristic 14, `KO_TIME_BEFORE_DEATH`. The actual native cap is **-1**, so neither the AP cap 16 nor MP cap 8 applies. Its native events are `[0]`, with `bbA=true` and `bbB=false`. These values were executed from the installed registry, not inferred from nearby family numbers.

## Source representatives

The sealed inventory contains Kya, Mizz Frizz (2348) and Neokya, Mizz Frizz (5799), both native levels 128–133, with the same six owned spells: 3462, 3463, 3466, 3460, 3461 and 3577. Names come from `content.7`; spell names/descriptions come from `content.3`/`content.4`.

Both closures contain effect 87039, family 991, empty criterion, parameters `[2,0,1,0,0,0]`: add two to the raw maximum, apply the effective maximum delta to current, and disable explicit current removal. The effect is a root of native state 1713, named `content.8.1713`, “Presencia de la No-Vida”; its state description is absent. This is a KO resource mechanism, not HP, AP or MP modification.

## General implementation

`NativeMaximumResourceHandler` now includes family 991 in its existing `eWN` mapping. Original calculation, context forcing, scoped triggering-Qe identity, synchronous runner mutation, timing, wire payload and phase lifecycle remain shared with existing maximum-resource effects. The native maximum-event exporter includes 991, so future catalog generation can reproduce its source-qualified metadata automatically.

The existing copied-PA14 authority and setters handle the additional hidden raw-current case. Application changes maximum before optionally shifting current; removal optionally subtracts the retained raw amount before restoring maximum. Frozen copied current remains hidden and can reappear when a bound increases. Frozen current without a genuine raw-current producer fails closed.

Fresh mutable PC14 has `over_max_current=false`; its bounded effective current is the raw current, so it reuses the existing ordinary maximum path. Percentage effects matter: removal subtracts the original raw amount, not the effective maximum delta, and therefore need not recreate the initial current exactly. This behavior is native.

## Evidence and validation

`sniffer/java/ProbeNativeKOMaximum.java` executes seven actual installed-runner scenarios: ordinary increases, no artificial AP/MP cap, percentage conversion, both current flags, negative amounts and frozen copied raw current. It also records the actual runner identity, cap and event metadata.

Private evidence: `.runtime/monster-blocker-recovery-20261011/ko-maximum-991/{native,representatives,receipt}.json`.

Focused tests: **16 pass**, comprising seven new family-991 tests and nine original shared maximum-resource tests. New coverage includes actual factory dispatch of reference 87039, unchanged HP/AP/MP, all four source phases, retained removal, percentages, native flags, frozen raw current and rejection of missing authority. Original assertions are untouched. No services, PostgreSQL writes, catalog publication or deployment occurred.

The generated five-prototype `native-maximum-resource-events.json` is an offline fixture. The same source-qualified metadata must accompany any later candidate/catalog publication. The two monster references still require their complete level/book/initialization/AI qualification; eliminating a missing family does not prove readiness.
