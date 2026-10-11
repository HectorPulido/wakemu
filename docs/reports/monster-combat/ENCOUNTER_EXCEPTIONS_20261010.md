# Native encounter exceptions

The user explicitly requested that native minigame/mission actors remain unavailable until their game mode exists. They remain part of the complete monster inventory and coverage denominator; they are excluded from automatic activation at every level. These exceptions are not counted as functional monsters.

| Reference | Actor | Reason |
| --- | --- | --- |
| 3174 | Adiestrador de drago | Native zero-health training actor; ordinary living combat is incompatible. |
| 3976, 3980, 3981, 3982, 3983, 3984 | Jalató de carrera | Native racing prerequisites and directional geometry require the minigame. |

This accounts for 7 of the original 29 pending references (24.14%). Of the other 22, 17 are now activated and five remain pending; see the [current deployment report](REMAINING_ACTIVATION_20261010.md). The automatic selection and generated all-level inventory use `server/tools/monster_activation_exceptions.py` as their common explicit exception policy. Requests selecting excluded references fail closed. Existing native effects and criteria are preserved.
