# Prepare complete static duel terrain before character row locks

The 15:02 UTC challenge acceptance took approximately 7.345 seconds. Sampled stacks showed one cold `published_geometry` preparation followed by one cold `NativeQISurfaces` construction, not duplicate decoding. The acceptance transaction already held both character row locks, causing the other session's health transaction to wait. Existing topology and QI caches avoid warm rebuilding but cannot eliminate an initial cold construction.

The live answer dispatcher now opts into prewarming before the acceptance transaction. A nonlocking read finds the pending invitation map, closes its connection, and builds a complete validated terrain bundle. The bundle retains strong references to the immutable prepared topology, verified native QI provider and provenance with the pinned catalogue revision. Arena construction consumes those references directly, even if their global LRU entries are evicted between phases.

The preflight read is only a performance hint. Final invitation ownership, expiry, session leases, positions and acceptance validation remain in the original locked transaction. The runtime rejects a changed map or catalogue revision. An actual acceptance without its required prewarm fails rather than performing a cold reconstruction under character locks. Existing domain callers without the optional prewarm callback retain their previous API behavior.

Normal PvE entry was audited: its group-selection lock is released before `local_arena`, and durable fight creation occurs afterward. The equivalent character-lock/cold-terrain pattern was not present there, so no PvE entry change was made.

Validation: three terrain preparation tests pass (strong source reuse without loaders, map/revision rejection, complete source/provenance retention and revision pinning); six existing duel arena/formation tests pass; changed modules compile. PostgreSQL acceptance/rollback/stale/decline and lock-boundary regression validation is delegated. No costly live benchmark, restart or deployment was performed.

Remaining cost: cold terrain preparation still consumes CPU and delays the requesting acceptance, but no longer holds the duel character row locks during full map loading. Arena selection, final snapshot production and registration still execute in the authoritative transaction. This change does not claim to eliminate all duel entry latency.
