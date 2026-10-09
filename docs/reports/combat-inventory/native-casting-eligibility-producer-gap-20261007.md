# Shared native casting eligibility: producer inventory

This inventory concerns the ordinary `fcj` contract called by `UseGateEffect`, independently of server resource/deck/usage validation. It does not execute a spell or require a portal. All work is offline.

| Native requirement | Existing authority | Remaining boundary |
| --- | --- | --- |
| Selected fyP range, LOS, linear, modifiable | Installed casting tables and signed range oracle | Complete; category modifier and actor characteristic snapshots remain required |
| Mandatory empty `cwU`, path option `cwN`, diagonal `cwT`, linear path `cwV`, self `cwE` | Corrected 4143-definition exporter and explicit level-zero catalog | Data complete; current normal target validator does not consume all restrictions |
| Fixed `gjl` terrain gate and `gtP` casting criterion | Raw aNr/bPS metadata now exported, including native parse presence | Criterion must be evaluated on actual target-cell context and admissible PVs; raw text alone is insufficient |
| Current-turn defaults | Native fch constructor has both toggles true | Need exact live fight turn identity snapshot, without deriving it from selected actor or a previous accepted cast |
| QI.aK / QI.P / QI.R / QI.j | Verified exported terrain and walkable sets are partial sources | Each distinct QI result needs its exact producer; membership in walkable cannot represent all predicates |
| fcr casting LOS | Native topology ray data, actor native heights and explicit obstacle footprints | Reuse authoritative ray source; missing height/footprints remain unknown |
| Root fKX shape versus QI collision | Installed root shapes and selectors exist | Native QI collision traversal and caster/target orientation required, not effect execution or children dispatch |
| Target sdR / caster sdG and level comparison | Explicit actor fight properties and levels | Exact target PV resolution includes areas and summons; do not select only living actor centers |
| Root selector acceptance | Installed native selector metadata | At least one actual root selector must accept the actual target; null selector has its native distinct behavior |
| Independent static alignment/path test | Newly exported flags; native bytecode captured | Diagonal branch and Sn path with actual footprint/occupancy and target obstacle temporary exclusion need authority. cwN's sixth-argument behavior must remain distinct from empty-cell checks |

Current `_validate_target` additionally checks resource/usage policy, which fcj does not. Its current target query uses living actor centers and its linear check lacks the native diagonal/path alternatives. Therefore invoking it as a UseGateEffect callback would change both accepted and rejected cases. A new reusable eligibility engine must calculate the ordinary fcj result and independent alignment/path result from one current snapshot, preserve evaluation of both calls, and avoid recursion through effect criteria or prepared spell execution.

The empty GATE manager can already answer HasValidGateForTp false without these casting sources. UseGateEffect itself requires the casting contract even when no gates exist. These two predicates must not be conflated.
