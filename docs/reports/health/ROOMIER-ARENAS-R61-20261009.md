# Roomier adaptive arenas r61 — 2026-10-09

Ordinary encounter selection draws independent minimum width and height from 5–7, covering all nine combinations. These are minimum targets, not final wire dimensions: preserved attack separation, obstacles, placement capacity and maneuvering space can require a larger arena. An optional explicit variation seed makes retries reproducible; ordinary new encounters vary by default. Duels retain their anchored radius policy.

The rectangle-first search attempts to include reachable original monster positions whose combined rectangle fits the 2,500-cell cap, preserving initial attack distance instead of always pulling monsters toward the player. It pads the preferred coordinates where native terrain permits and aims for at least 12 maneuvering cells beyond formation capacity in the interior. Irregular terrain uses a bounded directed-reachability fallback. Rectangle area includes holes. No terrain, height or native edge is invented.

Placement prefers interior cells. Rendered combat borders are always disjoint from both placement zones and their actor seeds. On open terrain the padding produces actual interior placement. At native walls or in extremely narrow components, full geometric padding may be impossible: native actor positions and collision rules are retained, and border flags are suppressed beneath unavoidable edge placement cells. This best-effort fallback avoids rejecting playable encounters or moving the player silently.

Validation: 65 focused tests passed in 11.57 s, covering all nine minimum dimension pairs, original enemy separation, disjoint interior zones, narrow corridors, doorway walls, movement, range/wire parity, LOS, surfaces and bootstrap. Root additionally ran 43 geometry/adaptive/arena/duel/surface tests in 0.553 s. The full server suite has not been established as passing.

Isolated benchmarks inside the existing world container: map 1134 selection+placement 0.301 s, 73 selected cells/36 interior; map 527 0.632 s, 78 selected cells/38 interior. Both preserved an enemy at distance ten and produced 12 placement slots per team with no rendered-border overlap. These are not live end-to-end latency measurements.

## Acceptance

1. Reconnect. Spawn `!mob 1 10 1`, walk roughly 8–10 cells away while keeping the group reachable, then click it once.
2. Confirm the enemy retains its starting separation when terrain permits. Both teams and their selectable positions should be inside the visible green boundary, with free maneuvering space.
3. Repeat three encounters from different positions. Minimum dimensions vary; final shapes adapt to native terrain and distances.
4. Press Ready, move and cast short/long-range spells. Native walls and LOS must still behave normally. Finish and check rewards and return to exploration.
5. Repeat in a narrow passage. Combat should still start; no green border should be drawn beneath either actor or a selectable placement square. Native walls can prevent full geometric padding there.

The interactive-registration issue after combat and deferred beacon behavior remain separate open issues.

Deployment completed with the full current checkout as `wakemu-world:performance-20261009-r61`. All 649 source/migration hashes match the running container, PostgreSQL health is OK, and both game ports accept connections. r60 is retained as `wakemu-world:backup-r60-before-roomier-arena`.
