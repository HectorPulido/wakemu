# Vid Vil: four native arenas and revisited hub

This version11 source candidate replaces the incomplete three-encounter spine. It does not change native walking cells, edges, transport endpoints or exterior destinations. Activation and manual acceptance are separate. [Frozen configuration evidence](VID-VIL-NATIVE-HUB-CANDIDATE-V11-20261010.json) records placement and complete directed route witnesses. [Independent geometry evidence](VID-VIL-NATIVE-GEOMETRY-REVIEW-20261010.json) confirms all four arenas and literal arrivals.

The actual encounter order is region0→region1→region28→region14. The native visit path is **0→1→28→1→14**: after the third encounter, players must return through the already completed second-room hub to reach the boss branch. The previous simple-path extractor omitted region28.

| Stage | Native region | Arena anchor | Actors | Native-minimum composition score |
| --- | ---: | --- | ---: | ---: |
| 1 | 0 | (-7,0,0) | 2 | 268 |
| 2 | 1 | (91,-70,0) | 4 | 540 |
| 3 | 28 | (265,-260,0) | 6 | 816 |
| 4 | 14 | (165,-144,0) | 8 | 1099 |

These are explicitly local progressive family quantities, not a claim of official encounter composition or scripted difficulty. Native bosses4060 and4061 appear once each, only in stage4. Native ordinary roles are required for generated preliminary actors; no dominant, archmonster, unknown role or initial summon is generated. Eight enemies and six players fit every native arena.

Literal transport bindings are26745(1→2),26746(2→1),26751(2→3),26750(3→2),26747(2→4),26748(4→2). Entry cancellation uses26744 and completed native final exit uses26749. The two nonadjacent bindings explicitly declare `progression_gate_room: 3`. This is an opt-in mixed-native contract; other candidates retain adjacent-only offline defaults.

Forward26747 requires the destination frontier4 and the committed victory receipt from destination-minus-one, stage3. Looking up its source-stage2 receipt would incorrectly permit skipping the third encounter. Reverse26748 requires both stages unlocked, preserves progress and creates no victory receipt. Source and destination IDs, positions and approach cells remain literal native catalog data.

Offline checks prove actual entry ingress, formation engagement from literal arrivals, unavailable future arenas before the preceding victory, return from third arena to the hub source26747, and final native exit approach. Projected transport edges are used only in offline formation reachability; the configuration retains the original native walking graph. Independent PostgreSQL lifecycle acceptance is tracked separately by Luna and is not implied by these offline checks.

Source configuration: `.runtime/local/vid-vil-native-hub-v11-20261010/native_dungeon_115.json`, file SHA256 `6d082d4cc46ff43b2f959c9e1f242d02bb6b847dfca112a29d325ed744db5ac3`. Frozen report SHA256 `b531381e1d6acb1ee8d2de1b2d07ffc10be15c1a8d910705e09c48341801c448`.
