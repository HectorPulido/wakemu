# Reusable validated combat geometry

## Change and contract

`combat_geometry.py` snapshots native map coordinates and directed edges into immutable frozensets, with read-only forward and reverse adjacency containing sorted neighbor tuples. Topology validation still checks every coordinate, endpoint, and cardinal XY adjacency before publication into the cache.

Published geometry is cached for at most 16 `(catalog revision, map ID)` keys. The native catalog pins its published revision for the process lifetime. This cache reads the published catalog directly, never mutable values returned to `map_geometry` callers. Arbitrary mutable dictionaries passed to arena selectors are freshly validated and snapshotted on every call; changing them cannot silently reuse a stale identity cache. A previously returned prepared snapshot remains detached from subsequent input mutation.

Both arena selectors reuse adjacency for induced-subgraph reachability and select edges only inside the resulting cells. This removes repeated scans of the full map edge set, including adaptive sizing checks. Directed movement, ambiguity removal, source height selection, BFS neighbor ordering, participant relocation, and bounded rectangle rules remain unchanged by this optimization. The separate adaptive arena sizing change is described in the release report.

## Validation

Added `test_combat_geometry.py`: five tests pass for mutable input isolation and revalidation, immutable graph values, induced-subgraph traversal equivalence, raw/prepared selector equality, and publication revision cache separation. The 14 arena selection tests also passed locally; the delegated focused regression run is reported separately by the release owner.

Differential benchmark ran inside the current world container using published map exports. The baseline was the adaptive arena implementation immediately before geometry reuse. Every returned field was compared for exact equality, including cells, directed edges, placements, relocations, bounds, and blocked ambiguous columns.

| Map | Mode | Baseline seconds | Prepared seconds | Returned cells |
| --- | --- | ---: | ---: | ---: |
| 1134 | Automatic | 1.593 | 0.192 | 25 |
| 1134 | Explicit 2500 | 1.775 | 0.173 | 1199 |
| 527 | Automatic | 3.796 | 0.421 | 25 |
| 527 | Explicit 2500 | 3.980 | 0.461 | 1896 |

All four outputs matched exactly. One-time preparation cost was 0.432 seconds for map 1134 and 0.981 seconds for map 527. Warm selection improved approximately 88–90% in this isolated benchmark. These numbers exclude catalog fetching, native surface loading, actor creation, and downstream combat initialization, and do not establish an end-to-end live latency guarantee.

Private benchmark inputs, harness, and `geometry-benchmark-result.json` are in `.runtime/local/diagnostics/fight117-entry/`. No world restart was performed by this subtask.
