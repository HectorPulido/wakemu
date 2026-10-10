# Live cast and AI stalls at 06:54 UTC

Read-only investigation, evidence retained under `.runtime/local/diagnostics/slow-combat-20261010-0654/`. No restart or gameplay mutation.

## AI integrity guard

Fight 147 tactical action at 06:54:47.627220 UTC reports source_guard 7 calls, 1 failure, 26,316.255 ms wall, **26,289.283 ms thread CPU**, maximum single call **26,233.399 ms**. Decision elapsed 27,020.252 ms. The immediately following event duplicates these guard metrics and must not be counted twice. A deadline failure therefore occurred after roughly 26 seconds of CPU consumption.

Capture `capture-1791615216364167182` beginning 06:53:36.364 UTC: thread 2549 has 421/1430 identical samples. Next capture `capture-1791615278430427410` beginning 06:54:38.430 UTC: 234/1433 identical samples. Path:

`decide:1197 → query:1229 → guard:988 → _measure_native_query:1238 → _source_hash:972 → fingerprint:100 → reducer_override:59 → items:39 → __iter__:30`.

The checked iterator wrapper is still part of the pathological fingerprint path. Exact graph ownership remains unresolved. Independent CPU telemetry distinguishes this stall from a network or SQL wait.

## Player spell authority work

Request `20e3e76b55634b978446548044cbc534`, caster 4, reportedly completed in 8,873 ms at 06:54:08.927 UTC. In the first capture, approximate offset 23.6–32.6 seconds (06:54:00–09) contains 225 session-thread samples. 146 contain the shared cast transaction; 129 contain `combat_event_replay.__call__:208`; 126 contain retained-runtime execution; 125 contain ordered child-group execution. These inclusive counts overlap.

Frequent stacks end in `combat_effect_removal._identity_fields:32/37/43`, called through `combat_retained_runtime.view:1310 → EffectRemovalAuthority.__init__:127` from event replay phase processing. This identifies repeated authority-view construction/identity collection as a concrete cast cost candidate. It is independent of the later AI fingerprint stall. Exact CPU attribution and safe lifetime/caching boundaries need inspection before changing behavior.

The second socket thread waits at shared dispatch and expiration lock entry during portions of both captures. Those waiting stacks are not CPU work. Preserve event replay and removal-authority semantics when addressing repeated metadata traversal.

## Corrections prepared and validated

- AI guard/transport traverses stored dictionary entries without executing lazy overridden dictionary views; complete subclass fields and identity graph remain included. 95 focused AI tests passed.
- Common retained-effect protobuf identity parser caches immutable parse results only, keyed by exact bytes, field selection and message mode. Fresh dictionaries preserve caller isolation; malformed/duplicate and partial-error semantics remain checked. Cache is bounded to 512 entries of at most 4096 bytes and 16 selected fields. No mutable fight authority or view is cached.
- 25 parser/effect-removal/event-replay tests passed. Synthetic repeated parsing improved 4.96 times; this is not a measured whole-cast latency improvement.
- Complete r68 image matches all 688 current server implementation/migration files. Live acceptance must repeat a player spell and an AI turn, including spectator entry, before claiming the stall eliminated.

Deployment: single world restarted at 02:07 local with `wakemu-world:performance-20261010-r68`. Health returned OK; mounted AI implementation hashes match the validated source. Continuous profiler is running, retaining one hour (1 GiB cap), with no current error. Prior live captures remain preserved in diagnostics.
