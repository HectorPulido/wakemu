# Optional external world profiler

This sidecar attaches to the existing Python world without restarting it. It has no Docker socket, host PID namespace, world control endpoint, captured locals, or arbitrary command interface. The container shares only the world PID namespace and adds `SYS_PTRACE`. Host HTTP access is localhost only. Captures stay under private `.runtime/local/profiler` and retain a rolling hour of data. Starting the service automatically records all-thread stacks (active and waiting) at 25 Hz in consecutive 60-second Speedscope chunks. A JSONL timeline saves process metrics and the complete published feature summary every five seconds; timestamps and metric-file age expose the world summary's 30-second publication cadence. Process PID/start ticks and the world summary identify restarts.

```sh
docker compose -f compose.yaml -f compose.profiler.yaml --profile observability build profiler
docker compose -f compose.yaml -f compose.profiler.yaml --profile observability up -d --no-deps profiler
curl -s http://127.0.0.1:18082/status
curl -s -X POST -H 'Content-Type: application/json' -d '{"seconds":30,"mode":"cpu"}' http://127.0.0.1:18082/capture
curl -s -X POST http://127.0.0.1:18082/stop
docker compose -f compose.yaml -f compose.profiler.yaml --profile observability stop profiler
```

Stopping the sampler never sends a signal to world. Stopping the sidecar finalizes the current chunk (up to eight seconds) and does not stop world. After a world container recreation, recreate the sidecar so its PID namespace follows the current world.

Timeline files and capture metadata are available through the artifact endpoints. `/status` reports retained coverage, gaps longer than two seconds, recent errors and capacity truncation. A default 1 GiB cap (`PROFILER_MAX_BYTES`) bounds completed history; if that limit shortens the hour, `capacity_truncated` and `degraded` remain true for an hour after eviction. Active capture bytes count toward the cap. If an active chunk alone exceeds the cap, the next five-second check interrupts and finalizes it early; writes between checks can temporarily exceed the cap. Completed capture groups are evicted together so metadata never advertises a removed profile. Files expire by modification time after one hour (chunk granularity).

`bash client-tools/profiler.sh start|stop` toggles the sidecar; `pause|resume` toggles sampling while keeping the service and process timeline alive; `artifacts` lists saved files. No world restart is needed.

Endpoints: `GET /health`, `/status`, `/report`, `/artifacts`, `/artifacts/<basename>`; `POST /capture` accepts only integer `seconds` (5–120) and `mode` (`cpu` or `waits`); `POST /stop` pauses continuous sampling and interrupts only the sampler, finalizing a partial capture. `POST /start` resumes continuous sampling within five seconds. While continuous sampling is active, `/capture` returns the current covering chunk rather than competing for the same process. Only one capture runs at a time. `/report` reads `performance-latest.json` from the read-only metrics mount and returns 404 until world publishes instrumentation. `/status` provides cumulative CPU seconds, RSS, thread count and state from procfs independently of the Python GIL in world.

The pinned sampler is **py-spy 0.4.2**, verified against PyPI package metadata on 2026-10-09. Sampling uses 25 Hz, per-thread Speedscope JSON, and `--nonblocking`. CPU mode samples active stacks; waits mode includes idle threads. Neither is an exact measurement of CPU cost per feature. Sampling reveals hotspots and waiting stacks; application timing summaries provide feature latency and counts. Nonblocking reads can occasionally produce incomplete samples; the profiler has finite overhead and runs continuously while enabled; this is sampled telemetry, not a lossless trace of every operation.

Open the JSON in a local Speedscope installation. Do not upload private captures to external services without reviewing them. Artifacts contain source paths and function names but do not intentionally capture locals or game payloads.

Official implementation and limits: [py-spy README](https://github.com/benfred/py-spy), especially nonblocking sampling, idle thread detection, and Docker `SYS_PTRACE` requirements.

Recorder health is independent of HTTP liveness. `/health` returns 503 for a dead/stalled recorder thread (20-second progress limit), a capture older than 140 seconds, enabled sampling without a child after 15 seconds, or an outstanding lifecycle error. `/status.recorder` exposes the individual reasons and heartbeat age. Unexpected recorder-loop errors are persisted to timeline JSONL when storage permits and retried on the next tick.
