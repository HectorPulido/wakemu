# Owned heroes combat admission

The admission adapter uses the actual company roster and actual character IDs.
Each hero receives its own native combat snapshot, equipment/build statistics,
health baseline, resources, and available team placement cell. The selected main
character's real account session authorizes all heroes; no extra account or
selected-character session is created.

`combat_heroes.admit_owned_heroes` requires an active transaction and existing
durable main participant. It locks the account, selected session, roster, fight,
and actual hero health rows. Admission validates the complete roster against
the six-player team limit and available cells. A savepoint rolls back partial
hero membership and regeneration changes on failure. It returns an unpublished
candidate fight and actual source characters; the caller commits before
publishing the candidate.

Initial PvE placement includes heroes before registry registration. Joining an
existing placement uses a transaction spanning main/hero durable admission and
native packet construction. World appearances precede native fighter admission
and placement bootstrap. A new peer receives appearances for the full player
roster, including heroes admitted by other accounts. Regeneration is paused for
each hero while in combat.

Ordinary combat with an empty company retains the original fight object and
the exact `create_placement` packet bytes. Hero admission rebuilds placement only
when actual heroes were added, using the same fresh-player and fresh-monster
serializers as `create_placement`. Runtime movement/cast stat snapshots must not
replace the fresh placement payload. The native placement opcode sequence remains
`13652, 12847, 13684, 13026`; hero world appearances precede that sequence.

## Automated verification

Luna's targeted gate passed 73/73 tests, including five isolated PostgreSQL
admission cases built from real accounts, real characters and the saved company
roster. The primary acceptance case encodes three native player appearances and
the complete placement bootstrap, verifies separate positions, and exercises
each character's turn and action under the single real main session. Additional
cases cover capacity, stale sessions and savepoint rollback when the second hero
cannot enter. Shared combat and spell-source regressions are included.

This verifies the protocol/backend path. Rendering and interactive selection in
the running graphical client still require the manual acceptance below.

## Manual acceptance

1. Add two existing, living characters from the same account to the company.
   Choose characters with different equipment/builds so their statistics differ.
2. Start an ordinary monster fight. Expect three distinct player actors in
   separate allied placement cells, with their own HP, AP, MP, WP and builds.
3. Join from a second account with its own two heroes before placement ends.
   Expect six distinct allied actors visible to both clients. A seventh actor
   must be rejected without a partial company or extra durable membership.
4. Ready each account, act on each character's turn, and finish the fight.
   Verify each character's own spells, wounds, and reward inventory.
5. Repeat with withdrawal and reconnect. Verify that heroes remain under the
   real main's ownership and that persistent health is restored individually.

Rift admission groups the frozen company by each account's real selected main,
validates the exact owned roster again inside each admission transaction, and
checks the final admitted player identities against the frozen members.
Full graphical acceptance remains pending; backend and packet tests alone do
not certify it.

## Surrender followed by a second fight

Read-only investigation of the reported failure confirmed that both consecutive
fights retained the actual main and both heroes as durable participants, while
the saved company still contained both living heroes. The disappearance was
therefore a client hydration failure, not loss of the saved roster or combat
admission. The deployed return replay used the exploration `PLAYER_TEMPLATE`
for native `cue12093`; the corrected shared implementation uses the full owned
format-10 `OWNED_HERO_TEMPLATE` in both world join and company publication.
No additional activation packets are needed on the return path.

The isolated PostgreSQL regression
`test_owned_heroes_survive_surrender_and_rejoin_second_fight` passes: actual
abandon/return, first registry retirement, removal/re-addition of one saved hero,
then a second fight with all three real participants under the unchanged main
generation and only the real main session.

The native owned-hero oracle verifies actual names, breeds, nonempty appearance
data, and each character's spellbook/decks across repeated hydration and owned
registry selection. Full graphical acceptance must also verify that, after
surrender, both company entries have their names and appearance, can be removed
and added again, and enter the next fight with the main.

## Terminal settlement investigation with an owned summon

For reported fight 155, the durable checkpoint already contains `phase=finished`,
`winner=0`, and the last enemy at zero HP. The registered owned summon delivered
the final damage and the FSM recorded the death and finished events. There is
no pending acknowledgement, but `combat_fights` remains active and no reward or
health-exit receipts exist. The final cast's request emitted its native action
and death messages before reporting `Sesión o personaje inválidos` during
completion. This isolates the failure to post-action settlement, rather than a
missing victory check or an undelivered damage action.

The reward-policy resolver still uses a strict selected-character fence for
each winning character; real hero IDs differ from the main selected by the
single account session. The settlement owner is correcting this authority
boundary while keeping registered summon UIDs excluded from character rewards.

### Terminal retry and interrupted-fight recovery

The owner heartbeat now retries the existing shared settlement operation for a
resolved PvE fight whose settlement is not ready, once the native action ACK is
clear. This uses the original reward, loot, group, corpse and terminal-packet
transaction. Already settled fights and explicit surrender remain excluded.
The eligibility regression suite passes three tests.

Fight 155 was privately backed up before recovery, including its complete
checkpoint, participants, current lease, world group and receipt tables. The
backup is runtime-only and excluded from publication. The existing restart
policy cancels interrupted fights; it does not award the unresolved historical
settlement. This cancellation frees the blocked character but must not be
reported as recovery of that fight's rewards. Future transient settlement
failures can retry through the live heartbeat without requiring that restart.
