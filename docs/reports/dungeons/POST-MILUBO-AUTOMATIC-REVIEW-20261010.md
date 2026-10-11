# Automatic review after the Milubo mixed-flow correction

This is source preparation and read-only structural review. It does not certify deployment, official boss mechanics, or graphical acceptance.

## General correction

The native graph now combines directed walking, physical door transitions and literal internal transport bindings. Small transit components may belong to an encounter stage; they are not automatically additional combat rooms. Within-stage transports preserve progression, while forward stage transitions require the preceding durable victory.

The previous extractor removed physical gates to identify terrain components, then followed only transport links. This made Milubo's entry appear isolated. The same mistake affects other dungeons with both connection types.

## Seven additional recovered main routes

The frozen [V7 candidates](HYBRID-NATIVE-FULL-ROOM-CANDIDATES-V7-20261010.json) retain native walking edges, exact transport endpoints and ordered main encounters. [Detailed recovery evidence](HYBRID-NATIVE-FULL-ROOM-RECOVERY-V7-20261010.md) describes formations, gate states and exclusions. Fresh isolated PostgreSQL lifecycle verification passed for all seven configurations: six-player admission, every room victory/replay and spawn receipt, literal native progression, final exit state and instance closure. [V7 lifecycle evidence](HYBRID-NATIVE-FULL-ROOM-PG-LIFECYCLE-V7-20261010.json) binds the exact configurations and source. Tests of former single-encounter fallbacks are not used as proof of the recovered routes.

| Dungeon | Main encounters | Previous limitation | Explicit remaining scope limit |
| --- | ---: | --- | --- |
| Hacienda de la Topera Oculta | 3 | Collapsed to the entry arena | Local family quantities; official encounter composition is not claimed. |
| Kokolost Island | 4 | Collapsed to the entry arena | Optional council, voting and treasure/archmonster branches are not required main encounters. No archmonster is spawned. |
| Cono de Crújian Jerry | 3 | Collapsed to the entry arena | Item-gated optional secret and its return are explicitly disabled. |
| Necrópelis de Morbax | 4 | Collapsed to the entry arena | An alternate foreign-map exterior exit is excluded from this entry-return route. |
| Hacienda de la Balinería | 3 | Mixed physical/transport room bindings unsupported | Local family quantities; official encounter composition is not claimed. |
| Montaña Conohos | 4 | Mixed bindings and alternate exits conflated | Exterior entrance route only; the alternate mine route and post-boss achievement traversal remain separate work. |
| Escarantera Abandonada | 3 | Mixed physical/transport room bindings unsupported | A native source in an unreachable one-way component is explicitly excluded. |

All selected encounters exclude native dominants, archmonsters and unresolved roles, increase deterministic native-level composition strength, and keep the selected family boss in the final encounter. Conohos uses one explicitly documented additional ordinary actor in the final local roster to preserve increasing composition strength.

An excluded source requires its exact native ID, a reason and the canonical native source hash. Exclusions cannot overlap reviewed progression bindings or the main exit. They are visible limitations, not evidence that every secret or alternate route is implemented.

## Guide context resolves misleading room counts

- [Kokolost guide](https://methodwakfu.com/pvm/donjons/kokokolantha/): three ordinary encounters and the boss form the four-room main route. A separately listed archmonster encounter belongs to a council-vote side branch, mutually exclusive with a treasure branch. It must not be inserted as a mandatory fifth fight. The user explicitly permits authentic documented optional archmonsters; resolving and implementing that side encounter remains separate work. The no-archmonster restriction applies to generated family groups.
- [Conohos guide](https://methodwakfu.com/pvm/la-montagne-adezieu/): the exterior entrance has three preliminary encounters, the mine entrance has two, and both reach the same boss. The unused branch opens after victory for an achievement. The six guide encounter entries are not a single six-fight linear main route.

These are reviewed historical guide descriptions, not certification of matching contemporary boss scripts.

Kokolost optional actor and location evidence is now resolved separately: native actors 1751 and 1753, one each, plus two Grokoko 4728; map 295, optional arena `(-36, -91, 0)`, access gate 13348. [Identity and location evidence](KOKOLOST-NATIVE-OPTIONAL-ACTOR-EVIDENCE-20261010.md). The guide classifies this encounter as an archmonster encounter even though the installed actor records do not carry property 45. Exact identity, family and location prevent selecting same-name copies. It is not spawned yet: optional encounter settlement must be separated from main progression and final rewards; council selection also remains unimplemented.

## Retroactive structural audit

The [independent audit](ALL-CLASSIC-HYBRID-STRUCTURE-AUDIT-20261010.json) covers all 109 classic level-specific definitions, representing 107 distinct names. It separates current database configurations from latest source candidates, and separates the 37 validated native ordinary flows from older active anchor configurations. The ten ultimate-boss arenas are outside this ordinary-dungeon structural denominator.

Checks include omitted native separator gates and transports, directed arrival-to-encounter paths, future-stage paths, large omitted terrain components, and explicit native room-count metadata. Archived guide count mismatches are review signals, not automatic proof of broken gameplay. The native `DUNGEON_3_PLAYERS` type describes team size and must not be interpreted as three rooms.

The initial retroactive pass found no blocked native route among the previously validated 37. Tofullero's manual acceptance is retained. Other older anchor configurations are reported separately; their presence in the database does not mean they passed native progression acceptance. That pass identified six structural follow-ups. Wagnar (three encounters) and Ratacumbas (two encounters) now have complete source-only V8 replacements with explicit native bindings and fresh six-player PostgreSQL lifecycle gates. [V8 evidence](HYBRID-NATIVE-FULL-ROOM-PG-LIFECYCLE-V8-20261010.json). Four remain explicitly unresolved: Vid Vil needs a revisited hub and victory-gated nonadjacent-stage travel; Palacio Zollo needs a native cycle and completed-run return to its entry exit; Base del Susurro has four-encounter metadata but only three proven large sequential arenas; Arena Danzante has three-encounter metadata but one connected arena, requiring script or wave evidence. [Exact structural blockers](HYBRID-NATIVE-RETROSPECTIVE-V8-20261010.md).

## General graphical acceptance after deployment verification

Use one complete run per selected route, with a real party and heroes where available. Reach the exterior using the command below, then enter through the native entrance. Interior coordinate teleportation is not a substitute for testing connections.

| Dungeon | Exterior command | Expected encounters |
| --- | --- | ---: |
| Topera Oculta | `!teleport 1120 -185 4 0` | 3 |
| Kokolost | `!teleport 1135 45 80 -60` | 4 |
| Jerry | `!teleport 504 -26 -74 0` | 3 |
| Morbax | `!teleport 1137 20 -173 0` | 4 |
| Balinería | `!teleport 1136 20 147 -80` | 3 |
| Conohos, exterior entrance | `!teleport 1134 -50 -104 50` | 4 |
| Escarantera | `!teleport 1137 128 -135 -74` | 3 |

1. Enter as a group. Confirm all intended participants share the instance and the first enemies are reachable from the actual arrival.
2. Before each victory, try the next encounter access: it must remain closed. Native transit within the current stage must work and must not advance progression or deliver rewards.
3. Complete each fight normally, checking initiative, turns and termination. A traversal-only repeat can use `!winfight` in an active fight; that repeat does not certify combat or boss mechanics.
4. After each victory, confirm the correct door visibly opens or the forward transport becomes usable. Reach every next encounter by native movement and interactions. Confirm generated family groups contain no dominant or archmonster and the main family boss appears only in the final encounter. An explicitly reviewed native optional archmonster encounter is allowed and must remain optional.
5. Finish the boss and use the reviewed native exit. Confirm all intended participants return outside, then re-enter and confirm a fresh first room with closed gates.
6. On another run, use `!losefight` during a fight. Confirm no next-room unlock, then `!exitdungeon` and re-enter successfully. Reconnect once between encounters to confirm retained progress and no duplicated enemies or rewards.

Record the first failed numbered step, dungeon, character, `!position` output and whether the other account observes the same problem. Optional branches explicitly excluded above are not main-route acceptance requirements.
