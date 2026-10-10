# Continuous profiler coverage gaps across world recreation

Read-only inspection on 2026-10-10 confirmed a gap of **888.342 seconds** between the completed sample ending at **07:28:43.449 UTC** and the next sample beginning at **07:43:31.791 UTC**. Timeline records continued until **07:29:29.707 UTC** against world PID 7 / process-start ticks 5223148; the following timeline began at **07:43:31.748 UTC** against PID 8 / ticks 5434247. An intervening sample log existed without finalized profile metadata. Therefore the missing interval is real observability loss, not merely a status formatting issue.

Historical Docker events for the earlier gap were unavailable in the current daemon event buffer, so the exact original stop command cannot be attributed. Deployment chronology from the parent investigation places a world boot during the missing interval. A directly observed later recreation confirms the failure mechanism:

- Profiler container `2890b6b67ddd` started at 07:43:25.930 UTC and exited with code **137** at **07:50:48.862 UTC**.
- Docker reported `OOMKilled=false`. Recent HTTP health checks succeeded immediately before exit.
- Its PID mode remained `container:105c0463...`, the prior world container.
- The replacement world container `8bba8af23f3b...` was created at 07:50:38.557 UTC and started at 07:50:49.911 UTC.
- The profiler restart policy was **no**.

The observer shares the world's PID namespace. Replacing world destroys that namespace and its remaining processes, terminating the sidecar observer. The observer cannot recreate itself after it has stopped, and its stored PID namespace target still identifies the old container. A plain restart policy is insufficient to guarantee reattachment to the replacement world container.

During inspection the parent subsequently reattached the sidecar: new timeline data began at **07:59:00.540 UTC**, against PID 7 / process-start ticks 5480652. This investigation itself did not restart or modify any service.

## Recommended recovery contract

Every supported world deployment/recreation should recreate the enabled profiler after the replacement world is healthy, using the current Compose `pid: service:world` resolution. Preserve an explicit enabled/disabled intent so deliberately stopping observability does not cause automatic reactivation. The existing profiler start script already recreates only the profiler; the missing piece is invoking reattachment from the world deployment lifecycle.

For recovery from unexpected world replacement outside that lifecycle, use a separate host supervisor or restricted orchestration controller that can observe container identity changes and recreate the enabled observer. The stopped observer cannot perform this recovery internally. Do not grant it a Docker socket or a host PID namespace merely to conceal the lifecycle dependency.

Within a still-running namespace the service already retries an unavailable sampler periodically. That handles attachment errors while the observer is alive, but does not handle container destruction. Coverage status should continue exposing gaps; missing historical samples cannot be reconstructed.
