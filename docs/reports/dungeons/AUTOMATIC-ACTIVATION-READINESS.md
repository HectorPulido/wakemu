# Automatic dungeon activation readiness

Eight frozen offline configurations now have native room flow, resolved species identities, validated formation and literal exterior exits. These support an explicit DEV acceptance scope for entry, spawn, durable victory gates and exterior return. The user explicitly authorized activation: seven configurations are active at version 3 and the accepted Tofu version 3 was preserved. See [activation evidence](AUTOMATIC-PHYSICAL-ACTIVATION.md).

None currently has complete native boss spell coverage. There is no generic damage fallback: `combat_npc_attack.ability()` authorizes only the audited Wonejo5525 attack; tactical NPC casts reject unsupported mandatory roots and end the turn when execution is unsupported. Activating the flow therefore does not establish a faithful or challenging boss encounter.

| Dungeon | Boss | Covered owned spells | Exact catalog gaps |
|---|---|---:|---|
| Trinchera de Huelguerreros | Throll (2774) | 0/4 | spell 4022 level 70: missing roots 105232,105234,105235,105233; spell 4021 level 70: missing roots 282292,282297,282293,282298; spell 4056 level 70: missing roots 107018,107020,107021,107019; spell 4020 level 70: missing roots 105219,105220,107616,107609 |
| Mazmorra de los Demorribles | Crateros, verdugo del fin (5289) | 0/3 | spell 7249 level 233: casting level unavailable; spell 7250 level 233: casting level unavailable; spell 7304 level 233: casting level unavailable |
| Mazmorra del Charcoso Real | Charcoso Real (4720) | 0/4 | spell 6417 level 128: missing roots 263666,263668,263665; spell 6418 level 128: missing roots 255914,255922; spell 6419 level 128: missing roots 255974; spell 6420 level 128: missing roots 256015,263794,263795,256016 |
| Mazmorra de los Fitoformes | Vaal'Enthia, reina demonio (5277) | 0/3 | spell 7234 level 233: casting level unavailable; spell 7235 level 233: casting level unavailable; spell 7265 level 233: casting level unavailable |
| Mazmorra de los Vaciantes | Ar'Nan, augurio del vacío (5283) | 0/3 | spell 7243 level 233: casting level unavailable; spell 7242 level 233: casting level unavailable; spell 7303 level 233: casting level unavailable |
| Cuerbokueva | Corbot C-800 (3696) | 0/4 | spell 4881 level 80: missing roots 153154; spell 4882 level 80: missing roots 153158; spell 4883 level 80: missing roots 153167,153170,153168,153171,153169,153172; spell 4884 level 80: missing roots 153181,153183,153182,153184 |
| Pasto Real | Muuugresa Real (4758) | 0/4 | spell 6533 level 53: missing roots 265288,265607; spell 6534 level 53: missing roots 265601,265301; spell 6535 level 53: missing roots 265590,265305; spell 6536 level 53: missing roots 265311,265596 |
| Tofullero | Tofu Real (1259) | 0/3 | spell 1155 level 23: missing roots 10113,183326,183327,10114; spell 5786 level 23: missing roots 183310,183336; spell 5791 level 23: missing roots 182847,183324,183325,183309 |

All eight pass actual reward settlement, atomic rollback and replay in isolated PostgreSQL: [economy evidence](AUTOMATIC-PG-LIFECYCLE-ECONOMY.json). Shared full-checkout build validation remains a separate deployment gate. Boss mechanics remain incomplete despite flow activation.

No substitute species, boss damage or spell ownership were invented. Missing ability data belongs to the NPC spell-catalog workstream; no combat engine changes were made here. Special boss AI, phases, summons, invulnerability and rewards require their own acceptance after root coverage.

Reproduce `PYTHONPATH=server python server/tools/audit_dungeon_activation_readiness.py`. [Machine-readable readiness](AUTOMATIC-ACTIVATION-READINESS.json), [native spell evidence](AUTOMATIC-BOSS-ABILITY-COVERAGE.json), [prepared configurations](AUTOMATIC-COMPLETE-CANDIDATES.md).
