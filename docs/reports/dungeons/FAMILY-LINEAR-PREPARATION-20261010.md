# User-authorized family encounters on proved linear dungeons — 2026-10-10

Twenty-seven additional classic dungeon definitions have source-only configurations, totaling 64 encounter stages. The previous 47 active native flows are untouched. Preparation does not claim runtime activation or certification of special boss mechanics.

The user explicitly authorized approximate same-family encounters when official compositions were unavailable. Every prepared room uses the native dungeon species pool, with the actual family boss identified from native BOSS property 43 evidence. Earlier rooms exclude the final boss; the final room contains exactly one. Alternate visitor bosses (Cire Momore, Anathar and Aguabrial) are excluded from ordinary additions. Quantities are local policy, never presented as official quantities.

The preparer preserves native room order, literal entry and exit contracts, gate progression and teleport endpoints. Six-player combat formation and an unobstructed engagement approach are checked in every room. Physical routes additionally validate locked and unlocked walking boundaries; teleport routes validate native arrival-to-engagement and arrival-to-forward-transport paths. Sliptorium retains its separately proven backward exit witness and still needs the previously documented server deployment before activation.

Guarida de los Magik Riktus is intentionally reduced from eight to four actors per encounter: eight and six passed formation placement but blocked the approach needed to engage in room three. Four passes both checks. This is a concrete example of why formation placement alone is insufficient.

## Prepared candidates

| Dungeon | Native definition | Rooms | Actors per room | Actual final boss reference |
| --- | ---: | ---: | ---: | ---: |
| Ala de la Embajadora | 9 | 2 | 8 | 2348 |
| Caverna Brizlónica | 122 | 2 | 8 | 4251 |
| Caverna Samaraciosa | 123 | 3 | 8 | 4231 |
| Meseta Pikapik | 83 | 2 | 8 | 2972 |
| Mazmorra de los Escapatarazones | 165 | 2 | 8 | 5235 |
| Mazmorra Gelatinada | 69 | 3 | 8 | 1345 |
| Mazmorra Máquinas de Nox | 201 | 2 | 8 | 5718 |
| Mazmorra Martilloseco | 186 | 3 | 8 | 5388 |
| Mazmorra Fallecinerados | 185 | 3 | 8 | 5382 |
| Mazmorra de los Devastadores | 180 | 2 | 8 | 5301 |
| Mazmorra Sramvil | 86 | 2 | 8 | 3080 |
| Jawdín de la Weina | 67 | 3 | 8 | 2570 |
| Antro Olvidado | 81 | 2 | 8 | 2768 |
| Glaciar Cornudo | 62 | 2 | 8 | 2363 |
| Caseta del Yech'Ti'Wawa | 8 | 2 | 8 | 2368 |
| Palacio de Tsu | 147 | 3 | 8 | 4918 |
| Tymabar | 144 | 2 | 8 | 2018 |
| Colmena Madre Arenóptera | 192 | 2 | 8 | 5478 |
| Santuario de los Dragohuevos | 129 | 3 | 8 | 4400 |
| Guarida de los Tejaroxores | 126 | 2 | 8 | 4318 |
| Templo del Gran Orrok | 99 | 2 | 8 | 3587 |
| Pestrucería Abandonada | 146 | 3 | 8 | 4871 |
| Mazmorra Solgazanes | 161 | 2 | 8 | 5176 |
| Mazmorra Nievajas | 163 | 2 | 8 | 5188 |
| Ratacumbas | 12 | 2 | 8 | 2313 |
| Guarida de los Magik Riktus | 138 | 3 | 4 | 4520 |
| Sliptorium | 48 | 3 | 8 | 1786 |

## Release and manual risk

Isolated PostgreSQL lifecycle validation is delegated independently; its report must be checked before runtime activation. Missing route registration and the deployed server module version must also be checked independently. This report cannot be used as proof that a route is live.

Highest manual priority: Magik Riktus (reduced room-three engagement), Sliptorium (backward final exit), Martilloseco/Fallecinerados/Devastadores (visitor-boss exclusion), Dragohuevos/Tejaroxores (Aguabrial exclusion), and the sixteen candidates whose native route lacked a legacy guide-base configuration. All candidates should be tested with a full party or heroes: native entry, first encounter, every victory gate, final singleton boss, ordinary exit, and fresh reentry. A party member leaving and rejoining mid-run must recover the same progression.

Machine-readable placement, sequence, boss evidence and quantity-reduction witnesses: `FAMILY-LINEAR-CANDIDATES-20261010.json`. Reproduce using `server/tools/prepare_family_linear_dungeons.py --boss-evidence docs/reports/dungeons/REMAINING-FAMILY-BOSSES-20261010.json` with the documented read-only catalog database environment. No client, combat or spell files are modified.
