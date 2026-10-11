# Ecology service infrastructure

Status: source implemented and verified; this worker did not deploy or restart services.

## Ownership and transport

The service has one planning loop and one PostgreSQL advisory-lock session. A second worker cannot acquire ownership of the same database. Losing that session stops work; the loop must reacquire the advisory lock before planning or delivering again. There is no automatic fallback to simulation inside world.

World supplies a bounded authenticated snapshot through `GET /internal/ecology/snapshot`. The worker prepares plants, mobs, weather and population proposals, commits their envelopes to PostgreSQL, and submits at most 16 proposals per request through `POST /internal/ecology/apply`. Newly committed proposals can be delivered in the same tick. Existing pending work is attempted first. Every proposal carries a stable hash of its domain/payload and the expected world epoch. Domain CAS and native outboxes remain the authority for replay protection; network delivery is at least once.

The dedicated token is loaded from `WAKFU_ECOLOGY_TOKEN_FILE`. It is separate from game, admin and scheduler credentials. Requests use finite socket deadlines, a 256 KiB request limit and a 1 MiB response limit. World never calls this client from a gameplay critical section.

## Durable wakeups and recovery

Migration `104_ecology_service.sql` adds:

- `ecology_dirty_scopes`: coalesced transactional scope revisions. Triggers cover planted resources, combat groups, weather and resource-harvest occupations. Settings changes mark the global `(-1,-1)` scope. Rolling back a gameplay transaction also rolls back its wakeup.
- `ecology_service_proposals`: pending envelopes with retry counts and delivery timestamps. Pending work survives process restarts.

Migration `110_ecology_delivery_recovery.sql` adds retry deadlines and the completed-history retention index to the already-deployed schema. Retry delays grow from one second to a maximum of 30 seconds; low-attempt work sorts ahead of repeatedly rejected rows. Migration 104 remains byte-identical to its deployed version (SHA-256 `ca59d1cd5d2cb07e27e10a5a9897520cfbc3eac3e1e1e9a1d31c24b8779f5bad`); recovery uses a forward migration without changing recorded database checksums.

Acknowledging an observed scope advances only its captured revision, so a newer event remains pending. Scope ACKs use one bounded `UNNEST` update. The planner does not require dirty rows to run: timers and interactive intents are polled even when no wakeup exists. Domain priority rotates to prevent one full batch from permanently starving another domain. Domain failures leave dirty scopes unacknowledged while preserving proposals prepared by other domains.

Pending envelopes are capped at 256 by the single producer. Completed history retains at most 4096 rows or seven days, cleaned in batches of at most 256; pending rows are never removed by retention. A full pending budget reports degraded health instead of silently dropping events.

Delivery retries default to five attempts, configured by `WAKFU_ECOLOGY_MAX_ATTEMPTS` (integer 1–100). Both explicit retry responses and HTTP failures count. Exhausted envelopes are durably archived with `last_error_code='retry_exhausted'`, never represented as applied, and use the existing bounded retention. Before planning, the worker archives up to 256 historical rows already beyond the limit, allowing a previously saturated queue to recover even while transport is unavailable. The same proposal ID is not resurrected within the same world epoch. Status reports retained delivery attempts, exhausted count and configured limit.

## Health, controls and queries

All HTTP endpoints require the dedicated bearer credential:

| Route | Behavior |
| --- | --- |
| `GET /health` | Returns 503 on stalled progress, worker/domain errors or a full pending budget. |
| `GET /status`, `GET /metrics` | Fixed counters, pending count, last tick duration, progress age, CPU time and peak RSS. |
| `POST /pause`, `POST /resume` | Accept `{}` and persist the enabled flag in PostgreSQL settings. |
| `GET /query` | Debugging snapshot with age and `authoritative:false`. |
| `POST /query` | Actual repeatable-read population or weather query with `authoritative:true`, scope revision and observation time. |

An actual query accepts only `kind` (`population` or `weather`), `map_id`, `instance_id`, and optional `region_id`. Population results preserve the domain's explicit `complete`/`unresolved` information; authoritative database data does not imply complete native-region knowledge. Queries are limited to 4096 entities or 64 weather regions, bounded JSON, a single concurrent computation, and a two-second response deadline. A timed-out read-only computation may finish in the background; additional requests cannot queue behind it. Repository SQL uses a one-second statement timeout, 250 ms lock timeout and 500 ms pool acquisition timeout.

`EcologyClient.query()` must use the ecology-service base URL and run outside gameplay locks. Its response is a point-in-time read, not permission to bypass final mutation validation.

World now exposes the explicit `EcologyWorldBridge.query(kind, map_id, instance_id, region=None)` method. Startup injects a client using `WAKFU_ECOLOGY_URL` (default `http://ecology:8093`) with a two-second socket deadline. The method refuses calls while the current thread owns the world, group or harvest lock, and requires external mode. It accepts only authoritative responses for the requested scope, with a valid revision and timezone-aware observation timestamp no more than five seconds old (at most two seconds ahead). Errors propagate; it never returns a cached response as current authority. Existing gameplay call sites were not changed.

## Configuration

Build `server/ecology-service/Dockerfile` with the server directory as its context and the pinned catalog revision as `CATALOG_REVISION`. Startup validates that revision against PostgreSQL. Required environment includes database configuration, the database password file, Redis URL, catalog revision and dedicated token file. `WAKFU_WORLD_URL` defaults to `http://world:18081`; `WAKFU_ECOLOGY_POLL_SECONDS` defaults to one second. The HTTP service listens on port 8093. Compose resource/network policy belongs to the coordinator's integration.

## Verification

Luna verified 61 combined corpse, initial-population, population and service tests in 1469.138 seconds. The result includes all 18 pure transport/worker/control tests and six PostgreSQL service tests on the final migration and implementation. Covered cases include transaction rollback, scope-ACK races, restart persistence, epoch replanning, retry backoff, durable pause, ownership reacquisition, actual query data, bounded completed retention, pending-row protection and persist-before-deliver ordering.

After wiring the explicit world query client, Luna verified 31 bridge/transport tests in 0.107 seconds. Six new query cases cover fresh authority, rejection under all three owned locks, a lock held by another thread, stale/malformed response rejection, a two-second client deadline, error propagation without stale fallback, and unavailable execution modes. Log: `.runtime/local/diagnostics/ecology-bridge-query-final.log`.

After separating the deployed migration from its recovery delta, Luna verified `test_ecology_delivery_upgrade test_ecology_service_postgres test_ecology_service_transport`: 25 tests passed in 28.294 seconds. The upgrade regression starts with migrations through the original 104, preserves a pending envelope and its recorded checksum while applying the complete current migration set through 110, and verifies a second migration pass makes no changes. All mutations use isolated test schemas. Log: `.runtime/local/diagnostics/ecology-delivery-upgrade-final.log`.

After adding bounded retries, Luna verified 43 service PostgreSQL, transport and world-bridge tests in 35.004 seconds. Regressions cover HTTP timeout accounting, historical over-limit recovery, restart persistence, no same-epoch resurrection and success on the final allowed attempt. Log: `.runtime/local/diagnostics/ecology-retry-cap-final.log`.
