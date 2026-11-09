# WakIA planner benchmark

This runs the production C# planner and its real serialized admission gate on a
prepared advisory snapshot. It does not need Docker, World, a database or a game
client. It wraps the snapshot in a protocol frame and includes the actual host's
JSON parsing and recursive duplicate-key validation, gate waiting and planning; it does **not**
include native snapshot construction, transport, World execution, animation
ACKs or an entire game turn. Never describe these timings as end-to-end latency.

```sh
dotnet run --project server/ai-jondo-service/Benchmarks/WakIABenchmarks.csproj -c Release -- --scenario melee --warmup 3 --samples 30 --concurrency 1
dotnet run --no-build --project server/ai-jondo-service/Benchmarks/WakIABenchmarks.csproj -c Release -- --scenario crowded --warmup 3 --samples 30 --concurrency 4
dotnet run --no-build --project server/ai-jondo-service/Benchmarks/WakIABenchmarks.csproj -c Release -- --scenario team --warmup 3 --samples 30 --concurrency 1
dotnet run --no-build --project server/ai-jondo-service/Benchmarks/WakIABenchmarks.csproj -c Release -- --scenario team-coordinated --warmup 3 --samples 30 --concurrency 1
dotnet run --no-build --project server/ai-jondo-service/Benchmarks/WakIABenchmarks.csproj -c Release -- --input /path/to/advisory-snapshot.json --warmup 3 --samples 30 --concurrency 1
python3 -m unittest discover -s server/ai-jondo-service/Benchmarks -p 'test_frame_validation.py'
```

The JSON output includes request counts by status, action types, errors and
nearest-rank p50/p95/max in milliseconds for parsing, queueing, planning and
their total. Very small samples do not establish a meaningful latency
distribution. `--budget-ms` changes only the snapshot decision budget and is
clamped to the production gate's 1–2000 ms interval. The timeout counts from
receipt through parsing, queueing and decision. A 503 under load is a result,
not a successful fast decision.

`parse` includes frame validation, including the host's duplicate-key walk;
`snapshotBytes` measures the payload and `frameBytes` includes the envelope.
Measurements from the older benchmark without that walk are not directly
comparable. The runner does not measure TCP frame reception or serialization
of the response. Use `--check-frame PATH` to run the same duplicate-key check
against a raw JSON frame without planning.

The bundled scenarios are synthetic: they exercise the actual C# code but do
not establish correctness of Wakfu combat semantics. An external snapshot must
be a protocol-1 decision request; use only authorized, sanitized fixtures and
do not commit captures or private player data. The benchmark never modifies the
input file. Compare versions with the same input, warmup, samples, budget,
concurrency, machine and otherwise comparable load. Do not compare these
numbers with a client-observed turn or with different snapshot preparation.
The `team` and `team-coordinated` scenarios have the same map, actors and
spells. The latter adds an eligible focus target and a live allied firing
corridor, so they can also help identify the cost of coordination on a
representative request. Timing differences can include different planning
choices and machine load; they are not a controlled guarantee of overhead.

For live end-to-end analysis, use native diagnostic timings separately for
snapshot preparation, RPC/queue/planning, validation and commit, and client
ACK. Pair observations from the same fights and report sample size and load;
do not add independently computed percentiles to derive a total percentile.
