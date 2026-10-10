# Continuous profiler stopped progressing before r71 deployment

The completed capture ending at **2026-10-10 15:30:22.146 UTC** was followed by an unfinished capture log beginning immediately afterward. Process/timing JSONL also stopped, with its final old-world record at **15:30:31.830 UTC**, against world process-start ticks 5599751. No timeline records followed until the reattached observer at **15:42:42.179 UTC**, against ticks 8304264. The next finalized profile began at **15:42:42.191 UTC**, creating a **740.045-second** gap.

The parent explicitly stopped the profiler around 15:41:15 UTC before recreating world at 15:41:26 UTC. Therefore most of the gap precedes that deployment. Both the sampler and timeline stopped progressing approximately eleven minutes before the intended stop; this is not only a missing finalized profile at deployment.

The prior observer container was already replaced, so its final process state and logs were unavailable. Historical Docker events were no longer present in the daemon buffer. The inspected macOS power-management records did not establish an actual sleep event for this interval. Current observer usage was about 24 MiB, retained history about 60 MiB, with no byte-cap truncation and ample disk space. These observations do not prove the old container avoided OOM, termination, or blocked host I/O. The original interruption cause remains unproven.

## Proven monitoring defect and correction

Before this change `/health` always returned success, and `running` only meant a sampler process object remained assigned. Neither demonstrated that the recorder thread was alive, that the timeline was advancing, or that the active capture was completing.

The revised service reports recorder health and returns HTTP 503 when enabled recording has any of these conditions:

- Recorder thread is dead or its monotonic progress heartbeat is older than 20 seconds.
- The active capture is older than the existing 140-second sampler completion limit.
- Recording is enabled but no sampler is present after the 15-second initial grace period.
- A recorded lifecycle error remains outstanding.

`/status` includes recorder heartbeat age, thread liveness, missing/stale capture flags, and marks degraded status. Existing saved coverage gaps remain visible.

Unexpected timeline/retention exceptions are now caught, written to stderr and persisted as `recorder_error` rows in the minute JSONL history where disk writes remain possible. The recorder retries on the next five-second tick instead of allowing an unexpected exception to silently terminate the only recorder thread. Persistent host I/O failures cannot be repaired by promising successful persistence; stale heartbeat/health makes that loss visible.

The existing bounded child wait remains unchanged: only a timed-out sampler child is killed, never world. This patch adds no Docker socket, host PID access, world restart, or blind container recovery. A stopped container still requires the previously documented external reattachment lifecycle.

## Validation

All 17 external profiler tests pass, including stale/dead recorder detection, stale capture status, HTTP 503 with a responsive HTTP server, persisted unexpected-error reporting, and recovery on the next recorder tick. Existing continuous chaining, one-hour retention, byte cap and child-only stop tests remain passing.

Only the sidecar source/tests and this report changed. The parent controls the separate sidecar rebuild/recreation; no world rebuild is required for this patch.
