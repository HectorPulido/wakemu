# Storage, catalog, inventory and character optimization audit

Date: 2026-10-10. Scope: current shared checkout; read-only audit, no deployment or additional gameplay changes. Line references are audit-time references. Distinguish measured incidents from static opportunities; do not add timings across inclusive profiler spans.

## Ranked findings

| Priority | Finding and evidence | Safe next action |
| --- | --- | --- |
| P0 reliability, fix prepared | Position owner contention escaped the request boundary and disconnected a player during planting. The 16:34:58 UTC request failed before plant mutation with `TimeoutError: Position owner is busy; retry checkpoint`. | The prepared typed `PositionOwnerBusy` handler rejects only that action, preserves dirty write-behind data and keeps the connection usable. Validate in the complete image before deployment. |
| P1 measured lock amplification | `storage/store.py:171` health observation takes `sessions FOR UPDATE`, including `renew=False`. Session idle checks run at approximately one-second cadence (`local_game_server.py:3310,3522`), renewal every ten seconds. During the 15:02 duel incident, the challenge transaction held both participant lease rows while preparing terrain; another session was sampled blocked in health SQL. Acceptance lasted 7.345 seconds. | Current duel prewarming already moves cold terrain preparation before acceptance (`combat/friendly_duels.py:381-424`). Audit remaining transaction callbacks for CPU/network work while lease rows are locked. Consider a separate non-renewing observational SELECT, preserving strict generation and expiry validation at every mutation. Do not remove locks from writes. |
| P1 static, unquantified | `storage/store.py:376-454` hydrates the entire character: roster, account cosmetics, build capacity, progression, haven bag, containers, items and their extensions, secrets, mount state, shortcuts, builds and active selection. This is more than a dozen SQL statements before optional domain work. `items/inventory_items.py:125` calls this full loader while removing one item solely to inspect build equipment references. | Introduce an explicitly scoped build-reference reader for removal, under the existing lease/character transaction. Check every build exactly as today; preserve equipped-item rejection, item ownership and quantity checks. First instrument per-domain hydration wall time/query counts and compare under representative inventories. Avoid a mutable full-character cache. |
| P2 static, unquantified | `characters/captured_roster_store.py:9-17` performs `to_regclass` on every Osamodas character hydration, then reads its roster. Rolling-DDL fallback deliberately represents unknown authority, not an empty roster. | Cache schema capability only after a controlled startup/schema-generation check; never cache absence forever across migrations. Preserve unknown-authority rejection. |
| P2 static, unquantified | `storage/native_catalog.py:73-82` fetches and reconstructs the complete published document hash inventory on every `document_hashes()` call, although `release()` is process-pinned. | Cache an immutable revision-keyed inventory and return immutable data or defensive copies. Prove callers cannot mutate the shared authority. Measure call frequency first. |
| P2 cold-path latency and memory tradeoff | `storage/native_catalog.py:167-179` already shares parsed documents in a revision/path LRU of 32 entries, guarded by one global RLock. Cold decoding of any document serializes all catalog readers, including otherwise warm lookups. Raw catalog reads still checksum payloads; Redis caching is capped at 2 MiB, so large documents use PostgreSQL when parsed cache misses. | Measure hits, misses, eviction rate, decoded retained bytes and lock wait. If contention is material, use per-key single-flight decoding plus a small map lock, retaining checksum verification and shared immutable parsed authority. Do not increase cache count blindly: large documents can retain substantial Python graphs. |

## Existing protections that must remain

- Inventory extension hydration already batches by item UID: `inventory_elements.py:61`, `inventory_shards.py:178`, and `mount_inventory.py:55`. This audit found no per-item query loop in those hydration functions; replacing them with an N+1 path would regress performance.
- `position_redis.py:243` obtains scarce DB capacity before the account barrier. `position_buffer.py:131` attempts independent accounts so one failure does not prevent healthy accounts from flushing. Retain those boundaries.
- Position flushes preserve authoritative buffered coordinates, compare revisions before acknowledgement, and do not discard dirty journal entries on contention. Redis acknowledgement and SQL persistence are distinct stages; a successful zero-position checkpoint does not prove a stalled gameplay request executed.
- Catalog parsing is already cached. Historical parse/fingerprint/deepcopy stalls must not be reported as missing caches in current code without a fresh capture.
- The measured 7.345-second duel server request does not explain the entire approximately one-minute client placement freeze. Native creation/recovery and placement expiration require a separate protocol investigation; see the linked incident report.

## Evidence and validation

Measured incident details and private capture references:

- [Position contention disconnect](PLANT-POSITION-CONTENTION-DISCONNECT-20261010.md): request ID, boot, connection and preserved evidence. Prepared regression tests exercise busy rejection with no mutation, a subsequent successful request, and propagation of unrelated terminal timeouts.
- [Duel and session lock amplification](LIVE-SLOW-COMBAT-20261010-1502.md): exact request timeline and sampled terrain/SQL wait paths.
- [Cast latency](CAST-LATENCY-20261010.md): native effect CPU and outbound send timestamps; no demonstrated multi-second send queue wait in that reproduction.

No new benchmark or SQL EXPLAIN was run for the static opportunities above. No index deficiency, cache eviction rate, memory total, or percentage saving is asserted without measurement. The documentation-only audit requires no new behavioral test; the prepared position fix has its separate regression suite and complete-image validation remains owned by the parent task.

## Acceptance scenarios after verified changes

1. Keep two accounts active, start a duel, and move both characters during placement. Repeat on a cold map and a warm map. Neither account should stop receiving actions while terrain is prepared; placement must not expire before the client can act.
2. Keep a fight active while another account repeatedly checkpoints and plants. A busy position owner may produce one retry message, but no disconnect, duplicate seed consumption or lost plant. Retry must succeed after contention clears.
3. With several builds referencing equipment, attempt to delete an equipped item, an unequipped item and part of a stack. Equipped deletion must remain rejected; other removal must affect only the requested quantity and survive reconnect.
4. Load a large inventory containing identified items, shards and multiple mounts. Compare state and statistics before/after reconnect; batching or projections must not lose per-UID mount state or equipment authority.


## Cautious implementation review

Follow-up source inspection found only two `document_hashes()` callers: `tools/audit_class_initialization.py:58` and `tools/audit_ready_start.py:60`. Both are offline audit tools and each obtains the inventory once. A revision-keyed defensive-copy cache would preserve the caller contract, but would add retained process state without improving the current game runtime. The proposed cache was therefore withdrawn; neither production code nor tests retain that change.

The narrow inventory-removal projection is deferred in this batch. Although removal itself uses only the equipment field from each build, its current full-character loader also checks that the character is not deleted, validates build capacity and active selection, and validates owned mount/roster/inventory authority. Replacing it with a bare build-equipment SELECT would silently eliminate existing rejection boundaries. A future projection must explicitly preserve the relevant authority and malformed-state behavior before it can be called equivalent; no broad refactor or weakening was made here. No session-lock changes were made.
