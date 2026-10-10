# Friendly duel settlement with controlled summons

## Report and evidence

Hector reported failed surrender at 2026-10-10 00:24 local. The screenshot
shows `Friendly duel runtime roster is incomplete` after Cra beacon casts.
The runtime log confirms repeated settlement failures for fight 134, actors
4 and 6, at 05:24 UTC.

Settlement previously treated every controlled actor as an owning duelist.
Registered controlled summons therefore made the runtime roster larger than
the two consented characters. Terminal result metadata already distinguishes
registered summons from owning characters; settlement now uses the same
authority-validated summon classification before checking its exact owner roster.
It still rejects missing duelists and forged summon registrations. Healing,
original exterior positions, no rewards, and durable settlement checks remain.

## Validation

Three isolated PostgreSQL regressions passed initially: settlement with a valid
controlled summon, rejection with a missing real owner, and rejection of forged
summon authority. Full regression and deployment results follow below.

## Arena and placement follow-up

Duels use a separate 30-by-30 minimum policy, capped at 2,500 native cells.
Small native connected components remain smaller instead of inventing terrain.
Both duelists retain their exterior positions; placement offers distributed
slots on opposing reachable sides. Ordinary PvE retains random 5–7 minimum
dimensions, while its NPC initial formation spreads on the distant native side.
See [arena details](DUEL-ARENA-AND-TEAM-SPREAD-20261010.md).

Final placement/terrain/selector coverage passed 58 tests. Five isolated
PostgreSQL duel acceptance/settlement cases passed. Synthetic geometry
construction measured 58 ms CPU at 900 cells and 168 ms CPU at 2,500 cells
with eight NPCs; these are construction-only measurements, not live combat
latency guarantees. Broader current-checkout coverage passed 237 assertions;
its command also named one nonexistent module, reported separately as an import
error. Historical LOS fixture and direct finish packet-order expectation
failures were not represented as new production regressions or a green full suite.

## Manual acceptance after deployment

1. With two characters on the same open outdoor map, challenge the second
   through the normal character menu and accept the friendly duel.
2. Before Ready, select placement cells on opposing sides. Both clients
   should show the same positions; the duel should offer a broad 30-by-30
   native area where terrain permits, with no player on a rendered border.
3. Ready both characters. Summon at least one Cra beacon, then surrender
   through the normal combat menu. Both characters should return to exploration
   at full effective health, with no rewards and no roster-incomplete rejection.
4. Immediately challenge again, play a turn and surrender from the other
   character. Neither account should remain stuck in the previous fight.
5. Start ordinary PvE against multiple mobs. NPC starting positions and team
   placement slots should spread into opposing reachable regions rather than
   all clustering around the clicked monster. Move and cast at range, finish
   the fight, and confirm exploration movement resumes normally.

## Verified deployment

The current shared world service is running the concurrent complete image
`wakemu-world:heroes-combat-fix-20261010`. Its 687 source/migration hashes
match the full validated `wakemu-world:performance-20261010-r66` image exactly;
no overlay or partial rollback was deployed. The mounted AI fingerprint source
also matches the verified implementation. The existing world restart already
loaded that current code, so another redundant world restart was avoided.
Health and game ports 15556/15558 passed. The external profiler was recreated
against the current world process. Full-suite legacy fixture failures remain
reported above; this is focused regression validation, not a green full suite.
