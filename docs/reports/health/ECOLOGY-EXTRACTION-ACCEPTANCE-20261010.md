# Ecology service acceptance

Ecology is deployed in external mode. The shared deployment currently uses `wakemu-world:admin-actions-20261010-r77` and `wakemu-ecology:admin-actions-20261010-r77`, pinned to complete catalog `1d428d93dd4eeea23c81d10230b33e7bfd897671930efaf8d56ac1c0e82b19f6`. World, ecology, AI and the reattached profiler report healthy. Manual gameplay acceptance remains pending.

The first startup exposed an independent concurrent spell implementation's required resource-cost catalog. A temporary rollback attempt also encountered newer applied migration history. Final startup uses the full shared implementation and the complete cost-only catalog; no missing-authority guard was bypassed. The existing migration 104 was restored byte-for-byte and its later additions moved to migration 110.

Live smoke verification stopped ecology, committed a diagnostic setting and observed dirty revision 4 while processed revision remained 2. World health returned HTTP 200 in 21.5 ms. After ecology restarted and the diagnostic setting was removed, revision and processed revision both reached 5, with no pending proposals. A world-container request to ecology returned authoritative weather for map 235. The diagnostic setting was deleted.

Focused automated evidence includes 94 planting/cancellation/harvest tests, 24 growth/publication/intent/batch tests, 39 creature lifecycle tests, 61 service/population tests, three prepared-creature PostgreSQL tests, 25 upgrade/service tests, 31 query/bridge/transport tests, 19 final transport tests, 11 mining tests, 32 focused combat lifecycle tests and 14 repaired-fixture lifecycle tests. These batches overlap and are not a full-suite total. A separate 30-test class/resource gate passed against the required catalog. Old fixture failures were corrected where owned, or explicitly excluded from that separate class gate; this is not a claim that the entire repository test suite passes.

## Ownership and delivery

World commits gameplay changes and durable dirty-scope events in the same PostgreSQL transaction. It does not issue a synchronous HTTP request to ecology to publish an event. Ecology owns growth, mineral refill planning, monster reproduction, maturation and movement planning, initial population preparation, corpse expiry planning and weather advancement. Interactive planting preparation also runs there.

World retains the final inventory, occupation, combat and position checks and bounded client publication. These checks prevent stale proposals from spawning a monster on a player, consuming a superseded planting request or changing an active fight. Delivery is at least once, with version guards and durable receipts; a socket write is not a client acknowledgement.

The internal authenticated query API exposes population and weather with observation metadata. Query callers must run outside gameplay locks and honor the timeout and completeness metadata. The cached snapshot endpoint explicitly reports that it is not authoritative. Ordinary combat does not depend on an ecology HTTP response.

## Complete manual acceptance

Use two connected characters, A and B. Record the map and coordinates with `!position` before starting.

1. In a normal outdoor planting area, run `!item 1752 10` to receive ten wheat seeds. Plant one seed in a free nearby cell and stay still. Expect the planting animation, exactly one seed consumed on successful completion, a visible resource for both clients and subsequent growth. Move immediately after starting a second planting. Expect cancellation without a late phantom planting or extra consumption. Native planting duration/profession/probability rules still apply.
2. Repeat planting inside an installed garden room in the Haven Bag. Expect the existing garden restrictions to hold; planting outside an allowed room must still fail. Leave and re-enter and confirm the resources persist.
3. Run `!monster 2 4 1` to create one level-four black Gobbly near A. Start the fight near planted resources. Move, cast, summon and finish the fight while B watches. Expect normal placement, turn progression and rewards; active fighters must not move because of ecology. The defeated group must not reappear from an old proposal. This checks preservation; it does not certify unrelated pending spell or spectator issues are resolved.
4. Observe outdoor groups over multiple movement cycles. Expect legal movement and normal population behavior. Revisit a cleared initial population after reconnecting; initialization must not refill defeated groups merely because the player returns.
5. An operator stops only ecology with `docker compose stop ecology`. A and B should still move, start a fight, cast and finish. Planting preparation and ecological timers can wait while the service is unavailable. Restart with `docker compose start ecology`; expect queued work to resume without duplicated seed consumption or rewards.
6. Run `docker compose ps ecology world`, then inspect `docker compose logs --since 5m ecology`. Expect healthy services and no repeated domain errors. A reconnect during service recovery must not apply a request from an earlier character session.

Stopping ecology intentionally pauses its features; it must not switch ownership back to legacy world workers. Rollback to inline mode is an explicit deployment operation and must restore the weather scheduler configuration as well.
