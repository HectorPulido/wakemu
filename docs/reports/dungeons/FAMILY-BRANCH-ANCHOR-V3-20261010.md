# Native combat anchor scan — branch V3, 2026-10-10

V3 is additive to the frozen 13-configuration V2 report; it does not modify V2 candidates. No runtime writes or combat engine changes were made.

The source tool scans actual native combat cells inside each stage, retaining only cells directed-reachable from the native arrival with future gates closed. Candidate anchors are evaluated by the existing six-player formation algorithm; coordinates are never snapped or invented. The final selected configuration also passes the full directed encounter/gate/exterior-exit sequence.

| Dungeon | Result | Stages |
| --- | --- | ---: |
| Ciudad Prohibida | blocked | — |
| Mekafábrica | offline_configuration_prepared | 3 |

Mekafábrica now has a valid three-stage local family configuration with an identified final boss. Anchor substitutions are recorded in the JSON report. Ciudad Prohibida still has no valid first-stage formation for six players and one through eight monsters, even after scanning every native eligible anchor. This is a concrete capacity/terrain blocker, not a missing family roster.

Verification uses the original native exploration and combat graphs, existing `enemy_formation`, `validate_dungeon_flow_rosters` and `validate_prepared_physical_flows`. Independent PostgreSQL lifecycle results are tracked separately.
