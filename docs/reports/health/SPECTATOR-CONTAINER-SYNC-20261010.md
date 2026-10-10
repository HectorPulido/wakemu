# Spectator synchronization after summon construction

Live fights 121–125 repeatedly rejected spectator refreshes with `Unverified native remote effect container absence`. Fight 125's durable checkpoint contained 38 retained records. Only constructor state carriers 34 and 37, owned by summoned actor 33, disagreed: ownership explicitly recorded a null parent container, while their serialized payloads contained type 11 and identity 315031602 from the outer summoning spell.

Direct state application bypassed the dispatcher's running-container scope. The nested constructor correctly selected a null-container runtime, but its serializer inherited the spawning spell's ContextVar. Direct applications now establish their own authoritative container scope and restore the parent scope on success or failure. Strict remote-effect validation remains unchanged. Existing inconsistent checkpoints are not silently rewritten.

The publication path compounded the mismatch: it rebuilt a full snapshot before forwarding any committed public action. A rejected refresh therefore froze already initialized spectators; late entrants could receive the last cached placement snapshot. Existing subscribers now continue receiving committed public events if snapshot rebuilding fails. The cached snapshot is explicitly marked stale, and new entries cannot consume it until a successful full refresh. Pending entries materialize only at a current snapshot. Spectators retain no participant turn or reward authority.

Regression coverage checks nested null-container state serialization and ownership, parent scope restoration on exceptions, existing observer movement/summon delivery during snapshot invalidation, late entry freshness, future events after entry, and existing summons in the active bootstrap roster. Deployment and final test results are tracked in the release report.

Manual acceptance: use separate accounts A and B on the same map. First let B observe during placement, then have A start, move, summon, and attack; B must see each action. Repeat with B entering after A has already summoned: B must see the current summon immediately and all subsequent movement/actions. Finish or surrender, then repeat a fresh fight to confirm no stale subscription or marker remains. No spectator should receive participant rewards or hold up A's turns.

## Deployment

Deployed full current checkout as `wakemu-world:performance-20261009-r62`. All 657 source/migration hashes match the running container. PostgreSQL health and both game ports were verified. Previous image retained as `wakemu-world:backup-r61-before-spectator-fix`. Continuous profiler recreated against the new process. Root ran all four dispatcher-publication tests successfully; full combined final validation status is reported separately. No checkpoint rewrite or migration was introduced.

Manual acceptance uses two clients on a fresh encounter: enter during placement, then observe movement, a new summon and a cast; repeat entering after a summon already exists; finish by surrendering and confirm the world marker disappears. Observers must not receive participant rewards or prevent turn progression.

## r63 follow-up: placement movement and existing summon entities

Hector confirmed surrender marker cleanup and normal spectator combat actions in r62. He then clarified that placement differs because moving the Cra leaves the observer at its previous cell, not merely because the observer UI hides placement zones. The public event allowlist omitted authoritative placement positions (13652); these are now forwarded. Native action flush (13420) was also omitted and is now preserved in order.

A native cva bootstrap enumerates actor IDs but resolves existing client entities before applying their state. Existing summons therefore require their recorded native creation descriptors, not merely roster stats. Late bootstrap now replays the actual stored creation packets, flushes their native action batch, refreshes current effects and stats, and flushes the complete snapshot. It uses the same descriptor authority as owned reconnect and does not fabricate summon data.

Focused validation: 115 tests ran, 100 passed, 15 skipped because they require an isolated PostgreSQL database. The placement regression checks the unchanged 12806 route invokes the actual drain, then executes that drain with 13652 through the real public event filter. It does not execute the entire session branch. Snapshot tests verify creation and flush ordering. Live acceptance remains pending.
