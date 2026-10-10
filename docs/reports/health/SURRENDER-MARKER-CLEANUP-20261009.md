# Surrender marker cleanup

Public fight swords were retained after a committed single-owner surrender.
`publish_external_marker` required `settlement_ready` for every finished fight,
but surrender commits an aborted outcome without reward settlement.

The publisher now accepts the committed abandonment continuation
(`runtime.abandon_owner`, finished fight, no winner) as terminal authority.
`combat_abandon.prepare` sets that continuation only after its abort and health
transaction commits. Normal lethal previews still wait for settlement. Active
individual withdrawals retain the marker for the remaining combatants.
Defeated-group/corpse publication remains restricted to normal settlement.

The regression executes the real extracted publisher with a real marker
registry. It checks unsettled lethal previews, settled completion, active
withdrawal, committed surrender, observer exclusions, idempotent removal, and
absence of marker replay after surrender.

Manual acceptance:

1. Keep a second account on the same public map as an observer.
2. Create a monster with `!mob 1 10 1` and start combat with the first account.
3. Confirm the observer sees the swords. Surrender during placement, then repeat
   after pressing Ready. The observer's swords must disappear immediately.
4. Leave and re-enter the map with the observer: no surrendered marker returns.
5. Join a fight with two accounts, withdraw only one, and confirm the swords
   remain while the other participant continues. End that fight normally and
   confirm the swords disappear.

Automated validation and deployment are recorded by the coordinating agent.

Live supporting evidence: fight 123 logged `shared_pve_abandoned_waiting_return` at 2026-10-10 01:15:15 UTC without a subsequent external-marker removal in the reviewed incident window. Normal completed fights 121 and 122 published opcode 12238. The private source is `.runtime/local/logs/game-server.jsonl`; no session generations or payloads are included here.

Manual acceptance: Hector confirmed after the r62 deployment that swords disappear correctly on surrender (2026-10-09 local evening). The reported marker-cleanup issue is accepted; spectator placement/summon visibility and performance remain separate open work.
