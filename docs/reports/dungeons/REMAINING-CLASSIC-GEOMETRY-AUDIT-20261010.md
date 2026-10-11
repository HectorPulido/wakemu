# Remaining classic dungeon geometry — 2026-10-10

This audit covers exactly the 70 distinct classic dungeon names outside the baseline 37 active ordinary dungeons. It excludes Neo variants, ultimate bosses, rifts, arcade definitions and the two inactive level variants of the already-active Mineral Tower. No runtime state was changed.

## Findings

- 31 routes have a proved linear physical chain or open geometry. Their remaining blocker can be monster identity, roster, combat formation or exit binding; this audit does not certify those layers.
- 20 routes contain internal native transports. Their exact source approaches, destination positions and progression relationship still require a supported runtime binding.
- 19 routes do not fit the current linear physical-room controller. Seventeen have branching room graphs and a reachable exterior exit with all doors open; this does not establish the intended fight sequence.
- Patapinxería has incomplete directed travel to both exterior exit objects. Campos Hupremos has a branching graph and neither exit object is directed-reachable from the native arrival, even with all door cells available.

Approximate family rosters do not repair terrain edges or identify which branch must contain the boss. Choosing a branch without a declared local progression policy could omit the final room or strand the party. No positions were moved to nearby walkable cells.

## Per-dungeon evidence

| Dungeon | Native map | Geometry blocker | Door count | Internal transport count | Exit witnesses |
| --- | ---: | --- | ---: | ---: | --- |
| Factor Trool | 483 | native_internal_transport_graph_requires_exact_room_binding | 0 | 6 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Ala de la Embajadora | 515 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Blópera | 1223 | physical_room_graph_requires_review | 8 | 0 | branched_region_graph / reachable; branched_region_graph / reachable |
| Caverna Brizlónica | 1126 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Caverna Samaraciosa | 1127 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Base del Susurro | 448 | physical_room_graph_requires_review | 4 | 0 | branched_region_graph / reachable; branched_region_graph / reachable |
| Castillo de Wagnar | 330 | native_internal_transport_graph_requires_exact_room_binding | 0 | 7 | directed_path_incomplete / unreachable; directed_path_incomplete / unreachable; directed_path_incomplete / unreachable; physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable; directed_path_incomplete / unreachable; directed_path_incomplete / unreachable |
| Castillo del Wey Wabbit | 1399 | geometry_proved_roster_or_formation_pending | 0 | 0 | physical_linear_chain_proved / reachable |
| Ciudad Prohibida | 1256 | physical_room_graph_requires_review | 3 | 0 | branched_region_graph / reachable |
| Hacienda de la Topera Oculta | 1128 | native_internal_transport_graph_requires_exact_room_binding | 2 | 2 | disconnected_region_graph / reachable; disconnected_region_graph / unreachable |
| Hacienda de la Balinería | 911 | native_internal_transport_graph_requires_exact_room_binding | 3 | 2 | directed_path_incomplete / unreachable; directed_path_incomplete / unreachable; directed_path_incomplete / unreachable; physical_linear_chain_proved / reachable |
| Mazmorra Abráknida | 202 | physical_room_graph_requires_review | 18 | 0 | branched_region_graph / reachable; branched_region_graph / reachable |
| Meseta Pikapik | 798 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Mazmorra Solgazanes | 1281 | native_internal_transport_graph_requires_exact_room_binding | 0 | 2 | physical_linear_chain_proved / reachable; directed_path_incomplete / unreachable |
| Mazmorra de los Escapatarazones | 1301 | geometry_proved_roster_or_formation_pending | 2 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Mazmorra iBúho | 917 | physical_room_graph_requires_review | 15 | 0 | branched_region_graph / reachable; branched_region_graph / reachable |
| Mazmorra de Anutropía | 854 | physical_room_graph_requires_review | 10 | 0 | branched_region_graph / reachable; branched_region_graph / reachable |
| Mazmorra Ferocirraptores | 1416 | physical_room_graph_requires_review | 3 | 0 | branched_region_graph / reachable; branched_region_graph / unreachable; branched_region_graph / reachable |
| Mazmorra Gelatinada | 559 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Mazmorra Máquinas de Nox | 1418 | geometry_proved_roster_or_formation_pending | 1 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Mazmorra Martilloseco | 1371 | geometry_proved_roster_or_formation_pending | 2 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Mazmorra Fallecinerados | 1372 | geometry_proved_roster_or_formation_pending | 2 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Mazmorra Milubo | 1266 | native_internal_transport_graph_requires_exact_room_binding | 2 | 8 | disconnected_region_graph / unreachable; disconnected_region_graph / reachable |
| Mazmorra Negraspora | 806 | geometry_proved_roster_or_formation_pending | 3 | 0 | directed_path_incomplete / unreachable; physical_linear_chain_proved / reachable |
| Mazmorra Pezgajosos Abisales | 1370 | physical_room_graph_requires_review | 26 | 0 | branched_region_graph / reachable; branched_region_graph / reachable |
| Mazmorra de los Devastadores | 1341 | geometry_proved_roster_or_formation_pending | 1 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Mazmorra Riktus de Élite | 301 | physical_room_graph_requires_review | 6 | 0 | branched_region_graph / unreachable; branched_region_graph / reachable |
| Mazmorra Sramvil | 851 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Mazmorra Steamers | 1373 | native_internal_transport_graph_requires_exact_room_binding | 30 | 8 | disconnected_region_graph / reachable; disconnected_region_graph / unreachable |
| Mazmorra Nievajas | 1283 | native_internal_transport_graph_requires_exact_room_binding | 0 | 2 | physical_linear_chain_proved / reachable; directed_path_incomplete / unreachable |
| Mazmorra de los Idos | 1336 | physical_room_graph_requires_review | 4 | 0 | branched_region_graph / reachable; branched_region_graph / reachable |
| Mazmorra Tripulación del Pulpo | 1369 | physical_room_graph_requires_review | 43 | 0 | branched_region_graph / reachable; branched_region_graph / reachable |
| Mekafábrica | 916 | physical_room_graph_requires_review | 13 | 0 | branched_region_graph / reachable; branched_region_graph / reachable |
| Fosa del Atormentador | 795 | geometry_proved_roster_or_formation_pending | 0 | 0 | physical_linear_chain_proved / reachable |
| Jawdín de la Weina | 1398 | geometry_proved_roster_or_formation_pending | 2 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Kokolost Island | 295 | native_internal_transport_graph_requires_exact_room_binding | 5 | 2 | disconnected_region_graph / unreachable; disconnected_region_graph / unreachable |
| Antro Olvidado | 712 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Arena Danzante | 549 | geometry_proved_roster_or_formation_pending | 0 | 0 | physical_linear_chain_proved / reachable |
| Montaña Conohos | 1224 | native_internal_transport_graph_requires_exact_room_binding | 6 | 2 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Patapinxería | 963 | physical_room_graph_requires_review | 3 | 0 | directed_path_incomplete / unreachable; directed_path_incomplete / unreachable |
| La Pischina | 912 | geometry_proved_roster_or_formation_pending | 5 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Laboratorio de Womewo | 1396 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Larventura | 902 | physical_room_graph_requires_review | 4 | 0 | branched_region_graph / reachable; branched_region_graph / reachable |
| Glaciar Cornudo | 517 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| El Hammalmejil | 548 | physical_room_graph_requires_review | 4 | 0 | branched_region_graph / reachable |
| Astrolillo | 456 | native_internal_transport_graph_requires_exact_room_binding | 0 | 18 | directed_path_incomplete / unreachable; physical_linear_chain_proved / reachable |
| Miasmausoleo | 965 | physical_room_graph_requires_review | 5 | 0 | branched_region_graph / unreachable; branched_region_graph / reachable |
| Cono de Crújian Jerry | 510 | native_internal_transport_graph_requires_exact_room_binding | 3 | 2 | directed_path_incomplete / unreachable; directed_path_incomplete / unreachable |
| Vid Vil | 1079 | native_internal_transport_graph_requires_exact_room_binding | 0 | 6 | physical_linear_chain_proved / reachable; directed_path_incomplete / unreachable |
| Campos Hupremos | 910 | physical_room_graph_requires_review | 5 | 0 | branched_region_graph / unreachable; branched_region_graph / unreachable |
| Ratacumbas | 477 | native_internal_transport_graph_requires_exact_room_binding | 2 | 2 | disconnected_region_graph / unreachable; disconnected_region_graph / reachable |
| Caseta del Yech'Ti'Wawa | 518 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Necromundo | 1403 | physical_room_graph_requires_review | 5 | 0 | branched_region_graph / reachable |
| Necrópelis de Morbax | 296 | native_internal_transport_graph_requires_exact_room_binding | 3 | 4 | disconnected_region_graph / reachable; disconnected_region_graph / unreachable; disconnected_region_graph / unreachable |
| Palacio de Tsu | 165 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Palacio Zollo | 1397 | native_internal_transport_graph_requires_exact_room_binding | 4 | 7 | disconnected_region_graph / reachable |
| Pastos de los Jalatós | 1086 | native_internal_transport_graph_requires_exact_room_binding | 0 | 4 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable; directed_path_incomplete / unreachable; directed_path_incomplete / unreachable; directed_path_incomplete / unreachable; directed_path_incomplete / unreachable |
| Guarida de los Magik Riktus | 1249 | native_internal_transport_graph_requires_exact_room_binding | 3 | 4 | physical_linear_chain_proved / reachable; directed_path_incomplete / unreachable |
| Guarida de los Supervillanos | 704 | physical_room_graph_requires_review | 3 | 0 | branched_region_graph / reachable |
| Tymabar | 1250 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Colmena Madre Arenóptera | 1395 | geometry_proved_roster_or_formation_pending | 1 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Santuario de Mihmol | 816 | geometry_proved_roster_or_formation_pending | 0 | 0 | physical_linear_chain_proved / reachable |
| Santuario de los Dragohuevos | 1132 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Escarantera Abandonada | 909 | native_internal_transport_graph_requires_exact_room_binding | 3 | 1 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Sliptorium | 325 | native_internal_transport_graph_requires_exact_room_binding | 2 | 4 | physical_linear_chain_proved / reachable; directed_path_incomplete / unreachable |
| Guarida de los Tejaroxores | 1130 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Templo del Gran Orrok | 955 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Teatro Intemporal | 1429 | geometry_proved_roster_or_formation_pending | 0 | 0 | physical_linear_chain_proved / reachable |
| Torre de las Miss Adefesio | 154 | geometry_proved_roster_or_formation_pending | 0 | 0 | directed_path_incomplete / unreachable; physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |
| Pestrucería Abandonada | 495 | geometry_proved_roster_or_formation_pending | 3 | 0 | physical_linear_chain_proved / reachable; physical_linear_chain_proved / reachable |

## Reproduce

```sh
PYTHONPATH=server python3 server/tools/audit_remaining_dungeon_geometry.py
PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_remaining_dungeon_geometry_audit.py
```

The JSON report retains exact exit positions and per-route failure statuses. Four focused regression tests pass. Full dungeon activation requires separate family/boss evidence, combat formations, exit contracts and PostgreSQL lifecycle validation.
