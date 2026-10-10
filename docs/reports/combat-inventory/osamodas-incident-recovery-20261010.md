# Osamodas combat recovery incident — 2026-10-10

## Scope and evidence

Character 13 (breed 2), account 2, map 1134. Times below are UTC;
subtract five hours for Hector's local time. Evidence is the private server log
`.runtime/local/logs/game-server.jsonl`, with the relevant window preserved at
`.runtime/osamodas-incident-20261010/server-window.jsonl`.

| Time | Observation |
| --- | --- |
| 05:27:57.488 | Fight 135 returned to the world after abandonment. |
| 05:31:16.292 | Fight 136 entered placement with player 13 and enemy -1125899906869760. |
| 05:31:17.419 | Server receive observed EOF from the client socket. Fight remained in placement; player had 2050 HP, enemy had 46 HP. |
| 05:31:47.236 | New connection reattached owner 13 to shared fight 136. |
| 05:31:59–05:32:00 | Abandonment finished fight 136. A delayed recovery request then failed with `No current duration owner`; a delayed turn ACK was rejected as stale. |
| 05:32:00.387 | Terminal acknowledgement returned player 13 to the world. |
| 05:32:05.187 | Fight 137 entered placement. |
| 05:32:22.656 | Spell 7316 executed. |
| 05:32:23.397 | Fight 137 finished normally. |
| 05:32:24.394 | Player returned to the world; no server disconnect recorded for this finish. |

The recovery rejection is secondary to the original EOF, rather than its cause.
The enemy was present in authoritative server state at disconnection. A missing
client appearance after reconnection is a separate presentation issue.

## Proven recovery defect and local correction

`RuntimeMessages.recover` previously requested `current_turn_duration` before
checking whether an active timeline existed. Placement and finished phases do
not own a current actor. A late coX13332 could therefore raise the duration-owner
error after legitimate terminal cleanup.

The correction checks participation and the exact fight ID first, then returns
an empty delivery for placement/finished phases. Existing pending presentation,
ACK state, FSM state, counters and deadlines remain intact. Active recovery
continues through the existing native timeline serializer and duration policy.
This does not fabricate an active turn or replay a finished combat.

Regression module: `server/tests/test_combat_nonactive_recovery.py` checks
placement roster/presentation preservation, terminal queue/ACK preservation,
and rejection of foreign owners, foreign fight IDs and malformed bodies.
Source compilation and `git diff --check` passed. Execution is delegated to
the shared Luna validation run alongside existing runtime/recovery tests.

## Original placement disconnect remains unproven

Fight 136 initial outgoing placement sequence was
12436, 13249, 13652, 12847, 13684, 13026, delivered between
05:31:16.291489 and 05:31:16.292045. Its start request completed successfully;
no server exception preceded EOF approximately 1.13 seconds later.

Fight 135's enemy identity was -1125899906869632, whereas fight 136 used
-1125899906869760. This does not support a direct reuse of the preceding
fight's enemy identity. Fight 137 reused fight 136's surviving group after
abandonment and completed normally; identity reuse alone is not evidence of
the original fault.

The server's post-EOF `world_delivery_failed_before_shutdown` occurred later,
at 05:31:17.427203, with an already closed socket. It cannot explain the earlier
client EOF. Relevant client logs rotated out before preservation, so the
client's reason for closing cannot be recovered from the available artifacts.
No speculative disconnect fix is included in this change.

The root workstream separately investigates/restores ordinary PvE enemy world
appearances before owned reconnect bootstrap. That addresses the demonstrated
missing-enemy reconnect presentation and does not establish the original EOF's
cause. No restart or deployment was performed by this diagnostic workstream.

## Ordinary PvE reconnect appearance correction

Exploration excludes claimed monster groups. A reconnecting fresh client cannot
resolve those NPC objects from the combat stats bootstrap alone. The reconnect
adapter now prefixes an owned 12608 appearance snapshot using original catalog
profile/level and current fighter position before 12847. It preserves the group
lease and fight, rejects incomplete or foreign group authority, excludes native
registered summons and leaves the separate Rift wave snapshot owner intact.
Duels do not fabricate monster groups.

`test_combat_reconnect_world_actors` covers payload identity/position, ordering
for placement and active reconnect, exclusions and authority failure atomicity.
The cross-class offline matrix passed 106 tests with native granted-cast opt-in;
this does not certify the NPC property change, whose actual shipped Java parser
probe subsequently exposed an additional wire-layout mismatch under repair.
The updated reconnect reconciliation module separately passed 10 tests against
the current disconnected-recipient ACK contract. No deployment was performed.

## Final local validation

The [NPC property wire correction](osamodas-capture-client-property-fix-20261010.md)
now passes the actual shipped client parser through all 11 format2 sections to
exact EOF. Four native probes cover capturable/noncapturable catalog profiles,
modified live counters and explicitly empty live counters. The combined final
Python matrix passed **116 tests, zero failures/errors/skips**, including the
updated reconnect ACK contract and prior four classes. This supersedes the
pending codec caveat above. Live manual acceptance and original EOF diagnosis
remain outstanding; no restart or deployment was performed.
