# Iop high-risk whole-system acceptance — 2026-10-08

Run after the shared event/context repairs are automatically validated and deployed. This is a prepared test, not a passed acceptance record. Record deployed release, character, level, equipment, deck, AP/MP/WP and target characteristics. Use a durable target that survives the complete sequence; a target dying before the last cast invalidates the combo test.

## Setup

1. Select a Yopuka character (native breed8). Outside combat, enter `!nivel 200` in the existing chat console if its level is below200. The existing command only raises levels and is subject to account command permissions; do not use it on a higher-level character. Existing `!level` is an alias. No deck-console command was established: edit the normal deck in the client.
2. The test character is prepared at level200 by the integration agent; `!nivel 200` is optional only if a lower level is observed. Set this12-active deck for the high-risk pass: Juicio4776, Fulgor4775, Carga4783, Sacudida4780, Lanza Rocas4781, Jabs4785, Ráfaga4786, Bofetada4787, Casca4788, Focalización4790, Virtud4791, Postura4792. Start with no passives for a clean baseline; repeat the relevant cases with passives in a later pass.
3. Confirm granted Borrasca8402, Uppercut8403, Salto8404 and Estandarte de Valentía8405 are available under native prerequisites. Start each isolated case in a fresh fight/turn with no residual combo state. Keep enough native resources to finish the sequence; do not inject AP, states or damage results to bypass legality.

## Exact native combo sequences

The following sequences come from Guerrero7553's1024 listener397553, its active-ID branches397554–397558 and their ordered state-transition children397665–397669. These are native state transitions, not guessed rotations. All actions must occur in the same turn; enemy death or a different intervening action can invalidate the sequence.

| System | Cast sequence | Expected intermediate progression | Expected final native outcome |
|---|---|---|---|
| Push | Ráfaga → Ráfaga → Bofetada | Combo de Empuje3445:1→2→3 | Final push branch activates, pushes2 cells subject to actual collision/terrain; combo marker removed by its native cleanup. |
| Additional damage | Bofetada → Ráfaga → Borrasca | Combo de Daños Adicionales3447:1→2→3 | Native extra-damage children execute; normal Borrasca damage alone is insufficient. Final combo marker cleanup occurs. |
| Lifesteal | Borrasca → Jabs → Jabs | Combo de Robo de Vida3444:1→2→3 | Native bonus attack/lifesteal branches execute. Test with missing caster HP; verify healing and cost, not merely damage. Cleanup removes the combo marker. |
| Preparation | Borrasca → Borrasca → Uppercut | Combo de Preparación3446:1→2→3 | Applies Preparación3462 at +20 native levels, then cleans the combo marker. |
| AP | Uppercut → Jabs → Uppercut → Ráfaga | Combo de PA3448:1→2→3→4 | Applies Motivación3463 at level1, whose native family31 child151236 adds2AP; verify against total ordinary cast costs. Recipient must lack3463 and not be carried. Cleanup removes the combo marker. |

Final-stage markers may be transient because their native children remove them. Record intermediate visible levels and final effect; do not require the completed marker to persist. Also perform a wrong-order sequence and an end-turn interruption: neither may award the completed combo bonus.

## Three corrected shared paths

**Carga distance context.** Use fresh states for each test, with a valid enemy exactly1,2 or3 native cells from the caster before the cast. Keep the target legal under actual range/LOS rules.

- Distance1: Carga must take397554's branch and start Combo de Empuje3445 at level1.
- Distance2: Carga must take397555's branch and start Combo de Daños Adicionales3447 at level1.
- Distance3: first cast Uppercut to establish Combo de PA3448 at level1, then move legally two cells away, spending2MP, and cast Carga on the target now3 cells away.397556/397587 must advance3448 to level2. With no prior3448, this branch is not required to create it.

The distance is the validated pre-cast caster/target distance, not the caster's SELF carrier distance0 or the post-displacement distance. Capture each observed marker, AP/MP cost and movement.

**Juicio triggering identity.** Cast Juicio to obtain state8912. Then cast a legal fire spell such as Fulgor. The native first criterion is `GetTriggeringEffectCasterIsSameAsCaster() and IsActivatedByElement(1)`: **element1 is FIRE**, confirmed by the current published element registry. Do not use an earth attack as the positive case. Verify original397246→397247/397773→397248 activation and native8912 cleanup. Repeat separately with the8402/8403+8916 alternative; that alternate path must not mask failure of the fire path.

**Preparación consumption.** Complete Borrasca→Borrasca→Uppercut and observe Preparación3462+20. Cast Jabs4785 as the next direct attack. Verify its actual family5 modifier+20 and3462 removal through151188;4785 is Jabs, while Carga is4783. Compare with an otherwise identical no-Preparation attack on the same target, element, orientation and critical branch. The producer's exact phase/rounding must follow the completed automated contract; this test does not invent a universal +20% final-HP formula.

## Banner and armor reactions

Estandarte de Valentía8405 is a granted action, not an active-deck slot. For the validated Portaestandarte case, equip passive8422 Portaestandarte, then cast the granted8405 on SELF. Verify state8965 appears and legal voluntary movement removes it through1005. In a separate native configuration, place the standard on a legal cell. Verify native profile3793 owner, placement, intended duration and area; repeat with Destino8413 to cover its native area889/2042 selection. Verify entry/exit and removal, then recreate. The integration validation equips passive8422, uses the actual granted8405 UID on SELF, observes Portaestandarte8965 and then performs legal voluntary movement removing it through the implemented boundary. Repeat that visible creation/movement/removal sequence. The separate1010 KO/death branch remains a distinct acceptance case.

Sacudida4780 applies Sacudido8913. Its reaction requires an enemy source, at least1 target ARMOR, exclusions398521/398522 absent and a legal triggering value. Use a real armored target and compare armor changes before/after subsequent damage2. Test2236 separately using the existing source-backed ARMOR97 reduction notification route; it is not a missing producer. An unarmored Wonejo cannot prove this effect; absence of armor loss in that setup is not evidence of failure. No supported console command for injecting target armor was established in this review.

## Whole class completion

After high-risk cases, rotate legal decks to cover the remaining actives4777/4778/4779/4782/4784/4789/4793/4794/5130. For all21 actives record normal/critical outputs, resources, legal and invalid targeting, states and cleanup. Exercise all20 passives with their actual trigger scenarios and representative combinations; use the exhaustive inventory rather than counting400 markers as successful effects.

Reconnect during a fight with a partially completed combo, Preparación, grants and a banner active. State levels/resources/book/owner/turn must restore once, without duplicate bonuses. Continue the next action, finish a victory, return to the world and enter another fight; repeat surrender separately. Temporary effects must reset under native rules.

Fixed damage/healing numbers depend on effective level, native evaluated parameters, mastery/resistance, armor, orientation and critical outcome. The current review does not contain an equipped-character/target numerical fixture. Record those inputs and use the automated expected-value contract; do not invent fixed damage or bypass missing fixtures with arbitrary buffs.

## Current validated checkpoint

Root reports automatic actual-route validation of Juicio FIRE-positive/EARTH-negative, Carga distances1/2/3, Uppercut→legal2MP retreat→Carga3 advancing3448 level1→2, Borrasca×2→Uppercut producing3462 level20→Jabs4785 applying family5 modifier+20 and consuming3462, and actual-granted8405 creation of8965 followed by legitimate movement/removal. Complete r47 build/deployment is being handled by root; verify the loaded release before manual execution. This document does not independently claim deployment or100% class completion.

Events500 and1005 use explicit Wakemu server policies; the original server callers were not recovered. Actual-route results remain automatic evidence, not live-client acceptance. Consolidated final validation is pending the integration agent's report.
