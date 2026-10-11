# Palacio Zollo: native parallel routes and return cycle

Map1397 contains two symmetric native branches between entryregion105 and bossregion0. The complete graph returns from the boss to entry before using the sole exterior exit.

| Route | Native transitions |
| --- | --- |
| Upper branch | 105 →34741→90 →Door34749→41 →Door34750→13 →34744→0 |
| Lower branch | 105 →34740→91 →Door34751→42 →Door34752→18 →34745→0 |
| Completed return | 0 →34746→105 →34747→map1384 `(-115,-63,16)` |

Native transports34742 and34743 additionally return the lower/upper first branch regions to entry. All native routes, objects and terrain remain in the independent graph evidence.

| Region | Cells | Validated six-player/eight-enemy anchor |
| --- | ---: | --- |
| Entry105 | 405 | `(-16,-1,4)` |
| Upper90 | 301 | `(-86,35,0)` |
| Lower91 | 301 | `(-84,-41,0)` |
| Upper41 | 406 | `(-111,38,8)` |
| Lower42 | 404 | `(-109,-38,8)` |
| Upper13 | 293 | `(-140,36,16)` |
| Lower18 | 298 | `(-138,-40,16)` |
| Boss0 | 411 | `(-216,-13,2)` |

All eight large regions support combat formations; geometry alone cannot identify regions13/18 as noncombat transit. Assigning entry asstage1,90/91 asstage2,41/42 asstage3, and13/18/0 asstage4 is a possible explicit local staging policy, not independently proved official encounter placement. Native guide/manual evidence must resolve this distinction before claiming official four-room fidelity.

The JSON contains directed native arrival-to-anchor paths, entry walking and anchor-to-departure paths for both branches. The SVG has one panel per large region, preserving XYZ source values in cell tooltips. No invented cells, teleports, runtime or client edits are used. Reproduce with `server/tools/render_palacio_zollo_native_geometry.py` and read-only native catalog access.

## External encounter-role resolution

Parent research subsequently confirms two alternative four-encounter routes, selected at entry: Lin Kuei or Shinlay. Region105 is the lobby, not encounter1. The encounter sequences are90→41→13→boss0 or91→42→18→boss0. Regions13/18 are actual third encounters, not transit. Native geometry supports both alternatives and the boss-return cycle; runtime branch-aware spawning is handled separately. Sources: [MethodWakfu Wabbit quest context](https://methodwakfu.com/quetes/principales/ile-des-wabbits/) and [Wakfu.Guide level126–140 dungeons](https://wakfu.guide/donjons/126-140/). This supersedes the provisional four-stage local grouping discussed above.
