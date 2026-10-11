# External ecology population preparation

`maps/ecology_population.py` preserves the existing regional `snapshot` API and adds the worker/world contract:

- `prepare(store, world_snapshot, limit=16)` returns JSON-safe proposals with the snapshot's nonempty string `world_epoch`. The limit is 1 through 256. Proposal kinds are `corpse_expiry`, `initial_population`, and `initial_publish`.
- `apply(store, groups, harvests, world, proposal, *, world_epoch)` rejects old-world proposals before acquiring any live locks. It acquires the existing group then harvest locks and returns `applied` or `stale`.

No HTTP, live game objects, callbacks, or locks cross the worker boundary. Configured initial habitats are processed even without nearby players, preserving one-time initial population behavior. All prepared data is tied to the catalog revision. The existing `seed_zone`, `seed_configured`, and legacy corpse `expire` APIs remain available.

## Corpse expiry

The worker reads bounded due identities without marking them published. The world transaction locks one corpse row and rechecks exact scope, expiry, consumption timestamp, unpublished status, and current due status. It emits the native removal first, then marks publication. Harvest claims and expiry publication share the row fence and existing harvest lock order.

`World.emit_location_batch(require_all=True)` attempts every captured recipient and raises if any send failed. The default remains unchanged for other callers. Strict publication therefore rolls back its SQL acknowledgment when the world send helper would otherwise swallow an individual socket failure. No recipients counts as successful publication; future scene hydration reads current durable state.

## Initial population

The worker checks configured geometry, roster, family, habitat, policy, capacity, and occupied cells. A repeatable-read snapshot produces a fingerprint of the scope's durable groups and planted resources. The world compares the current policy, permanent marker, catalog revision, configured plan, and fresh scope fingerprint under the population advisory fence. It registers at most eight members in one transaction without rebuilding geometry or regional population.

Migration `105_initial_population_publication.sql` adds a retryable projection outbox for newly registered background seeds. Existing startup seeds are not retroactively queued. A later `initial_publish` proposal reads the latest group under a row fence. Available groups emit one ordered native remove-then-spawn batch and then acknowledge the outbox. Reserved or defeated groups are left to their combat lifecycle and never respawned by this publisher.

Network publication is at least once: a crash after delivery but before SQL commit may retry. Corpse removal is idempotent. Initial group publication replaces current identities with ordered removal followed by the latest durable roster, covering both a retry and peers that already hydrated the birth from the database. No claim of transactional exactly-once network delivery is made.

## Limits and validation

Worker proposal count and world event size are bounded. Final registration still queries and hashes current group/resource rows for one scope, so its SQL work grows with that scope; it does not re-run map geometry or native regional classification. This conservative revalidation avoids applying a capacity decision after another world mutation.

Syntax compilation and whitespace checks passed. Luna owns regression execution, including publication failure retry, stale proposals, initial population markers, corpse harvest races, and strict world batch behavior. No service was restarted or deployed by this change owner.
