# Live combat CPU stall, 2026-10-10 05:42 UTC

Read-only investigation of world r65, with original evidence retained in `.runtime/local/diagnostics/slow-combat-20261010-0542/`. No restart or runtime mutation was performed.

Fight 139 contains a confirmed CPU-heavy source integrity fingerprint stall. The tactical action logged at 05:43:06.167 UTC for actor `-1125899906871299` reports 12 source guard calls totaling **32,290.294 ms wall and 32,239.805 ms thread CPU**, with **32,119.682 ms maximum single-call wall time**. The decision took 38,021 ms. Its later duplicate tactical-action event reuses the same metric set and must not be counted as another 32-second operation.

Continuous capture `capture-1791610904246071788` has 328/1399 samples of session thread 8284 on one identical stack. Following capture `capture-1791610966091355329` has 480/1423 identical samples:

`_prepare_npc_turn → native_turn.run_turn:160 → world_bridge.decide:1188 → query:1200 → guard:979 → _measure_native_query:1229 → _source_hash:963 → native_fingerprint.fingerprint:81 → _CompletePickler.reducer_override:56`.

The leaf is dictionary-subclass reduction (`iter(value.items())`) inside the C pickler. Ordinary guard calls nearby take about 13–20 ms. This establishes pathological graph traversal or reduction on one guard invocation; the exact owning object and cause of the exceptional traversal remain unproven. Captures include idle threads, but the independent thread CPU metric confirms this specific delay is computation rather than SQL, network or checkpoint waiting.

Session 6374 is overwhelmingly idle in SSL receive during the first interval. Checkpoint workers and other background threads mostly wait normally. The second interval includes 51 identical AI HTTP response-wait samples, which are secondary to the fingerprint occupancy. Do not attribute all server waiting to the fingerprint without lock/ownership evidence.

Recommended next step: inspect the precise value passed to `_source_hash`, its dictionary-subclass/authority fields and transient mutation boundaries; isolate the pathological reduction without weakening full state-integrity checks. Avoid disabling guards or replacing them with incomplete fingerprints. No optimization was implemented by this investigation.
