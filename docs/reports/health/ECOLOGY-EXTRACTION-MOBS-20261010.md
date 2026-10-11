# Monster ecology extraction boundaries

Read-only discovery, 2026-10-10. No service or code change yet.

## Current ownership

- `local_game_server.py:10548` reproduction owns a one-second loop, active-player map discovery, native geometry indexing, and calls the reproduction domain. Each observe/attempt/publish operation acquires COMBAT_GROUPS then HARVESTS locks and takes fresh player/harvest snapshots.
- `maps/monster_reproduction.py:95` performs random draws, population scans, destination search, native child construction and validation inside the authoritative transaction. Population advisory lock, group row lock and timer row lock fence births. A planting-cell advisory lock and recheck fence planted-resource collision. Receipt and outbox commit with the child/group mutation. Dungeon populations are explicitly excluded.
- `maps/monster_maturation.py:122` locks group and timer, chooses a next stage, constructs the native grown actor and validates its group before committing receipt/outbox. Identity is preserved. Tick publication shares the same in-memory fences as reproduction.
- `local_game_server.py:10680` wandering performs snapshot, occupancy scans and all path planning while COMBAT_GROUPS and HARVESTS are held. `maps/monster_wander.py:153` plans member paths; `combat/combat_group_store.py:98` commits position-only changes with exact old-members CAS and available status, incrementing revision. Publication follows within the world fence.
- PersistentGroups is DB-authoritative, not a large in-memory group cache. Its RLock serializes local publication/claim ordering; SQL status and revision protect durable claims (`combat_group_store.py:164`).
- Harvest occupations are genuinely in memory: `maps/monster_collect.py:186` owns pending/targets, and begin adds the reservation after lease, native rule and reachability checks. An external SQL writer cannot see these occupations today.
- Corpses are durable (`maps/monster_corpses.py`). `expire:205` sets expiry_published and returns removal packets. Sending occurs later in world under the group fence. Moving this function unchanged to another process risks marking an event published before delivery; an acknowledged outbox is required.

## Safe protocol: external domain planning, bounded world commit

The worker must own actual policy evaluation, geometry indexing, native actor construction, group occupancy scans and path planning. A cron HTTP call that executes the existing heavy tick in world does not satisfy extraction.

1. World exposes a bounded snapshot for requested active scopes: world boot epoch, snapshot token, current players and harvest targets, durable group revisions/members/status, and a policy/version fingerprint. The worker loads pinned native catalogs and geometry directly, not by asking world to compute them. Durable timers/population/resources can be queried directly from PostgreSQL.
2. Worker produces one proposal per operation. Envelope includes boot epoch, operation ID, scope, expected group revision and members digest, timer cycle/reference where applicable, policy fingerprint, planned destination/path or replacement actor, and reproducible random draws/choices. Birth identities must be allocated durably exactly once; a retry must never invent another child for one cycle.
3. World accepts a bounded batch asynchronously. Under COMBAT_GROUPS then HARVESTS, validate epoch, current scope presence, unchanged group/status/revision, unoccupied actor and current player/cell occupancy. No geometry loading, full-map scan or native construction belongs under this lock. Authoritative transaction still rechecks timer, population cap and planting-cell lock before committing. Invalid/stale proposals are rejected without mutation and recomputed externally; no fallback to an expensive local tick.
4. Publish committed native packets in world under the same fence and acknowledge durable outbox entries only after publication. Reconnect snapshots remain DB-authoritative. A retry with a receipt is idempotent and does not consume another cycle or repeat births.

Existing attempt functions cannot simply receive precomputed packets: native actor validation and expected configuration must remain authoritative. Extract pure preparation from commit, then validate the small proposal against pinned native definitions and precise preconditions. Do not trust arbitrary worker-provided stats or IDs.

## Alternative for fully external commits

Direct worker commits require durable, generation-safe harvest occupations plus a cross-process fencing protocol for world claims and publication. Both world and worker would have to acquire the same DB/advisory fences, validate live occupancy epochs, and use a durable outbox consumed by world. Merely adding a Redis lease does not make the current in-memory HARVESTS.targets snapshot authoritative. This is a larger migration than externally planning with bounded world commits.

## Proposed implementation order and regression gates

1. Wandering: extract pure scoped planning first, preserve exact-members CAS, available status, native directed-edge checks and all-step packet ordering. Reject proposals after fight claim, harvest begin, roster change, movement, boot change or player collision. Test multiple member movement and stale proposal retry.
2. Maturation: split native construction/choice from atomic timer and group commit; preserve cycle receipts, no-catch-up presence timers, identity and publication fences. Test duplicate completion and simultaneous harvest/combat claim.
3. Reproduction: split population/geometry/native planning from commit with population and planting-cell revalidation. Test cap races, plant collision, dungeon exclusion, duplicate ticket and restart.
4. Corpses: convert expiration publication to durable acknowledged events before externalizing expiry calculation. Test worker/world restart between commit and acknowledgement, harvest consumption versus expiry, and actor scope isolation.

Population scans can be expensive but cannot be replaced by stale snapshot counts without transaction-level cap validation. Worker failures must pause ecology only; combat, harvesting and movement continue. Every worker request and response needs explicit time/size limits, bounded retries, boot fencing and metrics for planning, queue delay, commit rejection and publication lag.


## Implementation draft

`wakfu_server.ecology_mobs.prepare(store, snapshot, limit=16)` now constructs JSON-safe proposals externally. It performs geometry indexing, random policy decisions, native actor construction, timer observation and path planning. `apply(store, groups, harvests, world, proposal, world_epoch=...)` rejects old world epochs and policies, rechecks live presence/harvest and all intermediate movement collisions, and retains world-owned CAS/publication fences. Reproduction and maturation accept an optional prepared proposal; the legacy call paths remain supported. Their existing durable timer/receipt/outbox transactions still own mutation and replay idempotency.

Outbox publication proposals are emitted independently of pending timers, so a committed cycle can recover publication after an interruption. Birth identity allocation during preparation can leave harmless sequence gaps after stale proposals; it does not create a group or receipt. The committed receipt determines the one actual offspring for a cycle. Prepared reproduction performs aggregate population count and proposed-cell checks in SQL under its population lock rather than hydrating all world member graphs in Python.

Worker integration must process snapshots in order and retain world monotonic `now_ms`, boot epoch, previous active locations and wander interval gating (`allow_wander`). No HTTP calls occur inside the module's live fences. Corpse acknowledged outbox and initial population extraction remain outside this implementation draft. This is not deployed; parent integration and full regression validation are required.
