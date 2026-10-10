# Fight entry latency, 2026-10-10 11:36 America/Bogota

Request `726397447e734e6480632f7bfe174e42` (opcode 13130) entered at 16:36:44.172 UTC and completed at 16:37:10.400 UTC: **26.228 seconds**, fight 167, map 527. No unfinished entry request remained afterward. A second queued click was rejected in 0.960 ms because placement was already active.

The `arena_selected` stage consumed 24.909 seconds wall / 24.728 seconds thread CPU. Resource construction was 24 ms, durable placement 109 ms, snapshot initialization 2 ms, and forced terrain serialization 856 ms. First entry packets were sent only after the expensive stage. This is confirmed server execution latency, not merely a client rendering delay.

Continuous capture `capture-1791650174925162271` has 611 local-arena samples: 585 under native QI surface loading and 582 at `NativeQISurfaces.__init__` line 79 (surface interning lookup). Only 15 samples are in arena selection/BFS and eight in published geometry loading. This does **not** establish quadratic complexity: the constructor has a linear loop over published surfaces.

The exact published map contains 3,384,935 bytes, 521 chunks, 168,804 columns and 174,052 surfaces. An independent process in the same running world image constructed the exact provider in **0.673 seconds wall / 0.641 seconds thread CPU**. This falsifies the claim that its normal loop inherently takes 25 seconds. Live heap/collection or other process-specific conditions need further evidence. Available aggregated GC telemetry recorded only generation 0/1 pauses below 100 ms and no completed generation 2 row; it does not prove a long GC pause in this request.

The provider already has an eight-map LRU. No speculative cache or validation bypass was introduced. Preserve signed surface validation, ordered columns, first-matching chunk behavior, provenance checks and authoritative map geometry. The parent may deploy the independently validated fixes without waiting for this completed request; this finding does not claim the entry pause is solved.

Private request and profile evidence: `.runtime/local/diagnostics/start-fight-1136/`.

## Follow-up observability

The GC monitor's bounded queue could overwrite a long completed pause if enough short collections occur before the report writer drains it. This is an observability gap, not proof that the 11:36 stall was GC. The monitor now retains the longest scalar pause record for each of the three generations independently of that queue. Sequence watermarks avoid counting the same record twice when it is present in both paths. Callbacks remain bounded, lock-free and detached from logging/profiler calls. Collection thresholds, enablement and scheduling are unchanged.

A regression simulates a 25-second generation-2 pause followed by three generation-0 pauses overflowing a two-record queue, then verifies that generation 2 is reported exactly once and a second drain does not duplicate it. Combined validation is assigned to the test agent.
