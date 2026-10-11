# Vid Vil: independent native route review

Map 1079 contains four large encounter regions linked through a revisited hub. Its native graph is not a simple linear chain: the complete route is region0 → hub1 → branch28 → hub1 → boss14. A simple-path extractor that forbids repeated regions cannot recover this full route.

| Encounter stage | Native region | Cells | Six-player/eight-enemy anchor |
| --- | --- | ---: | --- |
| 1 | 0 | 189 | `(-7,0,0)` |
| 2 | 1, revisited hub | 203 | `(91,-70,0)` |
| 3 | 28 | 307 | `(265,-260,0)` |
| 4 | 14 | 321 | `(165,-144,0)` |

Literal transition objects are 26745 (entry→hub), 26751 (hub→branch28), 26750 (branch28→hub), and 26747 (hub→boss14). Additional native returns 26746 (hub→entry) and 26748 (boss→hub) remain in the graph. There are no Door objects. ZoneTriggers26913 and26812 exist in branch28 and boss14; this review does not infer their scripted mechanics or replace them with physical gates.

Exterior objects26744 in entry and26749 in the boss arena both lead to map323 at `(59,-69,0)`. The entry destination is `(0,0,0)` in map1079.

The JSON records three valid combat anchors per arena, directed entry-to-anchor walking, native transport arrival-to-anchor walking, and anchor-to-native-departure walking for every segment of the required route. Every witness uses native XYZ edges. These checks establish reachability and placement, not runtime stage ownership or official monster composition. The runtime must allow returning to the already-cleared hub after stage3 while keeping the final branch unavailable until its prerequisites are met.

Reproduce with `server/tools/render_vid_vil_native_geometry.py` using read-only native catalog access. The standalone SVG uses one panel per arena and retains XYZ in cell tooltips; no teleport coordinates were invented. This source-only review makes no client, runtime or database changes.
