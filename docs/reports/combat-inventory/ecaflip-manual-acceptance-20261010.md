# Ecaflip complete manual acceptance battery

This is a prepared acceptance procedure, not a record of a successful client run. Execute after the complete shared server build has passed its automatic gates. Keep the Cra and Iop available for the shared combat regression at the end.

## Preparation

1. Select a Zurcarak/Ecaflip character (native breed6). Outside combat, enter exactly `!nivel 200` if the character is below200; `!level 200` is the existing alias. This command raises levels only and requires the account's existing command permission. Edit decks through the normal client UI; no invented deck-console command is required.
2. Start unequipped and without optional passives. Record current/max HP, elemental mastery, AP/MP/WP, critical chance and combat resistance. Healing tests require injured allies with room to heal; damage tests require enemies that survive the sequence. State raw levels are not always equal to final damage or healing after mastery/resistance.
3. Form a party with another player. First run a friendly challenge, then PvM. For a reproducible single low-level enemy outside a dungeon, existing command `!mob 4 8 1` creates one native profile4 level8 creature. Use a normal durable encounter for multi-turn and high-Racha cases. Do not use a dying target to judge nonlethal follow-up effects.
4. Use deck A: Cara o Cruz2041, Dado Seis2042, Todo o Nada2043, Tres Cartas2044, Craps2045, Bufido2046, All In2047, Ruleta de Dados2048, Batalla2049, Dado Gatuno2050, Doble o Nada2060, Trébol7225.
5. Later switch outside combat to deck B: Felintuición2061, Lengua Raspadora2065, Laceraciones2066, Pulga Arcito2067, ¡Zarpas Quietas!2072, Pulguita2073, Topkaj2075, Ficha de Vida2078, Mala Suerte2079, Trébol7225, Dado Gatuno2050, Cara o Cruz2041.

## Base spells and map rules

1. For every deck-A and deck-B spell, cast at least one legal target matching its tooltip: enemy, injured ally or empty cell. Check actual HP/armor/state/position change and exact tooltip resource costs; zero-PW/AP conditions must reject without charging or changing other actors.
2. Repeat one damage spell at normal and critical chance conditions. A critical must use its own native branch once. Dice/random outcomes may differ across casts; record the face/outcome and compare that branch's tooltip. Repeated identical seeded results in an automatic fixture are not a promise of repeated live random results.
3. Try targets out of range, behind a real wall, on an occupied summon cell, and behind a monster that has just died. A legal corpse-free line must become usable. Illegal targeting must reject locally without consuming resources, freezing turns, disconnecting or removing the character.
4. Kill a weak enemy with Lengua Raspadora2065 and ¡Zarpas Quietas!2072 from adjacent legal cells. The lethal damage must commit even when a later heal has no living recipient; only that enemy dies, the attacker stays connected, and the next turn advances.

## Tarot, hand ownership and played-card recovery

1. Enter combat and inspect the three actual granted cards. They must be distinct, owned by this Zurcarak and usable only while their grants survive. Native card IDs are7938–7950; use the client-displayed names rather than assumed names absent from the current localization catalog.
2. Play one legal card. Its grant must disappear, its effects/costs must occur once, and other players' grants remain intact. A surviving hidden/native card carrier is intentional and does not mean a playable duplicate remains.
3. Use Mala Suerte2079 after playing that card. It must recover a genuinely played card and replace the other old hand, rather than duplicating all old cards. The native hand counter includes its base1: one recovered card gives counter2.
4. In a fresh combat, use Mala Suerte before playing any card. An empty played pool must reject without spending resources or damaging the combat session.
5. Equip Desventura2068, Desdicha2080 and Destino de Zurcarák5250, then repeat across combats until each optional card is drawn. Across all draws, exercise all thirteen cards. The AP-producing card7947 adds3AP in addition to paying its ordinary costs.

## Racha and summons

1. Equip En Racha2076 and cast Dado Gatuno2050 on a durable legal target. Observe actual Racha contribution and its100 cap. Native dormant dice+50 branches are explicitly disabled and are not expected gameplay. Equip El Universo8000 and play an ordinary card: the verified native7-point card callback is replaced by integer3 through the half-level first-success branch, giving3 before later effects/caps.
2. Save the actually drawn Miaumiau card7944. Below Racha100 it creates profile1482 with action5231. Tarot Felino7955 alone must not upgrade it.
3. Reach Racha100 through actual casts and use card7944. It must create upgraded profile5535 with action7986. Its native branch consumes100; the ordinary successful-card reaction subsequently adds7 in the tested En Racha context. A final7 therefore is not a failed consumption.
4. Put an enemy within1–3 cells of the original controller and in legal reach of the Miaumiau. On its actual turn, use5231 against that enemy. This is an **enemy resistance debuff**, state7957 `Husmiau - Malus de Resistencia`, native level120; upgraded7986 supplies200. The original controller/allied players must not receive an invented healing buff. An enemy beyond the controller's ring is a negative control.
5. Let an actual enemy kill the summon. Its cell must become free in pathfinding/line of sight and a later legal summon must receive a fresh identity/slot. Damage, death animation and timeline must reference that summon only. Repeat for both Miaumiau profiles and the card7941 profile3789; the latter has an authoritatively empty action book and must not be given fabricated actions.

## Fleas, healing and area lifecycle

1. Injure an ally, use Pulga Arcito2067 without Pulgación2062, and record healing. Equip Pulgación and repeat with the same characteristics: immediate healing is split and native fleas3697 are stored. At level200 the verified raw flea levels are26 normal and32 critical; do not equate those raw levels directly with mastery-scaled HP gain.
2. Advance real turns while another injured ally stands in a legal propagation context. Fleas must heal and propagate only to qualifying recipients, expire/consume on the native schedule, and stop producing effects afterward. Repeat with the original carrier killed before the callback.
3. Use Felintuición2061 in its legal context, then enter/leave the resulting area1798 and advance real turns until its native expiry. Effects must apply only to qualifying occupants and no stale area/owner pointer may survive removal. Repeat with the source actor removed.

## Passive system pass

Rotate optional passives outside combat. Do not equip mutually incompatible setups merely to save one fight. The exact source branches and remaining automatic verification status are in `ecaflip-passive-semantic-matrix-20261010.md`.

| Setup | Action and expected observation |
|---|---|
| Tarot Suertudo2059 | Compare actual dice faces and successful-card Racha contribution against its tooltip; values must come from the face-specific branch. |
| Tarot Profético5246 | Play one card from each of its two tooltip groups; each group applies its corresponding effect exactly once. |
| Impacto Felino5249 | End your turn adjacent to an enemy: state7950 must appear with this passive. Repeat with a distant enemy and without the passive; those controls must not receive the state. |
| Trampas5251 | Start with the native one-card hand, play it, then check its postcast state/cadence without duplicating cards. |
| Racha Sanadora7954 | Perform actual qualifying healing: each eligible recipient callback adds5 Racha (three actual2067 recipients give15 over matched no-passive control). Advance the actual1037 turn boundary and check Racha removal. |
| Tarot Felino7955 | Play an enemy-targeted held card on an eligible uncarried recipient within1–6: positions swap and property11 applies. Without the passive neither occurs; repeat outside the distance/ineligible control. |
| La Fortuna Sonríe a los Audaces7956 | Receive damage that crosses from at/above50% to below50% HP: the extra reward is50 Racha over the same incoming-damage baseline. Starting already below50% must not award that crossing bonus. |
| Cruz, Gano7957 | Play a card at Racha100 and compare with below100; verify its qualifying modifier. Separately start a fight with positive DODGE from legal equipment/aptitudes and compare passive-off/on: the start response removes the native DODGE-derived amount. |
| Dados Generosos7958 | Use a legal build with native characteristic9 above100, then take a legal step. Compare passive-off/on: GoodStar state7999 derives the excess above100; the owner receives half as damage bonus without7958, or healing bonus with7958 (verified114→state14→bonus7). This point-target branch requires no nearby ally. The native disabled marker remains inactive; state7999 is not Seven passive7999. |
| Felino Supremo7959 | The current source installs marker359898 but no downstream consumer was found. Record any client tooltip claim for reconciliation; do not assume an invented numeric effect. |
| Black Jack7960 | Move voluntarily with card-weight sums on both sides of20; the <=20 branch grants armor equal to10%maxHP without state6624; the >20 fallback gives state6624level5. |
| Triunfos Periódicos7961 | Advance actual odd/even table turns and inspect permitted card draws; no stale hand from the previous parity may bypass the draw contract. |
| Siete Fetiche7999 | Play six actual cards while Racha stays below100 beforehand. Counter8047 advances for the first five; the sixth grants100 Racha through the native threshold. Individual cards may add other Racha and must not be mistaken for this bonus. |
| El Universo8000 | Compare the same die/card callback with and without the passive, including the100 cap. |
| Racha de Cartas8001 | Advance a turn retaining cards, then compare with cards already played; only surviving owned grants contribute their signed15-point branches; cards7939,7941,7944,7946,7948,7949 subtract15 and the other eligible cards add15. |

Desventura2068, Desdicha2080 and Destino de Zurcarák5250 are covered by the optional-card section; En Racha2076 and Pulgación2062 by their dedicated sections. This accounts for all twenty class passives.

## Shared combat acceptance

1. Run PvP with both players ready; both clients must show the same roster, first turn, AP/MP/WP and owned bars. Move/cast on both first turns.
2. Run a multi-player PvM fight, kill one enemy, reconnect one player, finish normally, then repeat surrender. Both clients must leave combat coherently; no player is disconnected and no stale swords, empty action bar or frozen timer remain.
3. Finish a dungeon room and enter the next with both players connected. The next group's monsters and join markers must appear; a reconnect must not be required to advance.
4. Run a short Cra beacon/Desbalizaje and Iop combo regression. Existing class grants, costs, death identity and turn behavior must remain intact.
5. For any failure record character, spell/card, active passives, turn, target cell, AP/MP/WP, visible message and time. Preserve the combat when possible so logs can be correlated. A rejected illegal action alone is not a failed acceptance; mutation or broken session after the rejection is.
