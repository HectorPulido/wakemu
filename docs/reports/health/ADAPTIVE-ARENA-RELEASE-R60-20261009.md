# Adaptive arena release r60 — 2026-10-09

## Behavior

Automatic ordinary encounters now stop at the first deterministic BFS prefix with at least 25 mutually reachable native cells, reserving 12 player placement cells plus at least 12 enemy placement cells (more for larger monster rosters). This is a bounded greedy search, not a global minimum-area proof or a guaranteed 5×5 square. Directed detours expand until return paths exist. Smaller native components remain usable when all actual participants fit. Both rectangle area including holes and selected cell count remain capped at 2,500. Explicit budgets retain their previous behavior; duels retain their original anchored positions and radius policy.

Published geometry is validated and frozen once per catalog revision/map, in a bounded 16-map cache. Forward/reverse adjacency is reused. Mutable raw dictionaries are freshly prepared on every call, so edits cannot silently reuse stale geometry. Native edges, heights, ambiguity rejection, LOS and spell rules are preserved. A separate native surface constructor optimization interns immutable values locally while validating every raw surface.

## Validation and performance

Luna ran 75 focused tests in 9.705 s before removal of an unrelated proposed scene-retry patch. That proposed patch and its prototype test were withdrawn because update-only retries could leave newly loaded interactives absent. Root subsequently ran 38 geometry/adaptive/arena/duel/surface tests in 0.326 s successfully. Earlier focused checks cover movement, range/wire parity, LOS, placement, surface provenance and directed-cycle expansion. This does not constitute a passing full server suite.

Inside the existing world container, prepared geometry selection preserved complete outputs on real maps 1134 and 527 for both automatic selection and explicit 2,500-cell budgets. Warm automatic selection: 1134 1.593→0.192 s; 527 3.796→0.421 s. One-time preparation: 0.432 and 0.981 s respectively. These are isolated benchmarks, not measured live click-to-combat latency. The previous live 22-second arena stage remains unexplained until a fresh post-deployment capture.

The full current shared server image was built as `wakemu-world:performance-20261009-r60`, and 649 Python/migration source hashes were verified against that image before deployment. Catalog revision is unchanged. Previous image is retained as `wakemu-world:backup-r59-before-adaptive-arena`. No database migration was introduced. Deployment completed: the running world matches all 649 verified source hashes, health reports PostgreSQL OK, and ports 15556/15558 accept connections. Continuous profiling is running against the new process (start ticks 2848030), with a reported 109.94-second deployment capture gap.

## Manual acceptance

1. Reconnect after the restart. On an outdoor map, run `!mob 1 10 1`. Click the group once and record elapsed time until placement appears. This first test exercises cold caches; repeat a second encounter for warm comparison.
2. Check the arena is small around the player, respects walls/heights and contains distinct positions for both teams. It may be elongated in corridors; no square floor is invented.
3. Press Ready. Move along an available route, cast a short-range spell and then a longer-range spell at a valid target. Walls and obstacles must still block movement/LOS; spells outside native range must remain invalid.
4. Finish the encounter, then create a group with `!mob 1 10 8`. Confirm every enemy is present and nonoverlapping, and placement/movement work. The arena grows when needed.
5. Have a second client observe an ongoing encounter and finish it. Check both return to exploration and rewards go only to participants. Report local time and last action for any delay.

Duplicate interactive registration after combat remains a documented open issue; this release does not claim to fix it. Beacon visibility/activation remains deferred.

## Follow-up acceptance evidence and limitations

Hector reported much faster entry after r60. A subsequent live summary recorded three start-fight requests, maximum 156.61 ms and mean 92.28 ms server processing time; this excludes client rendering/network latency. Two casts still reached 1,237.59 ms and three AI turns 1,201.19 ms, so this is not a claim that all combat latency is eliminated.

Manual screenshots exposed insufficient maneuvering room and relocation of a distant monster toward the player. A follow-up revision is being prepared to vary minimum dimensions, preserve feasible original enemy separation, and reserve free maneuvering cells beyond placement zones. r60 itself does not contain that follow-up.
