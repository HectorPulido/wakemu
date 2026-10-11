# Ordinary dungeon counts — 2026-10-10

Counts are derived from the installed client inventory, not a claim about a different live client release.

| Scope | Count |
| --- | ---: |
| Classic ordinary dungeon definitions | 109 |
| Classic ordinary dungeon distinct native French names | 107 |
| Neo ordinary dungeon variants, excluded from classic count | 11 |
| All ordinary definitions including Neo | 120 |
| Arcade definitions, excluded | 6 |
| Ultimate-boss definitions, excluded | 15 |
| Infinite/ultimate-wave definitions, excluded | 10 |
| All native definitions | 151 |

The sole exact native-name duplicate among classic ordinary definitions is La Tour Minérale: IDs 133, 134 and 164, levels 36, 186 and 201. These are three level variants of one named dungeon, producing 109 definitions but 107 distinct named dungeons. Five additional legacy guide records in the union inventory are not proven current native definitions and do not increase this count.

Of the 47 read-back activated flows, 37 are ordinary classic dungeons and ten are ultimate bosses. None of the 37 are Neo variants, and no two activated ordinary definitions share a native dungeon name: ordinary coverage is **37/107 distinct named dungeons**, or **37/109 classic definitions**. Seventy distinct classic dungeon names remain outside this validated active-flow set. This does not certify boss mechanics or imply pre-existing generic configurations are absent.

Following [individual review of the final eleven](FINAL-ELEVEN-INDIVIDUAL-REVIEW-20261010.md), source preparation covers **107/107 distinct ordinary names and 109/109 level-specific definitions**. The [latest structural audit](FINAL-ELEVEN-ALL-CLASSIC-STRUCTURE-AUDIT-20261010.json) has zero structurally blocked latest-source configurations. This source count does not change the historical activated baseline above and does not certify deployment, graphical acceptance, optional content or original boss mechanics.

Sources: `inventory.json`, `.runtime/local/methodwakfu-dungeons/native-dungeon-index.json`, and `MAXIMUM-ACTIVATION-READBACK-20261010.json`. Ordinary native types are DUNGEON_2_ROOMS, DUNGEON_3_ROOMS, DUNGEON_4_ROOMS and DUNGEON_3_PLAYERS; DUNGEON_ARCADE is excluded. Neo rows are the 11 explicitly Neo-named ordinary definitions. Distinct dungeon names are exact native `name_fr` values, without fuzzy merging.
