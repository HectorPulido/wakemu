# Progressive native family compositions — 2026-10-10

The new mandatory policy is applied to fresh immutable V5 candidates. Previous candidate files and reports remain unchanged. Twenty-seven linear routes plus Laboratorio de Womewo are prepared with role filtering, deterministic native minimum levels, six-player formation and complete engagement/gate/exit sequences. Nothing in this preparation activates runtime configurations.

## What increases

The measurable progression proxy is the sum of actual spawned monster levels across an encounter. The runtime level selector for these configurations is `native_minimum`: it returns each species' native minimum level exactly, without random grade draws. Each subsequent room must have a strictly greater level sum. This guarantees the stated composition proxy, not overall combat difficulty or correctness of special boss mechanics.

The common validated formation capacity applies to every room. For four rooms at capacity eight, quantities are 2, 4, 6, 8; for three rooms they are 3, 6, 8. Lower-capacity routes reduce all rooms together. Equal native grades can still progress by quantity. A single-actor route can progress only when native species levels provide strict increases. The builder rejects equal or decreasing strength; it never silently labels equal encounters progressive.

Native world property 45 (`ARCH`) and 115 (`DOMINANT_NPC`) are excluded. Missing role metadata is excluded. Native BOSS property 43 actors are permitted only when identified for that dungeon, only once each and only in the final room. Explicitly unrelated visitor bosses remain excluded. Multiple distinct actual bosses in a legitimate final encounter are supported.

## Additional omitted routes

Laboratorio de Womewo (definition 74, map 1396) has a prepared complete V5 candidate. Its retained native gate order and full six-player formation pass.

Negraspora (84, map 806) remains blocked: the intended exterior approach `[-83,-10,9]` is outside the extracted closed terrain regions and is not directed-reachable even with all native doors open. The alternative exterior approach `[-37,1,0]` has no mandatory gate separating it from entry; treating it as the final exit would certify an early-return exit as the dungeon's progression endpoint.

La Pischina (143, map 912) remains blocked: both exterior approaches `[15,-26,20]` and `[21,38,0]` have no mandatory native gate separating them from arrival in the retained complete region graph. The older selected-path classifier suggested a linear gate, but the complete graph does not prove that gate unavoidable. This is a precise topology/progression evidence blocker, not a missing family or boss identity.

These unresolved routes need either the missing native topology/interaction evidence or an explicitly different local route policy. They are not silently reduced to final-only arenas and counted as complete dungeons.

## Prepared linear progression

| Dungeon | Room quantity / actual level sum |
| --- | --- |
| Ala de la Embajadora | 4 / 456 → 8 / 951 |
| Caverna Brizlónica | 4 / 336 → 8 / 701 |
| Caverna Samaraciosa | 3 / 339 → 6 / 684 → 8 / 941 |
| Meseta Pikapik | 4 / 470 → 8 / 974 |
| Mazmorra de los Escapatarazones | 4 / 816 → 8 / 1661 |
| Mazmorra Gelatinada | 3 / 300 → 6 / 600 → 8 / 818 |
| Mazmorra Máquinas de Nox | 4 / 936 → 8 / 1901 |
| Mazmorra Martilloseco | 3 / 159 → 6 / 324 → 8 / 461 |
| Mazmorra Fallecinerados | 3 / 120 → 6 / 240 → 8 / 345 |
| Mazmorra de los Devastadores | 4 / 876 → 8 / 1781 |
| Mazmorra Sramvil | 4 / 576 → 8 / 1183 |
| Jawdín de la Weina | 3 / 388 → 6 / 780 → 8 / 1063 |
| Antro Olvidado | 4 / 204 → 8 / 437 |
| Glaciar Cornudo | 4 / 396 → 8 / 819 |
| Caseta del Yech'Ti'Wawa | 4 / 396 → 8 / 819 |
| Palacio de Tsu | 3 / 204 → 6 / 414 → 8 / 581 |
| Tymabar | 4 / 636 → 8 / 1325 |
| Colmena Madre Arenóptera | 4 / 576 → 8 / 1181 |
| Santuario de los Dragohuevos | 3 / 564 → 6 / 1134 → 8 / 1541 |
| Guarida de los Tejaroxores | 4 / 748 → 8 / 1512 |
| Templo del Gran Orrok | 4 / 276 → 8 / 583 |
| Pestrucería Abandonada | 3 / 204 → 6 / 414 → 8 / 581 |
| Mazmorra Solgazanes | 4 / 816 → 8 / 1661 |
| Mazmorra Nievajas | 4 / 816 → 8 / 1661 |
| Ratacumbas | 4 / 284 → 8 / 590 |
| Guarida de los Magik Riktus | 2 / 194 → 3 / 291 → 4 / 404 |
| Sliptorium | 3 / 249 → 6 / 504 → 8 / 701 |
| Laboratorio de Womewo | 3 / 433 → 6 / 870 → 8 / 1183 |

Machine-readable evidence is in `FAMILY-LINEAR-PROGRESSIVE-CANDIDATES-V5-20261010.json`, `EXTRA-LINEAR-PROGRESSIVE-CANDIDATES-V5-20261010.json` and `FAMILY-COMPOSITION-POLICY-AUDIT-20261010.json`. Independent PostgreSQL lifecycle acceptance remains a separate release gate.

Eight focused unit tests cover equal-grade quantity progression, single-actor native-grade progression, impossible strict progression, role exclusions, final-only singleton/multiple bosses and rejection of incomplete/invalid release configurations.
