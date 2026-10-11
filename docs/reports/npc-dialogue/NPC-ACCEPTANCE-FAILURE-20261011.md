# Conversational NPC acceptance failure audit

The user reported visible NPCs with no conversation and misplaced NPCs. Acceptance remains failed; no bulk activation is justified by this audit.

## Published actors and provenance

The live `world_dialogue_npcs` table contains exactly the four local trial actors from migration121, all map1134 instance0. Their native breed, portrait and localized dialogue speaker agree, but neither their coordinates nor chosen initial roots are canonical:

| Name | Breed | Position | Chosen root | Relevant dialogue content |
| --- | --- | --- | --- | --- |
| Arh Kayuh | 2986 | -10,-8,-1 | 6274 | Child groans guiltily |
| Laura Craft | 3814 | -12,-10,-1 | 6554 | References prior Imagori encounter and pipe investigation |
| Tristepin | 4687 | -14,-8,-1 | 7122 | Offers combat training |
| Kabrok | 3580 | -12,-6,-1 | 7279 | Shouts “What?” from across the room |

The map1134 replay additionally publishes three original captured type1 actors from frame78 of `.runtime/captures/2026-10-03T03-40-46.413625Z-fe2520f4/decoded/frames.jsonl`. `wire.without_captured_players()` preserves these non-player actors:

| Name | Breed | Actor ID | Native captured position | Dialogue action |
| --- | --- | --- | --- | --- |
| Guarda de Amakna | 4590 | -1724034232352690 | 11,-13,0 | None in conversational catalog |
| Wuan Tazo | 4800 | -1724034232352729 | -17,9,-1 | 1002, unconditional |
| Magnum Deskhalzo | 3819 | -1724034232352753 | 16,8,0 | 703, unconditional |

The latter two have native START_DIALOG actions, but the current13222 handler only resolves `world_dialogue_npcs`; their identities are absent from that registry. A click therefore cannot start a server conversation through the current path. Native `bly.jW(long)` serializes the action into `cnT` and sends it to the server; evidence `.runtime/local/npc-click-native-flow.txt`.

## Initial dialogue remains unresolved for captured actors

The complete extracted node catalog contains no `npc4800` or `npc3819` portrait roots and no localized159 speaker named Wuan Tazo or Magnum Deskhalzo. Their installed `interactiveDialogs/npc4800.lua` and `npc3819.lua` only call `Sound.playRandomSound`; they contain no textual dialogue or tree. Native START_DIALOG is consequently insufficient evidence for assigning an arbitrary text root. No captured12969/12218 conversation response exists in the replay to recover an initial root.

The original captures now provide three accredited actor positions, improving on quest-marker inference, but only zero accredited initial textual roots for the two conversational-action actors. Importing them as text conversations requires additional original data or an explicit local dialogue policy. Hiding actors does not restore their functionality, and choosing another NPC's root would be false attribution.

Other12608 publication sources include authoritative combat population groups/corpses, players/heroes and scene replay. Combat population actors must retain existing combat behavior and must not be broadly reclassified as conversational NPCs. Decorative map `aci` providers remain a separate client scenery path, not a registry of textual conversations.

No database, dispatcher, client asset or service was changed by this investigation.

## Safe correction and audiovisual protocol follow-up

Migration126 (`126_quarantine_local_trial_npcs.sql`) disables only the four trial IDs when their recorded provenance still identifies the original local seed. It preserves rows for review, custom replacements, and all three captured native actors. The migration is prepared, not applied by this audit.

Native audiovisual tracing found `bYR.oX(script)` called from `dcj.feO()`, the interactive dialogue view. The script key comes from `bpb.dCU()`: a node-specific `eUB.fLf()` override when present, otherwise the native speaker key. Thus sound scripts are attached to an opened native dialogue view; their presence alone does not identify its textual root. No standalone audiovisual reply opcode has been established. Sending12969 with an absent root (0 or -1) is unsafe: `eUD.Sq(id)` returns null and `bpb.a(eUB)` immediately dereferences `eUB.d()` while loading text. The handler must not fabricate a root or send such a sentinel.

Disassemblies: `.runtime/local/npc-audio-runner.txt`, `npc-audio-consumers.txt`, `npc-node-view.txt`, `npc-node-manager.txt`, `npc-root-data.txt`. No audiovisual server handler was added without a verified wire contract.

## Reproducible original spawn export and complete action schema

`sniffer/export_captured_native_npcs.py` now recovers native12608 type1/format11 actor breed, actor identity, exact map/XYZ and direction. It checks envelope/body identities and joins observed12969 opens by actor ID without interpreting portrait matches as initial roots. On the original installed replay it exports three actor positions and zero observed dialogue opens, with capture SHA-256 provenance in `.runtime/local/original-native-npc-spawns.json`.

`sniffer/java/ExportNpcActionContracts.java` exports every installed conversational `aMg` field for all505 actions. Every action has `cbH=0` and duration0; therefore an omitted nonzero `cbH` field does not supply initial roots. `clx` varies (433 actions use67), and is preserved without inventing root semantics. Related native binary table availability is recorded:42 MONSTER is installed;43 MONSTER_BLAHBLAH,44 MONSTER_FIGHT_BUBBLE,45/46 MONSTER_GROUP_TEMPLATE(_TABLE),62 SCENARIO and63 SCENARIO_CHALLENGE are absent. This is a concrete distribution boundary rather than a decoding failure.

Reproduce:

```sh
python3 sniffer/export_captured_native_npcs.py .runtime/captures/2026-10-03T03-40-46.413625Z-fe2520f4/decoded/frames.jsonl .runtime/local/original-native-npc-spawns.json
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ExportNpcActionContracts.java
java -cp '.runtime/local/classes:client/lib/*' ExportNpcActionContracts .runtime/local/native-npc-action-contracts.json
```
