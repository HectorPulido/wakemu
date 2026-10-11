# Palacio Zollo: two native routes and shared boss

Source-only release candidate: [V14 frozen evidence](PALACIO-ZOLLO-NATIVE-CYCLE-CANDIDATE-V14-20261010.json). This replaces the incomplete older two-room proposal. V12/V13 are superseded and must not be installed. No runtime activation or restart was performed.

## Recovered layout and general mechanism

Native definition 73 is Palais Lenald. The entrance is a noncombat lobby. Both documented alternatives contain three preliminary rooms and the same boss, rather than a combat in the lobby. [MethodWakfu's Wabbits guide](https://methodwakfu.com/quetes/principales/ile-des-wabbits/) confirms the two four-room routes; [Wakfu.Guide](https://wakfu.guide/donjons/126-140/) describes their different elemental mechanics. Those combat modifiers and branch-dependent emblem rewards are not certified by this traversal implementation; no spell or combat behavior was changed.

| Choice in lobby | Native first room | Second room | Third room | Boss | Return and exit |
| --- | --- | --- | --- | --- | --- |
| Source 34741 at `(-24,8,0)` | region 90 | region 41 | region 13 | region 0 | 34746 → lobby → 34747 |
| Source 34740 at `(-24,-8,0)` | region 91 | region 42 | region 18 | region 0 | 34746 → lobby → 34747 |

Each branch has four increasing local encounter groups, containing 2, 4, 6 and 8 actors; native boss 2556 appears only in the final group. These quantities are explicit local composition, not recovered official counts. [Native geometry](PALACIO-ZOLLO-NATIVE-GEOMETRY-REVIEW-20261010.json) and [annotated map](PALACIO-ZOLLO-NATIVE-GEOMETRY-ANNOTATED-20261010.svg) preserve both real walking paths and transport destinations.

Migration `112_dungeon_branch_selection.sql` stores one nullable branch choice per dungeon run. Entry initializes progression without a group. Choosing the native route commits selection, party travel, encounter registration and the per-member transition outbox together; failure rolls back all four. Reconnect and later room spawns use the stored route. Unselected terrain, transports and physical progression gates cannot authorize another route. The nonadjacent boss-to-lobby return preserves completion and uses the actual exterior exit.

## Automated verification

[Isolated PostgreSQL evidence](PALACIO-ZOLLO-NATIVE-CYCLE-PG-LIFECYCLE-V14-20261010.json) passed both branches with six independently controlled players. It verifies lobby without a spawn, selection rollback, durable choice, unselected-route rejection, four encounter/victory receipts, idempotent replay, atomic transitions and final native return/exit. A separate early lobby cancellation leaves the run incomplete. The native geometry remains unchanged.

Thirteen focused unit tests passed for the branch contract and stable JSON-owned configuration hashing. The hash correction also produced gameplay-identical Kokolost and Conohos replacements; [V15 PostgreSQL evidence](NATIVE-EVIDENCE-NORMALIZED-PG-LIFECYCLE-V15-20261010.json) passed both of those routes. Original frozen V7 files were preserved.

The broader extraction/configuration/movement regression ran 81 tests: 79 passed and two PostgreSQL transaction tests were skipped in that URL-free invocation. Isolated lifecycle checks were run separately. Fresh regressions passed for [Milubo](MILUBO-FOUR-ROOM-MIXED-PG-LIFECYCLE-POST-BRANCH-V14-20261010.json), [Pischina](PISCHINA-NATIVE-TRIGGER-PG-LIFECYCLE-POST-BRANCH-V14-20261010.json) and [Vid Vil](VID-VIL-NATIVE-HUB-PG-LIFECYCLE-POST-BRANCH-V14-20261010.json), including current migration and server callback source hashes. The [updated structural audit](POST-ZOLLO-ALL-CLASSIC-STRUCTURE-AUDIT-20261010.json) selects V14/V15; all 100 latest configuration records now have matching persisted plan/topology/route evidence hashes.

## Complete graphical acceptance after deployment

1. Use at least two independent accounts in one group. For full capacity, repeat with six independent players. Move each outside with `!teleport 1384 -116 -63 16`, then use the actual dungeon entrance. Everyone must arrive in the same private lobby, without a combat group there.
2. Choose the entrance near interior `(-24,8,0)` (native source 34741). The party must travel together and find the first group of two enemies in that first branch room. Return to the lobby using the native first-room return; choosing the other branch must remain unavailable. Re-enter the selected branch without creating another group.
3. Before winning, verify the next physical door is closed. Win the first encounter; the door must open visibly and allow access to the four-enemy second encounter. Repeat for the next door and the six-enemy third encounter. The other branch's physical gates must remain closed.
4. Win the third encounter, then use its native boss transport. Confirm an eight-actor final group with exactly one native boss. Defeat it normally; for a traversal-only probe, `!winfight` may finish each active fight, but that does not test combat mechanics.
5. Use native return 34746 to reach the original lobby. Cleared rooms must stay cleared and no fight must respawn. Use native exterior exit 34747; participants must return outside near `(-115,-63,16)` and be able to start a fresh run.
6. Repeat the whole run, choosing the entrance near `(-24,-8,0)` (source 34740). Confirm enemies appear in this alternative's three rooms and that it reaches the same final boss and exterior exit.
7. Start another fresh run and leave from the lobby before choosing a branch. It must not count as a completed run or create encounter rewards. Re-enter, choose a branch and surrender in its first fight: the second-room door must stay locked. Use `!exitdungeon` and confirm subsequent re-entry works.
8. Reconnect after choosing a branch in an additional run. The same branch and current encounter must remain selected, without duplicate monsters. Owned-hero travel remains a separate graphical integration probe; the six-player PostgreSQL evidence uses independent accounts.

## Coverage and remaining work

Source coverage becomes 96/107 distinct ordinary main routes prepared, with 11 structurally pending. Deployment coverage is unchanged. The shared branch selector is reusable, but Riktus de Élite and Hammalmejil have physical cycles without a matching native transport choice; this implementation does not resolve their puzzle/door conditions.
