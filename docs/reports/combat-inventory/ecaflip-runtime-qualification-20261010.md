# Ecaflip runtime qualification — 2026-10-10

Authority: published PostgreSQL release `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`. This report distinguishes catalog completeness, prepared casts, and executed semantic assertions. No service or catalog changes were performed by the class workstream.

## Confirmed automated evidence

- Current roster: 21 active spells, 20 class passives, 8 common passives, 13 tarot card abilities, and three summon profiles. Expanded current closure: 1,723 effects, 80 states, one area, 18 additional spells. There are no absent direct definitions in the extracted closure. Registration does not establish functional acceptance.
- The generic normal-cast audit prepared and committed 31 transactions across the 21 actives. Rejected contexts remain recorded rather than silently bypassed.
- Six actual seeded Ready branches create distinct owned three-card hands; all 20 optional passive initialization branches preserve caps and ownership (two test methods passed).
- All thirteen actual drawn card abilities cast successfully and retire the corresponding owned grants. Card carriers intentionally survive: Mala Suerte uses a surviving carrier without its grant as the played-card pool. The card granting 3 AP is verified against its resource receipt (one test method passed).
- Mala Suerte rejects an empty played-card pool without mutation, and recovers a genuinely played card. It discards the other hand and leaves the hand counter at 2, including its native base level (one method passed).
- Pulga Arcito normal/critical and Pulgacion on/off execute against a genuinely injured ally. Native level-200 stored fleas are 26 normal or 32 critical. Immediate healing is mastery-scaled and cannot be equated directly to stored flea levels. State variant plus flea gate: five methods passed.
- Real lethal Lengua Raspadora (2065) and ¡Zarpas Quietas! (2072) commit against an initially adjacent 1-HP enemy, consume AP, and preserve the original source snapshot. Follow-up healing does not roll back lethal damage (one method passed).
- Actual Pulga Arcito with Pulgacion heals again at the recipient's real end/regeneration boundary and spreads fleas to a nearby ally, excluding the enemy. Actual Felintuicion creates owned area1798 and expires through real turns without a dangling retained manager. The final lifecycle module passed2/2; it uses owned spell UIDs and does not inject state or area records.

## Source-backed corrections

`combat_state_variants.py` now recognizes multiple uniquely matched normal/critical group pairs, including family 999. The previous exactly-two/family-330 policy treated state 7931's four roots as ALL: normal and critical flea payloads both ran, yielding stored level 58 and identical normal/critical healing. The extension preserves explicit native selective masks and leaves unmatched or ambiguous roots in ALL mode. This is a documented server policy extension; the missing original native `fyW.ox` caller is not claimed recovered.

Upgraded Miaumiau 5535 is selected by card 7944 only at Racha 100, through criterion 374158. Passive 7955 alone still summons profile 1482. An actual cast/turn sequence with En Racha reached100 (not the disabled Dado Gatuno +50 leaves) and the card selected 5535 with owned ability 7986. Native removal 374159 consumes 100, then En Racha listener 359078/359822 adds 7 for the successful card, so the final Racha value is 7. The source-corrected final assertion passed in a fresh run.

## Still requiring semantic qualification

- Baseline Miaumiau5231 targets an enemy: native selector361104 includes enemy bit8. Effect361105 marks that recipient,361106 selects the original controller and361108 checks its ring1..3 before361109 supplies enemy resistance debuff state7957 level120. Actual5231 enemy debuff120 and upgraded7986 enemy debuff200 both passed. Allied targets correctly reject eligibility.
- Actual NPC7962 death of profile1482 now passes KO/QI-release and source isolation. Actual2079 recovery of the played7944 card followed by native cooldown-respecting resummoning passed with a fresh owned QI slot; upgraded5535 and3789 retirement remain separate checks. Profile3789 has an authoritatively empty ability book.
- Additional flea propagation chains, unavailable-recipient cases and area1798 occupant entry/exit reactions beyond the verified regeneration/ownership/expiry scenarios.
- All twenty passive initialization branches pass; the detailed semantic matrix records each actual positive/negative result. Six-card Siete Fetiche actual counter/threshold execution passed. Positive DODGE/FEROCITY branches and untested combinations remain explicitly bounded; disabled dice parents must not be enabled to manufacture an effect.
- Client animation, disconnect/reconnect, PvP, dungeon progression and full manual acceptance remain outside these local semantic tests.

No claim of complete functional acceptance is made from inventory or initialization alone.

Additional terminal evidence: passive7956 actual incoming damage crossing/no-crossing passed. Native innate6892 root359218 end-turn1002→369987 supplies the common20 Racha; the passive crossing contributes an additional50, producing70/20/20 across the three scenarios.

Additional terminal passive evidence: El Universo8000 replaces the verified ordinary7-point card contribution with integer3. Tarot Felino7955 swaps positions and applies property11 after an actual enemy-targeted held-card cast; matched no-passive control does neither. Racha Sanadora7954 awards5 per actual healed recipient (three recipients give15 over control), then real1037 removes Racha. See the combined semantic matrix and remaining-passive qualification report for source and control details.

Final focused results: six-card7999 counter/threshold PASS1/1; actual cast/turn Racha100→profile5535→owned7986 enemy debuff200 PASS1/1; actual NPC KO→QI release→owned2079 recovery→cooldown-respecting fresh resummon PASS1/1; baseline5231 enemy debuff120 PASS1/1. These are separate scenarios, not inferred from registration.
