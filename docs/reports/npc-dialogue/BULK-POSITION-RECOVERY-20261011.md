# Bulk original NPC position recovery

Hector prioritizes spawning all recoverable original NPCs before extending their
conversations. Position authority and dialogue authority are now independent.
Migration144 and `maps/npc_placements.py` implement one general public-scene
publisher. Original coordinates, native breed, native Spanish name, appearance,
level, direction, source checksum and frame are retained. No guessed dialogue
root is needed. Every original native collection action is disabled in the
format11 `sR` action set; these actors are not registered as combat groups.

## Entire captured source inventory

| Source scope | Raw records | Result |
| --- | ---: | --- |
| Original creation capture | 454 | All actor records crossed against native breed/action definitions |
| Original dungeon capture | 227 | All actor records crossed, including ordinary non-dialogue Amakna guard |
| Independent original reference capture | 3 | Duplicate identities retained as corroborating evidence |
| Total | 684 | 33 native breeds; 10 accredited NPC identities |
| Non-NPC actors | 670 | Monsters, bombs, training objects and other actors are not duplicated as noncombat NPCs |
| Repeated NPC identities | 4 | Reference duplicates and later Grugal movement do not create extra NPCs |
| Selected original NPC positions | 10 | All imported, with existing dialogue registry taking precedence |
| Existing prepared dialogue actors | 5 | Dynamic SQL exclusion prevents duplicate publication |
| Additional position-only actors | 5 | Guard, Wuan Tazo, Magnum Deskhalzo, B. Toven and Mod'Ulo |

The native catalog was read in a bounded128MiB original Java export for all33
captured breeds, including breeds with no START_DIALOG action. It is not a
species-only dialogue scan. Private complete ledger:
`.runtime/local/npc-position-bulk/ledger.json`; native metadata:
`.runtime/local/npc-position-bulk/breeds.json`.

| Native identity | Map | Original XYZ | Publication |
| --- | ---: | --- | --- |
| Otomai5459 | 1385 | 20,17,1 | Existing qualified dialogue actor |
| Kheperalia5467 | 1385 | 12,32,1 | Existing qualified dialogue actor |
| Huly5461 | 1385 | -17,-4,17 | Existing qualified dialogue actor |
| Airyna5460 | 1388 | 0,-19,3 | Existing qualified dialogue actor |
| Grugaloragran5458 | 1387 | -12,0,2 | First original spawn; later movement is not another NPC |
| Amakna guard4590 | 1134 | 11,-13,0 | Position-only, no conversation action |
| Wuan Tazo4800 | 1134 | -17,9,-1 | Position-only; action1002 disabled |
| Magnum Deskhalzo3819 | 1134 | 16,8,0 | Position-only; action703 disabled |
| B. Toven4069 | 527 | -219,-46,5 | Position-only; action798 disabled |
| Mod'Ulo4399 | 9 | 0,-5,4 | Position-only; action884 disabled |

Original captured visibility does not establish a permanent story predicate.
This is an explicitly authorized local public-instance scene adaptation.
Existing dialogue registry rows, including disabled/quarantined rows, always
win over position-only rows. The previous four incorrect trial placements are
not reenabled. Captured names/appearance are preserved rather than replacing
actors with arbitrary decorative graphics.

## Full native asset frontier and limits

| Source | Entire inventory | Accredited physical NPC placement contribution |
| --- | ---: | --- |
| Protector definitions | 105 definitions;101 exact placements across57maps;4 lack territory/map join | Original location and protector appearance are known; appearance IDs are not breed IDs |
| Original protector-to-actor publication | 13 unique exact joins | Only424/Otomai and303/B.Toven have actual captured actor envelopes; both included above |
| Environment actor records | 914 across961map archives | Decorative actors lack native breed authority and already belong to client environment rendering |
| Lua Actor.createActor literals | 1143 XYZ across196scripts | Map and native identity must be proved; cinematic graphics are not breed authority |
| Native quest compass candidates | 196 records | Objective coordinates/localized subject names are not certified physical NPC spawn contracts |

The independent Lua join audit crosses all1143XYZ records, resolving1134literal
visuals.533match at least one conversational appearance;145have a unique
current-catalog visual match, covering52breed candidates. Four exact objective
XYZ/appearance joins and three same-event proposals remain explicitly
unaccredited because no original creation map/breed field proves them. These
are retained as source leads, not silently substituted for missing NPCs.
Ledger: `.runtime/local/npc-lua-bulk-source-20261011/ledger.json`.

Known remaining problem is source authority, not a dialogue-root requirement:
additional NPCs can now be imported immediately when their original map,
coordinates and native identity are proved. The101protector locations still
need a physical actor/breed contract for the99not already joined to captured
actors. No name-based or appearance-based guessed actor is manufactured.

## Verification and deployment

Luna verification passed5/5 focused pure tests and1/1 isolated PostgreSQL test against a fresh1..144 migration snapshot. The test loaded all10 exact source tuples, selected exactly5 additions after the five dialogue actors, preserved disabled-dialogue precedence, denied private instances and repeated migration application with0new migrations. Temporary SQL schema counts returned8→8. Actual dispatcher AST scene/replay integration passed. The original Java ctE/eHj/sR consumers decoded all10 format11 packets and verified every action mask, including B.Toven798 and Mod'Ulo884. Source hashes remained unchanged. Receipts: `.runtime/local/npc-placements-validation/` and `.runtime/local/npc-position-tests/`.
Dispatcher integration and complete image publication are owned by the parent
Systems agent. This report describes prepared source, not a deployment claim.

## Complete position-first manual acceptance

Run only after migration144 and the complete current World image are confirmed.
Before testing dialogue, visit every qualified approach below. Each command is
an actual cell from the existing original native geometry artifact, not the NPC
cell. Geometry hashes/source paths are preserved in
`.runtime/local/npc-position-bulk/manual-approaches.json`; no geometry rebuild
was performed. Original NPC cells may be non-walkable and are not automatically
valid teleport destinations.

| NPC | Qualified approach command | Expected original actor location |
| --- | --- | --- |
| Otomai | `!tp 1385 19 17 1` | Map1385 (20,17,1) |
| Kheperalia | `!tp 1385 11 32 1` | Map1385 (12,32,1) |
| Huly | `!tp 1385 -18 -4 17` | Map1385 (-17,-4,17) |
| Airyna | `!tp 1388 -1 -19 3` | Map1388 (0,-19,3) |
| Grugaloragrán | `!tp 1387 -13 0 2` | Map1387 (-12,0,2) |
| Guarda de Amakna | `!tp 1134 10 -13 -1` | Map1134 (11,-13,0) |
| Wuan Tazo | **NOT RUN: no qualified nearby approach** | Map1134 (-17,9,-1) |
| Magnum Deskhalzo | `!tp 1134 16 7 0` | Map1134 (16,8,0) |
| B. Tóven | `!tp 527 -219 -45 5` | Map527 (-219,-46,5) |
| Mod'Ulo | `!tp 9 0 -6 4` | Map9 (0,-5,4) |

For each available approach: confirm one actor at the listed original location,
its native name and appearance, and no duplicate on reconnect/map return. The
five position-only additions must offer no enabled unimplemented collection or
dialogue action and must not start combat. Existing five qualified dialogue
actors retain their own actions, but conversation is tested only after the
position journey passes. Wuan Tazo remains NOT RUN for direct teleport approach:
its captured position is certified, but this bounded native geometry search
found no nearby cell within four XY steps and one altitude step; do not invent
a teleport coordinate. Ordinary map navigation may reveal it, without claiming
the approach was geometrically qualified.

The all-snapshot position-only comparison also checked all nine unique original
capture files, deduplicated by SHA256. It found **zero actor positions absent
from the three source inventories** and zero additional NPC positions. Proof:
`.runtime/local/npc-position-bulk/all-capture-position-coverage.json`.
