# Weather domain extraction

`wakfu_server.ecology_weather.prepare(store, snapshot, limit=16)` is the external domain entry point. It advances due PostgreSQL weather transitions and returns at most `limit` JSON-safe publication proposals across weather and forecasts. Forecast packets are encoded in the service. The snapshot is intentionally unused: weather authority is already durable PostgreSQL state.

`apply(store, world, proposal)` performs an exact outbox/current-authority lookup, publishes outside the transaction and acknowledges the exact revision. It does not advance transitions, compute forecasts or scan all pending publications. Stale/already acknowledged proposals are harmless. Socket failure leaves the event unacknowledged for retry. Weather acknowledgement now also compares against current authority, matching the forecast acknowledgement's existing version fence.

The prepared forecast bytes are an internal authenticated service contract, not a client-input API. The existing forecast decoder validates their wire shape. World routing still revalidates session generation, instance, map and native territory.

Publication is at least once. A transition racing between authority reload and socket send can still send an old snapshot before the newer durable event; acknowledgement cannot mark that old event current. Strict wire ordering would require scoped dispatch sequencing and is not claimed by this change. Neither socket delivery nor client receipt can be made atomic with a PostgreSQL commit.

The existing pending-publication cleanup runs in service preparation, including superseded-row maintenance; its cleanup UPDATE is not bounded by the returned proposal count. World application never calls that cleanup. This is a service-side maintenance concern for a future bounded cleanup change, rather than a hidden world-lock scan.

Validation: `PYTHONPATH=server:server/tests .runtime/local/performance-test-venv/bin/python -m unittest test_ecology_weather` passed 5 tests covering total proposal bounds, JSON safety, stale revisions, publication outside transactions, send failure and service-only forecast encoding. Independent broader validation was requested from Luna. A standalone existing publication-suite invocation without database configuration failed catalog lookup and a territory assertion; it is not reported as green. No deployment was performed by this implementation agent.
