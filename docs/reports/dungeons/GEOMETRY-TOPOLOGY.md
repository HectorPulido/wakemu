# Automatic native dungeon geometry extraction

**Follow-up:** [Native Tofu exploration flow](TOFU-NATIVE-FLOW.md) resolves the entry gap below using the installed player movement profile `Sm(6,0,4,true)`. This older bulk extraction intentionally retains the published combat profile `Sm(3,0,2,true)` as its input.

Offline evidence only. No runtime configuration or services changed.

Exact native coordinates and movement edges are used. Native bBk → bEG → Nm → Re inherits bet() = false; bEG collision writes VD.a(x,y,z,blocked), which marks the exact native surface. The analysis deliberately models all exported Door cells closed; hidden/inactive baseline objects may not block in game. Scripts and combat unlock triggers are not inferred.

```json
{
  "native_maps": 151,
  "extracted_maps": 151,
  "maps_with_doors": 98,
  "maps_with_separator_candidates": 87,
  "door_objects": 434,
  "exact_separator_candidates": 211
}
```

| Map | Native cells | Open regions | Door-blocked regions | Doors | Separator candidates |
|---|---:|---:|---:|---:|---:|
| 153 | 366 | 10 | 12 | 3 | 2 |
| 154 | 786 | 44 | 44 | 0 | 0 |
| 165 | 660 | 12 | 14 | 3 | 2 |
| 202 | 945 | 15 | 18 | 18 | 5 |
| 295 | 1378 | 24 | 29 | 5 | 5 |
| 296 | 1936 | 52 | 55 | 3 | 3 |
| 301 | 2606 | 118 | 121 | 6 | 4 |
| 311 | 864 | 17 | 19 | 2 | 2 |
| 325 | 824 | 44 | 44 | 2 | 0 |
| 330 | 2288 | 99 | 99 | 0 | 0 |
| 358 | 353 | 11 | 11 | 0 | 0 |
| 360 | 261 | 7 | 7 | 5 | 0 |
| 363 | 517 | 102 | 102 | 0 | 0 |
| 365 | 355 | 73 | 73 | 0 | 0 |
| 448 | 1252 | 36 | 38 | 4 | 4 |
| 456 | 1428 | 50 | 50 | 0 | 0 |
| 460 | 505 | 6 | 7 | 3 | 1 |
| 466 | 934 | 19 | 20 | 5 | 1 |
| 467 | 819 | 20 | 22 | 3 | 2 |
| 477 | 506 | 10 | 11 | 2 | 1 |
| 483 | 420 | 4 | 4 | 0 | 0 |
| 493 | 1407 | 39 | 41 | 3 | 2 |
| 495 | 1262 | 23 | 25 | 3 | 2 |
| 496 | 506 | 20 | 20 | 0 | 0 |
| 510 | 1150 | 47 | 49 | 3 | 2 |
| 515 | 486 | 5 | 6 | 3 | 1 |
| 516 | 1345 | 38 | 38 | 0 | 0 |
| 517 | 356 | 1 | 2 | 3 | 1 |
| 518 | 476 | 13 | 14 | 3 | 1 |
| 545 | 566 | 49 | 49 | 4 | 0 |
| 548 | 1010 | 19 | 21 | 4 | 3 |
| 549 | 334 | 11 | 11 | 0 | 0 |
| 559 | 482 | 6 | 8 | 3 | 2 |
| 704 | 272 | 4 | 5 | 3 | 3 |
| 712 | 554 | 4 | 5 | 3 | 1 |
| 716 | 1203 | 59 | 61 | 3 | 2 |
| 795 | 547 | 19 | 19 | 0 | 0 |
| 798 | 753 | 23 | 24 | 3 | 1 |
| 806 | 557 | 10 | 11 | 3 | 1 |
| 816 | 360 | 61 | 61 | 0 | 0 |
| 851 | 427 | 7 | 8 | 3 | 1 |
| 854 | 590 | 20 | 21 | 10 | 3 |
| 901 | 449 | 12 | 14 | 3 | 2 |
| 902 | 1422 | 34 | 37 | 4 | 4 |
| 909 | 677 | 15 | 17 | 3 | 2 |
| 910 | 503 | 15 | 18 | 5 | 4 |
| 911 | 517 | 26 | 29 | 3 | 3 |
| 912 | 1173 | 45 | 46 | 5 | 1 |
| 916 | 753 | 16 | 18 | 13 | 4 |
| 917 | 615 | 25 | 26 | 15 | 3 |
| 955 | 412 | 11 | 12 | 3 | 1 |
| 959 | 335 | 19 | 19 | 0 | 0 |
| 963 | 423 | 14 | 15 | 3 | 1 |
| 965 | 783 | 63 | 65 | 5 | 3 |
| 1000 | 482 | 4 | 4 | 2 | 0 |
| 1006 | 714 | 19 | 20 | 3 | 1 |
| 1007 | 570 | 16 | 17 | 3 | 1 |
| 1054 | 701 | 19 | 19 | 2 | 0 |
| 1056 | 221 | 4 | 4 | 0 | 0 |
| 1079 | 1057 | 54 | 54 | 0 | 0 |
| 1086 | 1088 | 9 | 9 | 0 | 0 |
| 1087 | 671 | 13 | 15 | 3 | 2 |
| 1091 | 586 | 8 | 10 | 2 | 2 |
| 1092 | 987 | 35 | 35 | 0 | 0 |
| 1126 | 827 | 36 | 37 | 3 | 1 |
| 1127 | 807 | 18 | 20 | 3 | 2 |
| 1128 | 803 | 37 | 39 | 2 | 2 |
| 1129 | 478 | 36 | 36 | 3 | 0 |
| 1130 | 717 | 30 | 31 | 3 | 1 |
| 1131 | 603 | 14 | 16 | 4 | 2 |
| 1132 | 1248 | 32 | 34 | 3 | 2 |
| 1133 | 585 | 14 | 15 | 4 | 1 |
| 1156 | 6911 | 161 | 161 | 0 | 0 |
| 1159 | 326 | 6 | 6 | 2 | 0 |
| 1204 | 326 | 6 | 6 | 2 | 0 |
| 1223 | 441 | 27 | 27 | 8 | 0 |
| 1224 | 1180 | 32 | 37 | 6 | 5 |
| 1229 | 2709 | 2 | 2 | 0 | 0 |
| 1249 | 506 | 21 | 21 | 3 | 0 |
| 1250 | 1403 | 30 | 31 | 3 | 1 |
| 1254 | 1061 | 24 | 26 | 3 | 2 |
| 1255 | 607 | 17 | 18 | 3 | 1 |
| 1256 | 359 | 2 | 3 | 3 | 3 |
| 1257 | 903 | 36 | 38 | 3 | 2 |
| 1266 | 1334 | 27 | 29 | 2 | 2 |
| 1268 | 1034 | 36 | 36 | 0 | 0 |
| 1270 | 1027 | 16 | 16 | 0 | 0 |
| 1271 | 997 | 23 | 23 | 0 | 0 |
| 1281 | 1753 | 42 | 42 | 0 | 0 |
| 1282 | 1285 | 21 | 21 | 0 | 0 |
| 1283 | 1628 | 21 | 21 | 0 | 0 |
| 1284 | 1567 | 27 | 27 | 0 | 0 |
| 1294 | 383 | 7 | 7 | 2 | 0 |
| 1296 | 770 | 20 | 21 | 2 | 1 |
| 1300 | 724 | 19 | 19 | 0 | 0 |
| 1301 | 815 | 14 | 15 | 2 | 1 |
| 1308 | 765 | 19 | 20 | 1 | 1 |
| 1313 | 787 | 39 | 40 | 1 | 1 |
| 1314 | 276 | 5 | 5 | 0 | 0 |
| 1316 | 271 | 3 | 3 | 0 | 0 |
| 1318 | 279 | 8 | 8 | 0 | 0 |
| 1320 | 279 | 3 | 3 | 0 | 0 |
| 1322 | 274 | 3 | 3 | 0 | 0 |
| 1324 | 335 | 14 | 14 | 0 | 0 |
| 1328 | 748 | 22 | 23 | 1 | 1 |
| 1329 | 239 | 6 | 6 | 0 | 0 |
| 1330 | 262 | 5 | 5 | 0 | 0 |
| 1332 | 1187 | 50 | 50 | 0 | 0 |
| 1336 | 734 | 20 | 21 | 4 | 3 |
| 1341 | 902 | 11 | 12 | 1 | 1 |
| 1345 | 304 | 6 | 6 | 0 | 0 |
| 1347 | 262 | 6 | 6 | 0 | 0 |
| 1369 | 963 | 86 | 88 | 43 | 4 |
| 1370 | 1504 | 41 | 46 | 26 | 14 |
| 1371 | 1236 | 55 | 57 | 2 | 2 |
| 1372 | 1529 | 64 | 66 | 2 | 2 |
| 1373 | 1497 | 28 | 38 | 30 | 22 |
| 1391 | 1235 | 61 | 61 | 0 | 0 |
| 1394 | 529 | 16 | 17 | 2 | 1 |
| 1395 | 702 | 23 | 24 | 1 | 1 |
| 1396 | 1403 | 74 | 76 | 3 | 2 |
| 1397 | 2933 | 86 | 90 | 4 | 4 |
| 1398 | 549 | 1 | 3 | 2 | 2 |
| 1399 | 1534 | 57 | 57 | 0 | 0 |
| 1400 | 1680 | 15 | 15 | 0 | 0 |
| 1403 | 770 | 52 | 53 | 5 | 5 |
| 1405 | 770 | 52 | 52 | 0 | 0 |
| 1415 | 809 | 30 | 31 | 1 | 1 |
| 1416 | 1029 | 37 | 38 | 3 | 2 |
| 1418 | 607 | 19 | 20 | 1 | 1 |
| 1419 | 659 | 11 | 12 | 3 | 1 |
| 1422 | 648 | 44 | 45 | 1 | 1 |
| 1429 | 292 | 5 | 5 | 0 | 0 |
| 1435 | 390 | 21 | 21 | 0 | 0 |
| 1439 | 260 | 13 | 13 | 0 | 0 |
| 1445 | 643 | 32 | 32 | 0 | 0 |
| 1446 | 1833 | 99 | 99 | 0 | 0 |
| 1447 | 257 | 50 | 50 | 0 | 0 |
| 1450 | 709 | 23 | 25 | 2 | 2 |
| 1451 | 700 | 16 | 17 | 1 | 1 |
| 1452 | 1146 | 51 | 51 | 0 | 0 |
| 1453 | 1586 | 81 | 81 | 0 | 0 |
| 1454 | 945 | 15 | 18 | 17 | 5 |
| 1455 | 1216 | 37 | 39 | 2 | 2 |
| 1456 | 486 | 5 | 6 | 1 | 1 |
| 1457 | 359 | 2 | 3 | 3 | 3 |
| 1458 | 517 | 26 | 28 | 2 | 2 |
| 1459 | 1088 | 9 | 9 | 0 | 0 |
| 1460 | 864 | 17 | 19 | 2 | 2 |
| 1476 | 1667 | 25 | 25 | 0 | 0 |
| 1477 | 575 | 20 | 20 | 0 | 0 |

## Interpretation

A separator candidate connects two or more regions when its exact cell is removed along with the other Door cells. This establishes a possible physical gate, not room identity, progression order or victory condition. Nearby cells are never snapped to the door, because that would create unsupported evidence.

For map 1087 (Tofu), inspect the three exact Door records in topology.json. For map 1086 (Jalato), native teleport links connect separated regions. Both analyses use the same graph extraction.

102 inventory records with doors comprise 98 native definitions and four legacy-guide-only records/maps; this extractor covers the 151 native definition maps. The next automatic step is to bind native visibility/state and script/event dependencies to these candidate regions; ambiguous branches and missing native cells require explicit evidence before gameplay changes.

## Tofu and Jalato evidence

Tofu (1087) has 671 native walkable cells. Removing all three exported Door cells splits the main 622-cell component into regions of 182, 207 and 230 cells. Door 26874 connects the first two, and 26875 connects the last two. Hidden Door 26873 is not a separator and its native baseline visibility prevents blocking. The entrance destination `(14,-25,0)` belongs to a separate 37-cell component. The missing connection between that entry region and the encounter chain remains unresolved; neither the door IDs nor geometric distance establish the natural entry direction.

Jalato (1086) has 1088 native cells. Its internal native teleports connect region 0 → 5 → 3, with return links. Those connected components contain 247, 252 and 328 cells, respectively; decorative disconnected regions are preserved in the evidence rather than counted as encounter rooms. Alternate Neo-server teleport destinations and their criteria are preserved, not silently treated as reachable.

## Native collision evidence

Installed client bytecode confirms `bBk` extends `bEG`, then `Nm`, then `Re`. `Re.bet()` returns false and no intermediate override exists. The `bEG.a(VD,boolean)` collision updater calls `VD.a(int x,int y,short z,boolean blocked)`. That function writes a coordinate-specific surface obstacle (using a column optimization only when the column has one surface). `bEK` checks co-located interactive elements before clearing an obstacle; `Re.beu()` requires both its blocking flag and visibility. This supports exact-cell geometry analysis for native Door instances, but does not prove that every exported door starts closed or must unlock after a particular combat. The export itself omits dynamic obstacles by design.
