# Complete installed map POI schema audit

The exact loader is resolved through `client/config.properties:137`:
`mapsPoiPath=jar:file:./contents/maps/data.jar!/poi/%d/map.poi`.
Native `bLa.nj(long)` formats this configured path with the requested world ID,
loads the bytes and calls `aIm.b(aoG,false)`. Searching JAR constants for literal
`map.poi` misses this configuration indirection and produces unrelated ranch
translation keys.

`sniffer/java/ExportNativeMapPoi.java` invokes this same native decoder separately
for every installed POI entry. **All720 files decode successfully, with zero
failures:1,887 landmarks and2,597 interactive-element records.** Full field values,
visibility criteria and serialized interactive payload bytes are preserved in
`.runtime/local/native-map-poi.json`.

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ExportNativeMapPoi.java
java -cp '.runtime/local/classes:client/lib/*' ExportNativeMapPoi .runtime/local/native-map-poi.json
```

The native `aIm` extends `act`: the initial section contains `acr` landmarks,
followed by `acq` interactive definitions. A landmark has ID, XYZ, direction,
additional visibility metadata, type and target ID, with one or more `acs`
variants containing localized-label ID, icon ID and criterion text. `aIm.cif`
parses these criteria using the native criterion parser. Landmarks are map UI
objects and do not directly publish world actors.

Native `bVb` establishes the type semantics. `bLa.b(acr)` dispatches them:

| Native type | Count | Target contract |
| --- | ---: | --- |
| STATIC0 | 728 | Map label/icon; no actor breed join |
| IE1 | 856 | `chj` selects `acq.aHm`; native `bEC` creates an interactive element from its type and payload |
| DUNGEONS2 | 199 | `chj` resolves `eQN.QO` dungeon definition |
| PROTECTORS3 | 104 | `chj` resolves `bLU` protector definition |

Labels resolve native localization category35 with `acs.p`; that number is a
label ID, not an NPC breed. The static marker `chj` is not a native NPC registry
lookup. No generic NPC type exists in the four-entry POI enum.

The2,597 interactive payloads cover12 native `bEE` types:

| Type | Count |
| --- | ---: |
| GenericActivableInteractiveElement | 1878 |
| CraftTable | 330 |
| Drago | 120 |
| Boat | 87 |
| BattlegroundEntrance | 85 |
| Zaap | 45 |
| InfiniteWaves | 16 |
| RespawnPoint | 13 |
| EnchantmentMachine | 7 |
| PvpExtraction | 6 |
| PvpChangeState | 5 |
| HavenWorldEntrance | 5 |

None of their `acq.cha` integer arrays references requested NPC action IDs1002,
703,1243 or1390. That negative scan is limited to this decoded field; arbitrary
payload byte coincidences would not prove a dialogue reference. Generic
activatable elements use native factory `bBJ` producing `bBH`, a `bEG`
interactive element, rather than an `aMb` monster/NPC actor.

This branch recovers authoritative map marker/interactive coordinates and
visibility rules. It qualifies **zero additional original NPC breed + world
spawn + initial-dialogue joins**. In particular, labels or icons must not be
converted to conversational breeds through name inference. Full payload records
remain available for future proven interactive or scenario joins.

Private native consumer disassemblies: `npc-poi-bLa.txt`, `npc-poi-aIm.txt`,
`npc-poi-act.txt`, `npc-poi-interactive-types.txt` and
`npc-poi-generic-activatable.txt` under `.runtime/local/`.
No client assets, server sources, services or databases were modified.
