# Ecology extraction: planting and growth boundary discovery

The initial boundary review below precedes the selected implementation documented later in this report. Deployment belongs to the parent integration workflow.

## Existing authority

`maps/planting_runtime.Plantings` currently combines socket occupations (`pending`, cell exclusions, duration, cancellation), seed/domain preparation, SQL mutation, snapshots, growth and publication. `planting.prepare/complete` verify session lease, profession, owned inventory, origin, resource definition and cell uniqueness. Completion uses an operation receipt, consumes exactly one seed, updates profession/ecology and inserts the resource atomically. The accepted probability is server-resolved and frozen at occupation start.

`Plantings.mature` refills minerals, selects due flora/monster resources, locks and compares current resource rows, checks SQL harvest occupations, validates transition policy and records the random decision once. Flora stages and outbox change together. Monster growth allocates a native identity, creates a durable birth outbox and removes the seed resource. `monster_birth_ecology.activate` atomically registers the available group and applies personal ecology using a stable operation receipt. `PersistentGroups.register_transaction` has no socket or in-memory group-registration side effect; it can execute in ecology with a non-recovering store adapter.

`publish_growth` is presently serialized with harvest completion by a process-local publisher lock. World additionally wraps the complete growth cycle with the combat registry mutex. Neither mutex can become a cross-service safety mechanism.

## Concrete service boundary

Ecology owns native planting/resource catalogs, preparation and probability calculation, occupation tickets, duration/cancellation, ownership/SQL lease verification, seed consumption, resource transitions, mineral refill, ecology receipts, birth activation and durable publication records. World owns socket decoding/routing, live combat/harvest coordination, authoritative runtime garden/location context and delivery to connected players.

Use a versioned internal API with request identity, world boot identity and catalog revision:

- `planting.begin`: account/generation/character ID, raw request, authoritative live context identity. Return opaque ticket token and native start packet only after validation. Service reloads seed, profession and policy; percentages or definitions supplied by the client are never authoritative.
- `planting.complete`: opaque ticket, account/generation, raw result and current live context identity. Revalidate ownership/origin and consume once using the stable operation token. Retry returns the committed receipt.
- `planting.cancel`: token and generation; idempotent. Disconnect/restart invalidates live occupation generation.
- `resources.snapshot`: map/instance with revision; immutable packet delivery data.
- Autonomous growth loop: discover due rows, compute/commit domain mutations, request live occupancy reservation only when a monster will enter the world, and enqueue committed publication.
- `publications.claim/ack`: event identity/revision, world boot/delivery identity and expiry. Acknowledgement compares exact event revision; newer stages cannot be acknowledged by an older delivery.

Avoid RPCs while holding world registry, harvest or socket locks. Bound request size, elapsed time, batch count and retries. An ecology outage should defer operations without consuming a second seed, duplicating a draw or freezing combat.

## Required fences

A live occupancy snapshot is insufficient to authorize a later monster birth. World must issue a short explicit cell reservation token tied to location epoch, expiry and world boot. Movement/claim/harvest entry points must honor it until the commit outcome is known. This is a registry reservation, not a mutex held across a network operation. After a commit, the durable pending birth/outbox continues reserving the cell until activation/publication or explicit safe resolution. Expired service requests cannot create a new group using an invalid world epoch. A committed receipt must remain recoverable after a lost response.

Resource harvest and growth currently reuse the same outbox primary key (`resource_uid`) for multiple stages. Extraction needs a monotonic resource/publication revision or distinct event ID. A conditional acknowledgement by resource payload prevents marking a newer event as published, but does not prevent sending a stale packet first. Final delivery must validate the current durable revision and current world context under a short world delivery reservation; superseded packets must be dropped. Harvest SQL occupations and row comparisons remain authoritative for growth exclusion. Do not replace them with an advisory snapshot.

Birth activation preserves its one SQL transaction: planter row, population advisory lock, group registration, personal ecology operation receipt. Packet preparation uses the committed current group revision and status, never a pre-commit candidate. Existing aliases and native identity allocation remain intact. Ecology startup must not invoke world fight-reservation recovery.

Garden context is runtime-sensitive: stored character location alone is insufficient for a visitor inside another account's bag. Pass a server-authenticated context identity and validate its generation; do not trust arbitrary client coordinates or a prepared character blob. Cancellation on movement, combat, teleport and logout must remain immediate in world and mirrored idempotently to the service.

## Required automatic regressions

Cover duplicate/lost begin and complete responses; foreign generation/token; movement during occupation; cancellation and early completion; seed disappearance; changed garden context; occupied spawn cell; reservation expiry and service restart; claim versus birth race; harvest versus stage change; old publication after harvest or a newer stage; lost acknowledgement; exactly-once ecology/XP/random draw; duplicate native identities; boot mismatch and unavailable service. Domain state must match the existing in-process implementation for successful operations and malformed packet rejection.

Integration should preserve current immutable catalog revision and compare complete source builds before any world restart. The discovery phase introduces no optimization or source mutation.

## Selected implementation: read-only prepare, authoritative world apply

The selected first extraction uses `maps/ecology_plants.py`: service-side `prepare(store,snapshot,limit=16)` performs bounded due scanning and native monster construction without writes. JSON-safe proposals include the world boot, exact expected resource row, transition policy and prepared monster. Mineral proposals contain their exact respawn deadline. Pending publication proposals recover already committed mutations after a lost delivery.

World-side `apply(plantings,groups,proposal,authorize_spawn=...,publish=...)` performs one authoritative row comparison, checks live occupancy/harvest state and current policy, then reuses the existing atomic mutation/receipt/outbox logic. Monster identities are allocated only in the final transaction. Targeted publication reloads only that resource's current outbox row; mineral refill compares the exact deadline and enabled/inactive state. No remote durable writers race the world publication lock in this phase. Set `plantings.ecology_world_epoch` to the world boot and pass its configured growth delay in the snapshot.

This phase extracts growth scanning and expensive native monster preparation, with final domain CAS mutation still in world. Interactive planting begin/complete and probability preparation retain existing ownership, inventory debit and session/garden authority; this is not a claim that their complete execution has moved remotely. Tests cover read-only bounded JSON proposals, stale resource/policy/boot rejection, idempotent application, targeted publication and recovery after delivery failure. Existing growth/mineral/planting lifecycle regressions are required alongside the new suite.

## Interactive intent implementation

Migration 108 adds durable pending planting intents. World enqueue supersedes the previous pending intent for that character; all existing `Plantings.cancel` paths also cancel pending durable intents even if there is no local occupation. Ecology prepares at most four intents per plant batch, resolving native surface/adjacency, seed/profession eligibility, garden context and frozen planting probability. It returns a small actor identity/location projection, never a complete inventory/build payload.

`EcologyPlantingIntents.apply` locks and checks exact intent identity, world boot, actor, generation, version and raw request before calling the world callback. `Plantings.begin_prepared` validates current actor origin, canonical seed/resource definitions, session lease, seed ownership, profession, live cell callback and current duration. Occupation time starts only when world accepts the preparation. Completion keeps the existing atomic inventory debit, reward/ecology receipt and resource commit. A cancelled or superseded proposal cannot resurrect an occupation. Service preparation makes no durable domain changes.

Growth planning now rotates independent flora, monster, mineral and pending-publication quotas, using bounded advisory UID cursors per world epoch. Occupied monster cells from the snapshot are skipped while final world occupancy checks remain authoritative. This prevents permanently blocked oldest monster seeds from starving flora or crash-recovery delivery. The service worker supplies a monotonic planning tick; cursor reset after restart changes scheduling only, never committed receipts.

World integration now attaches the durable intent repository in external mode and queues opcode 13220 without an HTTP request or native terrain/probability work. Prepared proposals recheck the loaded actor generation, combat membership, origin, seed/profession ownership and live occupancy before accepting. Errors target the captured lease; growth and occupation announcements use strict ordered batch delivery. Inline mode retains its existing path.

Remote planting preparation uses a nonlocking read-only session check; heavy catalog and inventory hydration does not hold session/character `FOR UPDATE` locks. Final world acceptance and completion retain their locking lease checks. Empty movement cancellation stays in memory and opens no database connection. A scalar cancellation flag closes the race where cancellation happens before an enqueued INSERT is visible, without holding a local mutex across SQL. Additional tests cover that race, empty cancellation, runtime combat/generation rejection and actual native occupation delivery.

## Final automated verification

The focused ecology proposal suite passed 24/24 tests, including all eight plant fairness/growth cases and six ordered location-delivery cases (`.runtime/local/diagnostics/ecology-final-focused.log`). Bridge/weather verification passed 13/13 (`.runtime/local/diagnostics/ecology-bridge-final.log`). The final planting/cancellation/harvest invariant run passed 94/94 in 113.460 seconds, including the current eight interactive intent cases and both cancellation races (`.runtime/local/diagnostics/ecology-cancel-harvest-final-rerun.log`).

Command for the final invariant run: `WAKFU_MIGRATIONS_TEST_DIR=/Users/hectorpulido/Documents/wakfu-experiment/server/migrations PYTHONPATH=server:server/tests .runtime/local/performance-test-venv/bin/python /tmp/run_retained_runtime_suites.py test_ecology_planting_intents test_planting test_planting_runtime test_resource_occupations test_planting_growth_concurrency test_harvest_inventory test_resource_harvest_completion`. These results establish automated lifecycle coverage; full current-source deployment and manual client acceptance remain integration-owner responsibilities.
