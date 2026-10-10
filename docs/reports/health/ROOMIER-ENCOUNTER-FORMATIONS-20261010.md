# Roomier encounter formations and unoccupied visible borders

## Selection behavior

Each automatic encounter draws independent minimum width and height values from 5 through 7. All nine pairs are supported. A supplied variation seed makes the draw reproducible for retries.

Selection first preserves reachable original monster positions when their combined rectangle fits the 2500-cell rectangle budget. It prefers rectangular native crops around those positions and the unchanged player position. Native holes, altitudes, directed reachability and ambiguity removal remain authoritative; no floor cells are synthesized. A bounded BFS fallback handles irregular native components and relocates monsters only when preserving their positions is not feasible in the chosen safe component.

The rectangle seeks interior capacity of at least `max(minimum_area, 12 + max(12, monster_count) + 12)`. For ordinary small encounters this leaves room beyond two 12-cell placement zones. Minimum dimensions are not fixed final dimensions: native obstacles, actor distance, padding, and maneuvering space can require a larger crop. Smaller native components remain usable.

## Border behavior

Preferred actor coordinates receive one-cell padding where native terrain permits it. Additional placement cells prefer the interior. Relocated monsters also prefer available interior cells.

A native wall or narrow corridor can make true interior placement impossible. Such terrain does not force an entry failure or silently move the player. Formation selection retains native collision rules and falls back to available native cells. The displayed combat perimeter excludes every actor seed and every selectable placement cell, including this fallback. Therefore the displayed green border is always disjoint from the full placement zones. This does not claim that a native map wall disappears or that every narrow corridor gains four walkable neighboring cells.

Explicit-budget arena callers and duel positioning retain their existing selection contracts.

## Validation and benchmark

The delegated focused suite passed 65 tests, including all nine dimension draws, stable seeds, distant enemy preservation, padding on open terrain, 12 slots per team, border disjointness, narrow corridor fallback, native-wall fallback, movement, spell range/wire, and native LOS.

An isolated benchmark inside the current world container used published native geometry and an enemy approximately ten cells from the player. Geometry preparation was completed before measurement; measured time covers selection plus placement generation:

| Map | Time seconds | Selected cells | Interior cells | Team slots |
| --- | ---: | ---: | ---: | --- |
| 1134 | 0.301 | 73 | 36 | 12 + 12 |
| 527 | 0.632 | 78 | 38 | 12 + 12 |

Both cases preserved the original enemy position and had no overlap between visible borders and placement zones. Private inputs, harness, and `roomier-benchmark-result.json` are under `.runtime/local/diagnostics/fight117-entry/`.

This benchmark excludes catalog loading, surface loading, actor initialization, and subsequent spell execution. End-to-end latency and visible formation still require live acceptance after deployment.
