# Mod'Ulo and B. Toven initial interaction audit

Installed native conversational definitions preserve Mod'Ulo breed4399,
action884, and B. Toven breed4069, action798. Both are native START_DIALOG type4
with empty criteria, duration0, payload `cbH=0`, and identical other action flags.
Native factory `blC` maps START_DIALOG to `blA`; after its subscription check,
`blA.i` calls `bly.jW`, which sends `cnT` actor/action request to the world.
This is a server dialogue request, not a local audio-only command.

The complete27,263 Lua-file scan finds no exact reference to NPC4069/4399 or
visual1300086/144902070, and there is no `interactiveDialogs/npc4069.lua` or
`npc4399.lua`. Missing local sound scripts cannot establish a silent service or
select an initial dialogue root.

New native content evidence for Mod'Ulo was missed by portrait matching:

- Node3972 has blank portraits and empty node criteria. Its native localized
  introduction explicitly welcomes the player to their Haven Bag and identifies
  the speaker as Mod'Ulo. Choices include10098 (questions),10023 (close) and
  multiple conditional hunting trophy quest options.
- Node4105 repeats that same introduction but requires global Ogrest-down state,
  reset eligibility for quest3874 and real level51. It offers a different quest
  menu. This is a distinct conditional variant, not evidence that3972 is always
  the action884 root.

B. Toven's name appears explicitly in nodes5537/5538, but their content concerns
unusual Gobball behavior and the player's mysterious diary. Choice12899 requires
quest5043 running and objective10375 complete/10376 incomplete. These are story
conversations; the name does not prove either begins the unconditional action798.

The two breed/action contracts are accredited. **Neither action-to-initial-root
join is accredited by these installed assets.** Mod'Ulo3972 is a concrete native
candidate for capture recovery, not an activated or inferred binding. No client,
server, service or database change was made.

## Complete available original-frame scan after protector recovery

A follow-up inspected every `frames.jsonl` under the original creation, original
 dungeon and root capture directories, deduplicating identical file hashes.
Nine unique snapshot files contain frames explicitly attributed to the original
Ankama game server. Partial snapshots overlap and are not counted as independent
conversations. No outgoing13222 action798/884, incoming12969 root3972/4105/5537/5538,
or response correlated with either target action appears in any of those files.
Private receipt:
`.runtime/local/npc-protector-validation/remaining-initial-root-scan.json`.
Consequently the available captures do not supply the missing initial-root join;
the native text candidates remain withheld instead of being guessed.
