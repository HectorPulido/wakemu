# Original capture NPC and initial-dialogue recovery

## New source and results

The original, non-Wakemu creation-session capture contains substantially more evidence than the previously inspected reference-session snapshot:

`.runtime/official-creation/captures/2026-10-03T06-56-20.133993Z-13a6e59e/snapshot-final/decoded/frames.jsonl`

The generic capture exporter recovers **454 distinct native actor-position records, 22 breeds, and 15 original dialogue-open responses**. Most actors are wildlife. Native conversational catalog membership narrows this to **six positions belonging to five conversational breeds**:

| Native speaker | Breed | Map | Captured XYZ | Evidence |
| --- | --- | --- | --- | --- |
| Otomai | 5459 | 1385 | (20,17,1) | Spawn frame1077; no captured dialogue response |
| Kheperalia | 5467 | 1385 | (12,32,1) | Spawn1077; action1255 returns5782, later5762 |
| Huly | 5461 | 1385 | (-17,-4,17) | Spawn1154; action1243 returns5765 |
| Airyna | 5460 | 1388 | (0,-19,3) | Spawn3785; action1390 returns5755, action1389 returns5787 |
| Grugaloragrán | 5458 | 1387 | (-12,0,2) | Spawn9303; action1238 returns5764 |
| Grugaloragrán, subsequent movement | 5458 | 1387 | (-16,0,0) | Spawn9342 after conversation choices; not its initial interaction position |

These are original actor spawns, unlike the earlier quest compass markers. Map scope is directly from each native actor POSITION section. The capture alone does not prove their unconditional visibility for all story states or all character instances.

## Exact initial interaction contract

Original frame9314 is outgoing13222, body `>qq`, actor `-1706442035962340`, action1238. Original frame9317 is incoming12969, body `>ibq`, node5764, speaker-type2, same actor. The preceding actor spawn at9303 gives breed5458 and map1387 XYZ(-12,0,2), direction1. Both native breed action1238 and node5764 have empty criteria.

This accredits an initial conversation in that captured context without choosing a root by portrait or name. Later frame9342 moves the same actor to(-16,0,0); assigning the earlier conversation to that future position would be wrong. Root5764 contains a level-dependent choice13343 and unconditional exit13344. Initial-only runtime must not invent quest rewards, progression, or a transition for13343.

The current world registry's negative-ID range excludes this genuine captured ID. Any activation must admit the exact captured identity with database constraints and duplicate checks; changing the original actor ID would invalidate the captured interaction binding.

## Why other observed starts remain conditional

- Huly action1243 requires map1385 and objective10595 incomplete; action1241 represents the other objective branch.
- Airyna action1390 requires objective10606 incomplete; action1389 requires it complete.
- Kheperalia action1255 is unconditional, but observed roots differ. Root5782 requires objective10607 incomplete; root5762 requires objective10607 complete and a native monster-population range. A generic first-root guess would erase real progression.
- One response uses speaker-type1, reference424, rather than the clicked actor. The exporter retains this event and the qualifier withholds an actor-speaker binding.

The qualifier therefore accepts **one observed unconditional action/root contract and withholds14 responses**. Its output explicitly sets `unconditional_world_activation=false`; captured contextual placement is not universal visibility authorization.

## General tools and regression controls

`sniffer/export_captured_native_npcs.py` now records outgoing13222 requests, the actor position existing at request time, and the following12969 response. It preserves first-seen spawn frame indices and attaches dialogue responses only to the corresponding preceding actor position. This corrects the previous exporter, which joined roots to every position of the same actor and could incorrectly attribute earlier roots to future movement.

`sniffer/qualify_captured_npc_dialogues.py` joins the recovered interaction to native speaker actions and native nodes, withholding nonmatching speaker types, missing actors/actions/nodes, conditional actions/nodes, mismatched portraits and multiple observed roots for the same action.

```sh
python3 sniffer/export_captured_native_npcs.py .runtime/official-creation/captures/2026-10-03T06-56-20.133993Z-13a6e59e/snapshot-final/decoded/frames.jsonl .runtime/local/original-native-npc-spawns-expanded.json
python3 sniffer/qualify_captured_npc_dialogues.py .runtime/local/original-native-npc-spawns-expanded.json server/protocol/npc-dialogues.json.gz .runtime/local/original-native-npc-dialogues-qualified.json
PYTHONPATH=server python3 -m unittest discover -s server/tests -p 'test_captured_npc_dialogues.py'
```

Regression controls cover temporal movement joins, observed-context qualification, conditional action/node denial, speaker mismatch, and ambiguous observed roots. Luna qualification requested. This extraction does not modify the client, services, or runtime database.

## Prepared server adaptation, not yet deployed

Root authorized the exact observed map1387 initial scene as a local initial-dialogue adaptation. Migration132 records the original Grugal contract and enables its registry entry for instance0. This authorization deliberately does not claim that original quest visibility has been reconstructed. The previous four misplaced local trial actors remain quarantined by migration126. No duplicate quarantine migration or invented replacement coordinates are needed.

`npc_capture_contracts.py` admits original negative IDs outside the former local reserved range only when all original binding fields, actions and source digest match the joined native capture ledger. Database constraints bind actor identity/breed/map/XYZ/root to that ledger. The runtime also enforces native appearance/action availability, scene/instance, proximity, duplicate identity/position rejection, and session revalidation. No quest grants or automatic subsequent movement are added.

After coordinated migration/deployment, the complete manual probe is:

1. Log in with an existing account authorized to use the test console. Run `!tp 1387 -11 0 2`.
2. Confirm **Grugaloragrán** appears at(-12,0,2), rather than its later captured position(-16,0,0).
3. Choose its native talk action. Expect the original initial dialogue node5764, attributed to the same NPC. Close with its native exit choice. No quest reward or scripted movement should occur.
4. Reopen the dialogue, move farther than four cells away, and attempt the earlier choice. The server must reject the stale interaction.
5. Run `!tp 1134 -12 -8 -1`. Confirm the four misplaced trial actors are absent. Existing original scenery/NPCs are separate and must not be removed by this change.

Native codec verification tool `sniffer/java/VerifyCapturedNpcInitialScene.java` consumes server-produced spawn/dialogue fixtures using installed `ctE`, `eHj` and `cuz` decoders. Luna received the exact command and test scope. Runtime activation and graphical acceptance remain pending; source preparation is not deployment evidence.

## Reference replay scene correction

A separate general replay defect could reintroduce the original map1134 NPCs when reconnecting on another map: the previous reference replay removed players but retained every captured nonplayer. `npc_capture_scene.py` now decodes the verified native format11 POSITION and retains those actors only on their captured public map. Private instances cannot inherit public reference actors. The caller supplies all registry IDs, including disabled rows; those identities are excluded from reference replay so current registry publication owns them exclusively and quarantine cannot be undone by an old capture. Unknown serializers preserve existing behavior rather than guessing their position fields.

This helper has dedicated controls for original-map retention, foreign-map/private-instance exclusion, malformed payloads, envelope identity mismatch and exclusive registry ownership. Root owns its replay integration; this report does not claim the runtime process has received the source change.

LunaFast read-only native geometry qualification: map1387 contains362 cells; both the original NPC cell(-12,0,2) and manual teleport cell(-11,0,2) are native walkable cells. No replacement or nearby guessed NPC coordinates were used.

## Automated qualification receipt

LunaFast completed27 distinct tests:2 isolated PostgreSQL migration/constraint cases and25 pure/export/actual-replay controls. All27 passed. The first replay harness attempt lacked the actual wire function's `struct` global; only the harness namespace was corrected, then all4 replay cases passed. Runtime sources and root dispatcher remained stable. The complete134-migration private snapshot was hash-stable.

Actual server-generated packets also passed the installed native Java oracle:12608 spawn body127 bytes and12969 dialogue body13 bytes. A stronger full native entity roundtrip passed: `Arrays.equals(actor.aLJ(), entity.a(eHf.values()[11]))`. Thus the decoder accepted the complete actor encoding, beyond its early position fields. Evidence log `.runtime/local/verification-fast-20261011/npc-gate.log` and LunaFast native-oracle receipt. No runtime database migration, image publication, service restart, or graphical acceptance is implied by these automated results.
