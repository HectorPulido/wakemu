# Conversational NPC native-world placement audit

This read-only/offline audit extends the initial local NPC cluster. The four
local seeds are not coverage of the original game's NPC population. Server
sources remained stable throughout this audit; no build, deployment or restart
was performed.

## Counts

| Evidence | Result | What it establishes |
| --- | --- | --- |
| Native aMb START_DIALOG catalog | 422 breeds, 505 actions | Native appearance/reference/action availability |
| Installed interactiveDialogs Lua | 385 scripts | NPC audio callbacks, not world placements |
| Installed map environment archives | 961 maps | Archives scanned |
| Environment chunks | 31,148 decoded; 90 unsupported | Explicit limit of this decoder |
| Native aci environment actors | 914 coordinate records | Decorative actor positions |
| Environment graphics matches | 80 records, 22 candidate conversational breeds | Shared graphics only; not NPC identity |
| Literal Actor.createActor calls across all installed Lua | 325 calls | Client-created visual positions |
| Lua graphics matches | 146 calls, 78 candidate conversational breeds | Shared graphics only; no accredited map association |
| Accredited permanent conversational NPC placements recovered | **0** | No guessed coordinates or identity mappings promoted |

The zero refers to permanent conversational NPC identity/map/root contracts
recovered by this audit. It does not claim no such information could exist in
an unexplored server source or unsupported chunk format.

## Why visual actor positions are insufficient

`aci` contains a native decorative actor ID, graphics ID (`cgI`), provider type,
chunk-local XY, altitude, animation script and parameters. The actual consumer
`aeA.a(ach,aci)` resolves XY with `ach.rL/rM`, requests a provider through
`aeD.sd(bFV)` and formats a graphics-file path from `cgI`. It does not load a
native monster breed, START_DIALOG action or dialogue root.

There are 897 type 1 decorative actors, 16 type 4 actors and 1 type 3 actor. Only one
record has nonempty parameters. Graphics are shared: graphics150 matches both
conversational breeds4551 and4695. Even a unique current catalog graphics match
does not prove a decorative actor was intended as that interactive NPC.

Literal Lua calls include cinematic clones created under generated/local actor
IDs. Their XYZ do not carry a world map ID. For example, scenario1971 creates a
`kabrok` visual actor with graphics101101151 at(-1,0,0); the call alone does not
establish a permanent NPC placement or its dialogue root.

`maps/data.jar` contains points-of-interest records, not another NPC spawn
archive. Audited native `bLa` consumers distinguish `bVb` STATIC, IE, DUNGEONS
and PROTECTORS. Its `acr.chj` joins interactive elements, dungeon references or
protector references according to that type; treating it as a monster breed ID
would be a false mapping.

## Reproducible artifacts

- `sniffer/java/AuditNpcNativePlacements.java` scans all installed environment
  chunks with the native `ach/aci` decoder and preserves actual world coordinates.
- `.runtime/local/native-npc-placement-audit.json`: complete 914 environment actors
  and decoder counts.
- `.runtime/local/native-npc-placement-summary.json`: graphics candidate joins;
  deliberately not imported into runtime placement tables.
- `.runtime/local/native-npc-script-literal-positions.json`: 325 static-position
  call sites with file/line and explicit `map_id:null`.
- `.runtime/npc-aci-consumers.txt`, `.runtime/npc-poi-loader.txt` and
  `.runtime/npc-poi-model.txt`: installed native consumer disassembly.

Run the Java audit from the repository root:

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/AuditNpcNativePlacements.java
java -cp '.runtime/local/classes:client/lib/*' AuditNpcNativePlacements .runtime/local/native-npc-placement-audit.json
```

## General population strategy

The SQL registry/runtime already supports every verified native speaker without
per-map handlers. Extend population from a provenance ledger with explicit
`breed,map,instance_policy,x,y,z,direction,root,action_ids,source` records.
Candidate imports must retain evidence and validation status separately from
enabled placements.

Verified official world snapshots (`ctE12608/eHj`) can supply breed, actor name,
coordinates and map. A matched native action13222 followed by dialogue12969
supplies the actual initial root and speaker identity. Record world-scene scope
and quest/story predicates alongside the observation; repeated captures of one
NPC can legitimately yield different roots or conditional visibility. Do not
collapse those into one unconditional spawn.

A future importer should reject duplicate identity/position, unknown breeds,
non-dialogue actions, mismatched portraits, unavailable roots and geometry
failures. Validated records can bulk-populate `world_dialogue_npcs`; uncertain
records stay in the evidence ledger. Full decision edges and quest grants remain
a later task as requested. If an authoritative original spawn database becomes
available, adapt it into the same ledger/registry rather than hand-editing each
map or inventing missing coordinates.

The current four local initial conversations are therefore a usable starting
cluster, while complete original-world NPC placement remains explicitly open.
