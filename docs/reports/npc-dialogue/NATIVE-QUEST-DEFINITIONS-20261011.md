# Native quest and achievement definition extraction

## Result

The installed client contains substantial native mission metadata beyond the
previously extracted dialogue/scenario scripts. The new read-only exporter
`sniffer/java/ExportNativeQuestDefinitions.java` preserves every public native
record field without assigning speculative gameplay semantics. It runs through
the installed offline `apw` binary loader and executes no mission or reward.

| Native content | Extracted count |
| --- | --- |
| Quest/achievement definitions (`aJM`, table1) | 3,278 unique IDs |
| Objectives (`aJN`) | 6,029 unique IDs |
| Typed reward records (`aJP`) | 5,593 |
| Objective map markers (`aJO`) | 1,682 |
| Objectives with markers | 1,509 |
| Distinct marker maps | 130 |
| Categories (`aJR`, table3) | 481 |
| Variables (`aJU`, table2) | 396 |
| Objective variable dependency records (`aJQ`) | 297 |
| Ordered list records (`aJS`, table115) | 0 |
| Definitions with nonempty `aHe` criterion | 2,858 |
| Definitions with nonempty `cjI` criterion | 1,148 |
| Literal achievement/objective references indexed in definition/objective criteria | 3,489 |
| Additional literal item quantity references | 2 |

These are a combined quest/achievement definition system, **not 3,278 certified
playable quests**. The exporter retains native flags/category/type values so a
later classifier can identify specific quest families using verified consumers.
An empty ordered-list table is recorded explicitly; no synthetic lists are added.

Localized categories62/63/64/65 are preserved in all four installed languages:
12,938 entries each in English, Spanish and French, and 12,939 in Portuguese.
Native display evidence confirms62 as definition title,63 as description and64
as objective text; category65 is preserved without overstating its semantics.

## Native contracts established

`aZy` loads `aJM.aHe` and the criterion derived from `cjI` through `eQe.tz`.
`aZx` can augment `cjI` with level/item/achievement rules depending on native
flags; the raw expression alone is not guaranteed to be the complete final rule.

`aZy.a(aJM,int)` loads every `aJN` objective, passes native flags, the parsed
`ckc/cke` criteria, the native `aJO[]` marker collection and flattened `aJQ.ckn`
variable IDs into `bdK`. `bdK` resolves these IDs as native `bdV` variables;
therefore dependency arrays must not be mislabeled as objective transition edges.

`aZy.b(aJM,int)` resolves `aJP.aeV` through `bdH.AT` and registers raw reward
parameter arrays and native flags. Reward enum names are accredited. Actual
parameter execution, eligibility, idempotence and transactional claims are not
implemented by this export.

The installed `bev` marker consumer calls:

```text
bLc.a(7, aJO.ckg, aJO.ckh, aJO.cki, aJO.ckj, ..., localized objective64, true)
```

This proves `ckg/ckh/cki` are markerXYZ and `ckj` is the associated map ID.
These are quest compass targets. A target can be an area, entrance or interaction
approach cell; it is not automatically the exact permanent actor spawn cell.

## Talk-to-NPC objective identity audit

The full native `aJN.a(apC)` decoder confirms that its record contains only:
objectiveID, one boolean, two criterion strings, `aJO[]` map markers and `aJQ[]`
variable dependency records. There is **no objective event/type field, NPC breed
reference, dialogue action ID or server event parameter array** in this schema.
The export includes every public zero-argument native getter; no such field was
omitted by the exporter.

All 6,029 objective criteria were scanned: none contains NPC, monster, breed or
dialogue predicates. `aJO` contains exactly markerXYZ and map. `aJQ.ckn` joins
native achievement variables through the audited `bdK` consumer, not monster
references; all 432 referenced variable IDs resolve to the exported variable table.
The variable names describe counters such as `nbGuildMonsterKilled`.
The binary schema disassembly is preserved at
`.runtime/npc-quest-objective-binary-schema.txt`.

Therefore an objective's localized “Talk to <name>” text and its marker cannot be
promoted into an accredited objective→aMb breed association. Literal dialogue
quest/objective predicates remain valid conditional references, but do not
supply NPC initial roots or exact spawn points. No derived NPC placements were
created from names or matching integers.

## Reward rows by accredited native type

| Reward type | Rows |
| --- | --- |
| GIVE_PLAYER_ITEM | 2,796 |
| GIVE_PLAYER_XP | 1,405 |
| GIVE_PLAYER_XP_PER_MOB_XP | 574 |
| GIVE_KAMAS | 380 |
| GIVE_PLAYER_TITLE | 349 |
| REGISTER_ZAAP | 38 |
| REGISTER_DRAGO | 22 |
| GIVE_PLAYER_EMOTE | 14 |
| GIVE_PLAYER_LANDMARK | 6 |
| GIVE_PLAYER_SPELL | 4 |
| GIVE_GUILD_POINTS | 3 |
| LEARN_RECIPE | 2 |

All 19 native `bdH` reward type definitions are also preserved, including types
with no observed reward rows.

## Accredited dialogue/quest anchors

The existing dialogue criteria can be joined to these tables without guessing
story transitions. The private link index contains 4,303 literal achievement or
objective references from 890 dialogue nodes: 4,253 resolve to extracted native
IDs, while 50 remain unresolved and are explicitly marked. Predicate breakdown:
1,629 `IsAchievementRunning`, 587 `IsAchievementComplete`, and 2,087
`IsAchievementObjectiveComplete` references. These are conditional dependencies,
not automatic dialogue edges or completion handlers.

A concrete consistent chain is native quest4996, **El final del viaje**:

- Objective10289: “Hablar con Kanz Herbero en la encrucijada de las almas caídas”,
  native marker map1342, coordinate(-6,12,-5).
- Objective10350 asks to return to the same speaker and has the same marker.
- Extracted dialogue6275/choice14076 references quest4996 and objectives10347,
  10348,10349 and10350 in its criterion.

This supplies an accredited quest/dialogue condition and a named quest target
location. It does not prove which exact NPC actor occupies that target, its
permanent appearance rules, the initial root selection or server reward triggers.
The native-world placement audit's zero certified permanent NPC placements
therefore remains accurate; this new marker evidence is a stronger starting
point for future location verification, not guessed placement data.

## Artifacts and reproduction

Generated private artifacts:

- `.runtime/local/native-quest-definitions.json`: complete 6.5 MB native export,
  multilingual text and SHA-256 provenance for the client, exporter and source
  binary/language archives.
- `.runtime/local/native-quest-definition-index.json`: normalized marker records,
  literal criterion-reference index and exact counts. Expressions are retained.
- `.runtime/local/native-dialogue-quest-criteria-links.json`: complete dialogue
  condition joins with explicit native-ID resolution status.
- `.runtime/npc-quest-loaders.txt`, `.runtime/npc-quest-manager.txt`,
  `.runtime/npc-quest-marker-display.txt`: installed consumer disassembly.

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ExportNativeQuestDefinitions.java
java -cp '.runtime/local/classes:client/lib/*' ExportNativeQuestDefinitions .runtime/local/native-quest-definitions.json
```

The exporter ran successfully and all 3,278 definition IDs and 6,029 objective IDs
are unique. Source hashes are included in the generated document. No server or
client file was changed, no game service was contacted, and no deployment or
restart was performed.

## Remaining work

Native metadata can now support a general quest catalog, prerequisite inspector,
objective-marker browser and NPC/dialogue condition mapping. A future import
should preserve unresolved references and raw values rather than silently
coercing them. Implementing playable missions additionally requires verified
server event/objective handlers, state transitions, repeat/reset policies,
visibility and prerequisite evaluation, persistent progress and transactional
reward claims. Full dialogue decision trees remain a separate subsequent task,
as requested. Do not infer edges from sorted IDs, objective order or shared
coordinates.
