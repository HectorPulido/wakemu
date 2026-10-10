# Friendly duel expiry retry loop

The October 9 22:57 local report was confirmed by repeated
`friendly_duel_invitation_rejected` events between characters 4 and 6 on map
527: `A recent same-pair duel reply may still be in flight`.
Read-only database inspection found invitations 15 and 16 still pending,
despite expiry at 22:18:19Z and 22:18:37Z, more than five hours earlier.
Both had null `responded_at`; the configured TTL and quarantine were 60 seconds.

Challenge creation retired expired invitations with `responded_at=now`, then
checked same-pair quarantine in that transaction. The check necessarily rejected
the request, rolling back retirement. Every retry repeated the same operation;
waiting never released the pair.

Automatic expiry now records the fixed `expires_at` boundary, both during
challenge creation and in the expiry worker. Quarantine remains enforced until
expiry plus its configured duration. Genuine received replies retain their
actual response timestamp and existing session/identity checks. Existing old
pending invitations recover on the next challenge without database repair.

Regression coverage in `test_friendly_duels.py` exercises repeated rejected
retries before the boundary followed by successful creation at the boundary,
and a delayed expiry worker that must not restart quarantine. These tests require
the isolated PostgreSQL fixture; validation is delegated to the test agent.

Manual acceptance: with two nearby characters on different accounts, challenge
and accept a friendly duel, play a turn, and finish or surrender. Also leave one
invitation unanswered, wait 120 seconds with the current 60/60 policy, then
challenge the same character again: the invitation must appear. A retry before
the quarantine boundary remains rejected. Repeat in the reverse direction.

## r64 deployment and complete acceptance

Full current checkout deployed as `wakemu-world:performance-20261009-r64` at approximately 23:11 America/Bogota. Image and running container verified against 677 source/migration hashes; previous image retained as `wakemu-world:backup-r63-before-idle-duel-fix`. All source edits shared by concurrent work are included. Focused combined validation: 258 combat/spectator/duel/harvest tests, 175 concurrent-module tests, and 11 migration tests passed without skips. PostgreSQL mutations were restricted to isolated test schemas.

Use two accounts A and B on the same map:

1. A challenges B through the normal character menu. B must receive the invitation; accept and complete one duel, including placement movement, a cast and surrender or normal completion. Both clients must return and move normally.
2. Wait 65 seconds after accepting/declining the invitation before repeating the same directed pair. A new invitation must work; the configured 60-second stale-reply quarantine remains intentional.
3. Leave a new invitation unanswered. Wait 125 seconds after sending it (60-second TTL plus 60-second quarantine and margin), then challenge the same character again. The invitation must work even after several rejected intermediate retries.
4. Start an ordinary monster fight and test placement, movement, spells, Ready and turn progression. No multi-second stall should be caused by idle harvest availability polling. Existing early/late spectator summon tests remain applicable. Record the exact local time of any new stall; continuous profiling remains enabled.

This release removes the proven receive-thread wait and infinite invitation quarantine. It does not claim all ecology or combat latency is solved. Whole-tick ecology fences remain a documented performance follow-up.
