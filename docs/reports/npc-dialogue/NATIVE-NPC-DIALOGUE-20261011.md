# Native NPC dialogue extraction and server runtime

## Delivered source evidence

The read-only exporter `server/tools/export_npc_dialogues.py` loads installed
`aKO/aKP` binary records through native `apw` and writes the deterministic gzip
catalog `server/protocol/npc-dialogues.json.gz`. It never changes client files.
SHA-256 provenance covers the client JAR, all binary archives, scripts, language
archives and Java exporter.

- 4,599 dialogue nodes and 7,790 offered choices.
- 467 nodes and 2,241 choices retain native criteria expressions.
- 16,521 localized dialogue/answer/speaker entries in each language (66,084 total),
  plus 2,857 breed names per language; 19,378 exported entries per language.
- 422 native conversational NPC references and 505 native START_DIALOG actions.
- All 385 `interactiveDialogs/*.lua` NPC audio scripts.
- All 2,384 `scenario/*.lua` scripts, including 30,793 function declarations.
- Native text categories: dialogue text 75, choice text 76, speaker override 159.

The catalog preserves entire scenario sources, not merely selected quest samples.
Lua remains inert evidence; the server does not execute it.

## Native protocol evidence

`cos` emits request 12535 as big-endian `int node_id, byte speaker_type,
long speaker_id`. `cot` emits request 12058 as `int node_id, int choice_id`.
`chC` consumes response 12969 (`cuz`) with the same node/type/speaker body and
response 12218 (`cuA`) with `int node_id`. `eUF.NPC` is speaker type 2.

`bak` constructs dialogue nodes and choices from `aKO/aKP`; node criteria,
choice criteria, choice type and native boolean are retained without renaming
unknown semantics. `bpb` uses categories 75/159; `bpa` uses 76.

## Server integration

`wakfu_server.maps.npc_dialogue.DialogueSession` provides native response bodies
and validates selected node/choice, authoritative speaker/range callback and
criteria. An unknown graph edge or unhandled nonempty criterion fails closed.
The callback is checked again for every selected choice. Allocate one session
per live character connection and close it on transfer, disconnect or combat.
Do not accept client-requested node IDs without the server NPC root allowlist.
The callback must validate NPC identity, instance, interaction range and the
allowed dialogue root/node for that NPC. Node and choice predicates must use
server state; client-visible criteria do not authorize rewards.

A server graph explicitly maps `(node_id, choice_id)` to a target node or `None`
for close. The runtime deliberately ships with no invented graph. An empty
native terminal node accepts choice -1 to close. Native choice -2 advances text
locally and is not accepted as a server transition.

## Local initial world placement

Migration121 creates `world_dialogue_npcs` with configurable map/instance,
position, appearance reference, native action allowlist and initial root.
The initial **local** cluster contains four native speakers on map1134,
instance0, each two tiles from the default character start(-12,-8,-1):

| Native speaker | Breed | Position | Initial root | Native action |
| --- | --- | --- | --- | --- |
| Arh Kayuh | 2986 | (-10,-8,-1) | 6274 | 515 |
| Laura Craft | 3814 | (-12,-10,-1) | 6554 | 698 |
| Tristepin | 4687 | (-14,-8,-1) | 7122 | 968 |
| Kabrok | 3580 | (-12,-6,-1) | 7279 | 673 |

All four positions and the character start are verified walkable in the installed VB/Vy map1134 export
(`.runtime/e18-deploy-server/protocol/combat-maps/1134.json.gz`).
Arh Kayuh's native action515 has START_DIALOG type4 and client criterion
`GetInstanceId() <> 1342`. Every selected root explicitly supplies its matching native NPC portrait and
localized speaker. Laura Craft, Tristepin and Kabrok have unconditional native
START_DIALOG actions and root criteria. Arh Kayuh root6274 explicitly uses
portrait`npc2986` and native localized speaker Arh Kayuh. Its exact placement and
selection as the first conversation are local Wakemu configuration, not an
assertion of an official position or story state.

`npc_world.spawn` uses native ctE12608/eHj format11 with the breed reference;
no client assets or combat-group registrations are changed. The native click
path is `blA` -> `bly.jW` -> `cnT`, opcode13222 with two big-endian longs:
NPC actor ID and native action ID. The runtime validates both, exact instance
and Manhattan interaction distance, and rechecks on subsequent selections.

Initial unconditional native choices currently close the dialogue, deliberately
without traversing unverified trees or granting anything. Conditional choices
fail closed. Full decision trees are a follow-up. No custom text is substituted.
Reserved conversational IDs occupy a separate negative Lua-exact range.

Root dispatcher integration publishes SQL scene snapshots on world joins,
handles13222 through `npc_world.begin`, sends12969, and routes12058 to the
live session. The dialogue gzip must be copied into the server image. No
restart/deployment is authorized in this code-only turn.

## Remaining work and limitations

The installed dialogue table does **not** contain choice destination nodes,
server quest state transitions, objective authority, rewards or NPC world
placements. Choice IDs and sequential nodes are not evidence of an edge. The
scenario scripts contain client visual/event callbacks and incomplete server
semantics; retaining them does not implement quests. No identifiable direct
`startInteractiveDialog/displayDialog/showDialog` calls were found in those
scripts by the exporter.

The extraction is complete for the identified tables/scripts. General SQL
placements and initial NPC appearance/dialogue runtime are implemented; native
decision trees and quest mechanics remain open. Dispatcher integration is
owned by the coordinating agent. Official captures or verified native/server map data must establish those
contracts before activating them. No service was restarted and no client asset
was changed by this work.

## Validation and manual acceptance

Automated regression files: `test_npc_dialogue.py`, `test_npc_dialogue_export.py`,
`test_npc_world.py` and `test_npc_world_postgres.py` in `server/tests/`.
The PostgreSQL test checks the seeded native portrait/name/action, scene isolation
and live disable invalidation. `.runtime/local/npc-seed-spawn.bin` is prepared for
the installed-codec oracle `sniffer/java/VerifyMonsterIdentity.java` with actor
`-2251799813685248` and group `2251799813685248`.
Command: `PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_npc_dialogue.py`.
The coordinating agent delegates execution to Luna.

After the code is deployed in a future authorized window:

For the local cluster, connect with a character near the default start on map1134,
instance0, position(-12,-8,-1). Arh Kayuh should appear at(-10,-8,-1).
Click its native dialogue action and expect root6274, Spanish text beginning
"Hmmm..." and the choice "Pero... ¿por qué?". That initial choice closes the
window; full story branches are explicitly deferred. Repeat the native dialogue
action for Laura Craft(-12,-10,-1), Tristepin(-14,-8,-1) and Kabrok(-12,-6,-1);
expect the matching native names/portraits and root text. Their first choices
also close and grant nothing. No quest or item is granted.

For future accredited full graphs:

1. Connect normally and walk within interaction range of that NPC.
2. Click the NPC and select its dialogue action. Expect the native speaker,
   localized text and available choices, without a client patch.
3. Select every available branch, including terminal close. Expect only the
   mapped native destination node; reopening starts from the authorized root.
4. Repeat with a character that does not satisfy a choice criterion. Expect the
   option to be unavailable and a forged choice to be rejected server-side.
5. Open a dialogue, walk out of range or change instance, and attempt the old
   choice. Expect rejection and no quest/inventory mutation.
6. Reconnect and reopen the NPC. Expect no stale dialogue session. Quest progress
   and rewards must not be accepted until separately implemented and validated.
