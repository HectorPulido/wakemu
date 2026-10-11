# Palacio Zollo: authentic parallel routes and completed native return

The native definition73 is **Palais Lenald**, not Palais du Tsu. Reviewed guides describe a choice between two paths at entry, each with three preliminary encounters and the same final boss. [Wabbits quest guide](https://methodwakfu.com/quetes/principales/ile-des-wabbits/) and [level126–140 dungeon guide](https://wakfu.guide/donjons/126-140/) distinguish the alternatives. The eight large native regions therefore cannot be treated as an entry fight followed by two fights and a boss: region105 is the common noncombat lobby.

[Independent native geometry](PALACIO-ZOLLO-NATIVE-GEOMETRY-REVIEW-20261010.json) proves both routes and six-player/eight-enemy formation capacity. [Candidate evidence](PALACIO-ZOLLO-NATIVE-CYCLE-CANDIDATE-V14-20261010.json) records separate formation and complete native-sequence witnesses for each branch. Source-only preparation is separate from runtime activation and independent PostgreSQL acceptance.

| Branch selection | First encounter | Second encounter | Third encounter | Shared boss |
| --- | --- | --- | --- | --- |
| Native34741 | region90 (-86,35,0) | region41 (-111,38,8) | region13 (-140,36,16) | region0 (-216,-13,2) |
| Native34740 | region91 (-84,-41,0) | region42 (-109,-38,8) | region18 (-138,-40,16) | region0 (-216,-13,2) |

The left physical gates are34749 and34750; the right gates are34751 and34752. Sources34744 and34745 connect their respective third rooms to the common boss. Sources34743 and34742 return from the first rooms to the lobby. After the boss, native34746 returns to lobby105, then exterior source34747 leads to the original exterior map1384. There is no fabricated final exterior object. Return34746 explicitly carries the nonadjacent gate3 contract and does not advance progress or create another victory receipt.

`topology.branch_routes` scopes each route's actual spawn cells, anchors and literal arrivals. Global stage1 movement retains the lobby and both first-room regions; stages2/3 retain both alternatives, while stage4 is shared. Durable selection occurs at the native entry transport before the first encounter spawn. The lobby never receives a preliminary fight. A selected route must remain pinned for the complete run, including reconnects and party arrivals; the unselected branch must not provide a bypass or duplicate encounters.

The roster is explicitly local progressive ordinary-family composition with the verified native boss only at the end. It is not a certification of official quantities or boss mechanics. Every branch separately passes offline formation, actual-entry ingress, arrival-to-enemy engagement, previous-frontier closure, next native gate/source approach and completed boss-to-lobby-to-exterior return. Native cells and walking edges are preserved exactly; projected transport edges are used only for offline reachability checks.

## Version14 branch ownership correction

Version12 evidence remains frozen. Version14 declares exact `physical_source_ids` per branch:34749/34750 for entry34741 and34751/34752 for entry34740. Native transport `source_ids` remain ports only. The movement and native object-state layers must reject unselected branch cells and gates; owning only transports was insufficient to establish this invariant. Both branches retain the same literal geometry, encounters and offline route witnesses. Independent lifecycle validation must additionally probe unselected physical gates and cells before accepting this replacement.

## Frozen JSON integrity correction

Version14 normalizes plan, topology and route through JSON before calculating evidence hashes. After all offline checks, the builder verifies each evidence hash and the full canonical round-trip before writing. The report explicitly separates canonical JSON SHA256 from serialized file SHA256. Reloaded artifacts passed all checks. Config file SHA256 `605770c3320c15ed0bff81c972e3242d97f5a55bc4d5810227a33842e936c148`; config canonical SHA256 `043ef3d42425bf8cac5abe31e91adad676aa355924bd4d0674fddebb95d00a6b`; report file SHA256 `5803d4bece50acd0f107d45ef47a8c218a00426f0ec157bbc913fadf16a07eef`. PostgreSQL lifecycle acceptance remains separate.
