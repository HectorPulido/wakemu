# Native Zaap destination inventory —2026-10-11

Read-only snapshot of the currently published PostgreSQL catalog. These are ordinary Zaap destinations; no Merkasaco source object or route has been accredited. A single arrival height is required by the server.

| Reference | Native Spanish destination name | Map | X | Y | Arrival Z | Default known | Native criterion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 13999 | Zaap del Convento del Santo Tocón | 323 | -6 | -73 | [0] | False | `none` |
| 14539 | Zaap de Kuatropatas | 327 | -4 | 5 | [-50] | False | `none` |
| 18258 | Zaap de la banquisa | 504 | 8 | -19 | [0] | False | `none` |
| 18354 | Zaap del castillo de Kontatrás | 508 | -12 | 18 | [3] | False | `none` |
| 19248 | Zaap de las alcantarillas de Astrub | 546 | 9 | -7 | [0] | True | `none` |
| 19249 | Zaap del centro de Astrub | 527 | 0 | 32 | [0] | True | `none` |
| 19569 | Zaap de Bilbyza | 458 | 7 | -116 | [32] | False | `none` |
| 21870 | Zaap del arrecife de kiryuks | 794 | 0 | -8 | [0] | False | `none` |
| 22035 | Zaap del desierto del Picahari | 792 | -1 | -85 | [-80] | False | `none` |
| 22809 | Portal de Inglorium | 856 | -22 | -13 | [28] | False | `none` |
| 22810 | Portal de Sramvil | 843 | 70 | 21 | [-13] | False | `none` |
| 22811 | Portal de Anutropía | 853 | 38 | -73 | [8] | False | `none` |
| 23034 | Zaap de las Tierras Salvajes | 711 | -67 | -147 | [-40] | False | `none` |
| 25064 | Portal de Xelorium - Presente | 923 | 47 | 43 | [-39] | False | `none` |
| 25066 | Portal de Xelorium - Pasado | 922 | 47 | 43 | [-39] | False | `none` |
| 25154 | Zaap de Kelba | 943 | -100 | -47 | [-24] | False | `none` |
| 25362 | Portal de Zurcalia | 967 | 0 | -8 | [24] | True | `none` |
| 25593 | Zaap de Moon | 999 | -76 | -136 | [-80] | False | `none` |
| 26192 | Zaap de la escuela de hipermagia | 1017 | 5 | -57 | [-68] | False | `none` |
| 26730 | Zaap de Incarnam | 1076 | 44 | -1 | [-40] | False | `False` |
| 26878 | Zaap de Tainela | 527 | -224 | -34 | [0] | True | `none` |
| 26905 | Zaap del Bibliotemplo | 1089 | 0 | 0 | [25] | True | `none` |
| 27534 | Silo de la playa salvaje | 1118 | -9 | 3 | [0] | False | `none` |
| 27537 | Zaap de la playa del Zinit | 986 | 16 | -12 | [4] | False | `none` |
| 27682 | Zaap de la Feria del Trool | 337 | -3 | -109 | [2] | False | `none` |
| 27699 | Silo de la cueva de los brizlones | 1119 | 42 | -13 | [8] | False | `none` |
| 27714 | Silo de la ladera baja | 1120 | 3 | -12 | [0] | False | `none` |
| 28042 | Silo de la nave | 1121 | -3 | -1 | [0] | False | `none` |
| 28089 | Silo de la ladera alta | 1122 | -29 | -26 | [0] | False | `none` |
| 28090 | Silo de la cueva de Dor'Mor | 1123 | -4 | 1 | [-60] | False | `none` |
| 28208 | Silo de la cima | 1124 | -13 | -15 | [21] | False | `none` |
| 29080 | Silo de la Torre Mineral | 1202 | -4 | -2 | [0] | False | `none` |
| 31313 | Zaap de Brakmar | 1137 | 4 | -91 | [0] | False | `none` |
| 31314 | Zaap de Bonta | 1136 | 1 | 26 | [-50] | False | `none` |
| 31315 | Bahía de Sufokia | 1135 | -8 | 16 | [-60] | False | `none` |
| 31316 | Zaap de Amakna | 1134 | -10 | -10 | [-1] | False | `none` |
| 32011 | Zaap de Pandalucía | 1252 | -4 | -22 | [-80] | False | `none` |
| 32260 | Zaap del Reino Sadida | 1264 | 3 | 3 | [0] | False | `none` |
| 32627 | Portal de Osamosa | 1276 | -2 | -5 | [0] | False | `none` |
| 32863 | Zaap del Reino Susurrante | 1295 | -17 | 13 | [-58] | False | `none` |
| 33607 | Zaap de Ereboria | 1360 | -1 | 0 | [-42] | False | `none` |
| 34644 | Zaap de Rii, la isla celestial | 1385 | 3 | -22 | [7] | True | `none` |
| 34801 | Zaap de la Isla de los Wabbits | 1384 | 14 | 15 | [3] | False | `none` |
| 34999 | Zaap de la isla de la bruma | 1401 | 7 | -144 | [4] | False | `none` |
| 36157 | Isla desconocida | 455 | 62 | -212 | [5] | False | `((GetDate() >= GetDate(08,09,2026,09,00,00)) and (GetDate() <= GetDate(03,11,2026,08,59,59)))` |

Destination labels are read from native Spanish localization family36 (`content.36.<reference>`), matching the original destination `getName` consumer in `.runtime/haven-zaap-20261011/link-cost.javap.txt`. All45 labels resolve; map names have not been substituted. Localization snapshot: `.runtime/monster-combat-extraction-20261010/translations.json.gz`.
