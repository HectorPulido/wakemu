# Final eleven ordinary dungeons: complete manual acceptance

These are source candidates. This checklist does not imply deployment or graphical acceptance. Deploy the complete shared server implementation and the reviewed configurations before testing. Preserve existing combat and spell changes. Start fresh runs: existing instances retain their pinned configuration.

Use two independent accounts in one group, adding heroes if desired, up to six participants. Move every independent character to the exterior coordinates below, then use the real dungeon entrance. Never teleport directly into the interior: that bypasses admission and progression checks.

| Dungeon | Exterior approach command | Entrance object | Expected encounters |
| --- | --- | --- | --- |
| Factor Trool | `!teleport 337 -17 -270 5` | 18969 | One arena |
| Ciudad Prohibida | `!teleport 1252 -17 -148 -60` | 31868 | Lobby doors already open; one arena |
| Steamers | `!teleport 1365 -115 -37 -36` | 33633 | Four; return through the hub between branches |
| Astrolillo | `!teleport 235 -303 -567 48` | 17373 | Four; note and training annexes remain transit |
| Negraspora | `!teleport 796 -71 96 20` | 21779 | Two; return to entrance exit 21700 |
| Necromundo | `!teleport 1365 -120 25 -45` | 34843 | Open lobby; one Toross Mordal encounter |
| Guarida de los Supervillanos | `!teleport 709 -4 4 0` | 20372 | Open lobby; four different bosses together |
| Riktus de Élite | `!teleport 1207 -112 -88 40` | 14568 | Four; fixed west main route, east retained as optional transit |
| Hammalmejil | `!teleport 458 67 -41 0` | 19547 | Three; clockwise route and final return to entrance |
| Base del Susurro | `!teleport 1295 -105 -59 -5` | 32889 | Four; includes the decoded activation frontier |
| Arena Danzante | `!teleport 458 -44 -81 30` | 18988 | Three successive encounters in the same arena |

## One complete acceptance cycle per dungeon

1. Enter through the real object with the group. All admitted participants must appear in the same instance, outside combat, with valid health and their own spells. The first enemies must be reachable; narrow lobbies must contain no inaccessible enemy group.
2. Before each victory, attempt the next entrance or boundary. It must reject premature access. In a shared arena, no later group should exist yet. Confirm the displayed native door state agrees with whether it can be crossed.
3. Start a normal fight, confirm fighter order and participation, then win. For traversal-only testing, `!winfight` can replace the victory; this does not validate boss mechanics. Follow the native route after every victory. A return through an earlier room must preserve progress and must not respawn a cleared group.
4. In the final encounter, verify the documented boss appears exactly once, except Supervillanos, which has one of each of its four different native bosses. There must be no generated dominant or archmonster substituted into the ordinary groups.
5. Finish the last fight. Use the native exterior exit. Astrolillo legitimately exits at map 1211 near `(8368,8352,0)`, rather than returning to its entrance map. Negraspora uses the verified entrance-side exit; do not rely on the unresolved height of exit 21701.
6. Re-enter as a group. Expect a fresh first encounter and locked later stages. Start a fight and use `!losefight`, or surrender normally. Defeat must not unlock the next encounter or leave participants in stale combat.
7. Use `!exitdungeon` to abandon the fresh run. Every independent participant should leave; verify hero and party state, then re-enter once more. No previous victory or branch selection may leak into this run.

For Arena Danzante, also check that the second and third enemy groups appear after the corresponding victories without a room transition; the boss belongs only to the third group. For Steamers, attempt the boss branch after only the first or second victory: returning to the hub must not permit skipping the third encounter.

For Base del Susurro, follow entrance arena → small arena → larger middle arena → boss. The activation boundary between the two middle arenas is a native zone, not a new visible door. For Riktus, take the west route for the second fight; trying the east transit route must not bypass that fight or permit early access to the common third arena or boss. Its original selectable branch progression remains outside this local configuration.

All eleven exterior coordinates above were checked against published native walkable terrain. This verifies the approach commands, not graphical interaction with each entrance.

These checks validate admission, placement, progression, repeated encounters, exits and re-entry. They do not certify original boss scripts, optional stele modifiers, original rewards or every quest annex. Report a failure with the dungeon name, step, current character and screenshot; do not repeat previously accepted unrelated systems.
