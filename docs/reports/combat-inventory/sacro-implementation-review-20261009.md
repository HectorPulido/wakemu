# Sacrier local implementation and acceptance — 2026-10-09

Status: implemented locally; no restart or deployment. Cra and Iop remain provisionally accepted (2/18); Sacrier awaits graphical/manual acceptance. This report supersedes the implementation backlog in the historical inventory, not its catalog evidence.

## Corrections

- Respect attested native missing-state behavior without inventing state759. Unknown missing states still fail validation.
- Support native dispel flag17 and avoid rearming a duration owner after a terminal turn-start reaction.
- Replay actual paid AP/MP/WP cost events without charging twice; exercise the real Pact/Heart chain and rollback.
- Skip armor on native off-play recipients before calculation. Columnata armor belongs to the caster, including lethal casts.
- Apply declared relationship selection to fresh server group children while preserving explicit retained targets. Sacrifice installs the protector and ally states on their correct owners and removes both below the native threshold.
- Remove the synthetic displacement2128 fallback; use native Cinetosis producers and expire one-cast helpers at the successful cast boundary.
- Preserve native displacement rules for stabilized actors, large footprints, carried actors and carriers. Unflagged carrier release executes its original child effect rather than directly unlinking actors.
- Recognize unconditional null equipment400 markers; the reported Cra mount warning119215 is corrected without changing mount statistics.

## Local evidence and limits

- [Normal casting regression](sacro-implementation-normal-20261009.json): Cra, Iop and Sacrier at levels20/200; 12/12 Ready decks,105/105 spell-level pairs,195/195 prepared attempts committed. Sources stable. Baseline coverage is not proof of every conditional combination.
- [Passive cycles](sacro-implementation-passives-20261009.json):20/20 installed and completed with real Ready/turn/ACK/expiry;10 activations observed, no incomplete traces. A completed cycle does not assert that every passive-specific trigger occurred.
- [Transformation](sacro-implementation-morph-20261009.json): real producer chain, all three transformed casts committed, original book restored and expired UID rejected; sources stable.
- [HP boundaries](sacro-hp-threshold-pipeline-20261009.md): real Punishment, Refusal and Heart paths around20%/50%, including repeated self-loss.
- [Sacrifice](sacrier-sacrifice-pipeline-20261009.md): allied redirection, position exchange and threshold cleanup.
- Large displacement geometry matched the original Java oracle16/16; carry factory/checkpoint/release5/5 and teleport surfaces10/10 passed.
- Final focused local regressions: Cinetosis/lethal/displacement/zero-HP/teleport/LOS suite55/55; Pact, Sacrier turn-helper lifecycle, native granted cast and armor suite12/12; HP-boundary suite6/6. Pact was also rerun alone and passed. The Cinetosis lethal path now uses an actual legal native target and confirms one death plus fight completion.
- Shared Cra/Iop cast, movement, boundary and external-marker regressions:32 tests;24 passed and8 optional tests skipped.
- Cinetosis movement variants executed6/6 across stable source runs: [critical and swap](sacro-implementation-cinetosis-movement-variants-20261009.json)4/4, plus [corrected native push](sacro-implementation-cinetosis-push-20261009.json)2/2. The old push fixture put an NPC directly on the casting ray and correctly rejected with `twG`; original NPC placement now keeps that ray clear. Native417107 applies4801 through415996 (cross1), then417108 pushes the adjacent ring1 recipient. At levels20/200 the extra NPC moves(-10,-6,-1)→(-10,-5,-1), receives4801 level3/21 and loses2/16 HP (84→82/68); the primary recipient stays at84 HP during that first cast. Exactly one first-cast damage event targets the pushed NPC, before the class300 movement event, and both source checkpoints remain unchanged. The report's detailed calculation observers cover the later5030 pull on the primary recipient, separately from these first-cast push events.
- [Cra equipment warning](equipment-null400-warning-20261009.md):16 focused tests passed, including real mount scaling and unsupported negative variants.

These are offline production-path tests against the published catalog, not graphical certification. The generic audit deployment gate remains false: no deployment or full manual acceptance was performed. See the manual acceptance below before accepting Sacrier as3/18.

## Complete manual acceptance after an authorized full build/restart

1. Use a Sacrier with a Cra or Iop partner in the same room. For all unlocks use `!nivel250`; equip legal decks and rotate through all21 actives and20 passives. Record the deck and combat ID for each run.
2. Start PvP, ready both clients and play at least two complete rounds. Each client must show the same current fighter; only its owner can act, with the correct spell book and resource costs. Repeat in PvM.
3. Test each elemental attack on a surviving target and on a lethal target. Columnata must grant armor to the Sacrier; a killed actor must neither occupy a cell nor block vision, and its own model must play the death animation.
4. Apply Cinetosis and force a real pull/push or exchange. Check one qualifying native reaction per producer, no reaction on a blocked/no-movement attempt, and no leftover one-cast helper triggering on a later unrelated cast. Repeat with a large or stabilized target.
5. Cast Sacrifice on the allied player. Hit that ally from the opponent, verify redirection to the protector and the expected exchange, then cross the ally cleanup threshold and verify both linked states disappear.
6. Exercise Punishment and self-loss above, at and below20%/50% HP; compare tooltip/state changes and resource costs. Test Refusal, Heart and Pact with their actual conditions. Self-loss must not consume ordinary armor or duplicate reactions.
7. Earn the transformation through its normal condition. Use all three transformed attacks, end the transformation, verify the original book and grants return; old transformed shortcuts must not cast expired actions.
8. Rotate passive decks, including Immolation. Finish a fight through a passive/turn-start kill. The terminal animation, rewards, actor cleanup and next fight must complete without waiting for a nonexistent turn owner.
9. Reconnect either client during placement and during a turn. Surrender one participant, then complete another fight normally. Both clients must leave combat consistently; party sword icons must clear, the dungeon must advance on victory and retain a retryable group on defeat/abandonment.
10. With the Cra mount18682 equipped, enter combat. The119215/400 omission warning must be absent, normal mount bonuses unchanged, and Cra/Iop attacks must still work.

No manual step has been claimed as completed by this workstream.
