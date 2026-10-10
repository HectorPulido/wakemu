# Live AI context inventory stall at 06:20 UTC

Read-only investigation; captures and log window preserved under `.runtime/local/diagnostics/slow-combat-20261010-0620/`. No restart or gameplay mutation.

Fight 145 tactical-action telemetry at 06:20:30.255623 UTC reports **45,811.645 ms in context inventory**, 45,811.846 ms in catalog session, and 45,844.611 ms total decision elapsed. The subsequent event reuses these metrics and must not be counted as another operation.

Continuous capture `capture-1791613135828302521` has 292/1414 identical session-thread-239 samples on context filesystem sorting. The next capture `capture-1791613195246536799` has 880/1484 identical samples on the same stack:

`world_bridge.inventory:305 → _inventory_scan:517 → files:383 → pathlib.__lt__:534 → _parts_normcase:502 → _str_normcase:491 → __str__:443 → drive:557 → _load_parts:415 → _parse_path:404`.

This is the expression `sorted(result, key=lambda pair: pair[1])`, sorting Path instances after enumerating a complete source root. Directory iteration checks the time budget, but the sort has no check and performs repeated Python path comparison/parsing. The dominant sampled path is different from the earlier fingerprint reducer stall. Context wall telemetry alone does not certify CPU seconds; the samples establish actual sorting work and duration attribution.

Thread 227 concurrently has 130 identical samples entering shared `expire_current_turn` and 126 entering shared `dispatch_connected`, consistent with waiting for shared fight access while thread 239 processes AI preparation. Exact lock owner requires runtime ownership evidence; do not classify these blocked stacks as CPU work.

Candidate minimal correction: precompute component-wise lexical keys from already captured relative names rather than invoking Path comparison repeatedly; preserve Path ordering semantics and source completeness. Add bounded budget checks during key generation/comparisons or sorting batches so expiration cannot be deferred until a giant sort completes. Investigate why a root expected to contain modest context suddenly incurs a pathological comparison workload before declaring the incident fully explained. No change was implemented by this investigation.
