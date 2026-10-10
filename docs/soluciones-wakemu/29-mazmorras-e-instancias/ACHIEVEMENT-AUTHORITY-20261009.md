# Native achievement entry authority — 2026-10-09

Migration 086 establishes an explicit durable achievement baseline for local
characters. The local server has no previous quest-state engine or quest import;
its locally created characters therefore start with empty running/completed/
objective lists, with provenance `local_server_initial_empty`. Initialization
preserves existing snapshots. The character-creation trigger initializes new
characters. No completed objective is fabricated.

The native dungeon criterion callback now reads this server-owned snapshot.
Missing rows remain unknown and fail closed; client packets cannot supply or
mutate facts. Malformed identifiers and contradictory running/completed states
are rejected. This is an authorization baseline, not a quest progression engine.

Casa de Miabuelita's native criterion is:

```text
not (IsAchievementRunning(5568)
and IsAchievementObjectiveComplete(11513)
and not IsAchievementObjectiveComplete(11515))
```

This excludes a temporary quest state; it is not a quest prerequisite. An
explicitly initialized empty snapshot permits entry. Running quest 5568 with
objective 11513 complete and 11515 incomplete rejects entry. Completing 11515
permits entry again. The general query producer also handles achievement
predicates in Savanastraux and the Father Kwismas workshop, preserving native
results: a positive completion requirement remains false for an empty snapshot.

Sorciere and Wagnar require `HasState`, for which persistent exploration-state
authority remains absent. Combat state containers cannot substitute for it.

## Live r58 acceptance failed — Tofullero

Hector entered normally with two characters and was placed at the gate on the
Yopuka's side. The initial encounter remains behind the closed gate, includes
Tofu Real, and cannot be reached normally. Screenshots show an eight-member
group including the boss. This fails practical first-room access and the user's
expected dungeon ordering/composition. The accessible-room policy and automated
transition tests are insufficient to establish a playable dungeon. Reopen entry
anchors, reachable encounter placement and native room composition/order.
Automatic post-victory progression remains unaccepted because a normal first
encounter cannot be started. Do not ask Hector to defeat the inaccessible group
or use administrative teleport as proof of a working dungeon. No code changes
or restart were made while recording this feedback.

## Earlier proposed progression acceptance (blocked by first-room access)

1. Reconnect two characters, form a group and run `!tp 527 -128 -33 0` on
   each. Enter Tofullero through its native entrance, not by teleporting directly
   into the interior asset map.
2. Both must share one run. Defeat the complete eight-monster room encounter
   and return all participants to exploration.
3. Both must automatically move from `(34,-29,-11)` to `(11,-45,-8)`, then
   after the next room victory to `(16,-26,0)`, then outdoors after final victory.
   Rewards must not duplicate; a separate party must have a different run.
4. Approach Casa de Miabuelita on map 527 and enter with an ordinary local
   character. It must no longer fail for missing achievement predicate authority.
5. Recheck accepted Jalató solo entry, progression and exit for regression.

All 87 installed configurations use the local accessible-room policy: native
interior doors are disabled and committed victory triggers automatic travel.
Tofullero's native room ordering/composition and reachable first encounter failed
live acceptance as recorded above. The disabled visual door policy does not
make the current initial encounter reachable.

Source and migration are deployed in the complete shared r57 image. Automated
validation and visible acceptance are distinct; this document does not claim
that either dungeon has passed a full new client run.
