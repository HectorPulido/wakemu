# Aniripsa complete manual acceptance

Run after a complete shared world build has been deployed. Automated results
and client acceptance are separate: this document does not claim a live pass.

## Preparation

1. Use an Aniripsa and an allied player in the same group. On the Aniripsa,
   enter `!nivel 250` outside combat to unlock every active and passive.
2. Save the existing build. Create temporary legal builds and rotate active
   spells/passives between fights; do not exceed the actual deck slots.
3. Start PvP first, then PvM with at least two enemies. For resurrection, keep
   the Aniripsa and a third allied fighter alive when the test ally is defeated.
4. Record combat ID/time, build/passives, spell, recipient and before/after
   PdV, PA, PM, PW, states. Compare amounts with the current client tooltip,
   accounting for resistances, masteries, critical hits and healing resistance.

## Every active and both modes

Rotate these exact owned actions through legal decks:

| System | Actions |
| --- | --- |
| Water/healing | Palabra Sanadora779, Revitalización780, Reconstitución625, Juventud782, Vínculo de Amistad781 |
| Fire/marks | Anatomía630, Fuego Guardián638, Explosana645, Corrosana636, Llama Purificadora1534 |
| Air | Infusión1532, Vivificación1533, Prohibición1538, Cura Alternativa1539, Psicosis1540, Aletargamiento1541, Matraz Infectado1542 |
| Utility | Colimador623, Desfase627, Anisurrección1535, Fuente salvadora7985 |

For each action, perform the following with its legal range/target conditions:

1. Cast on a wounded ally, self and an enemy where the tooltip permits it.
   Healing must reach the intended recipient, stay within capacity and never
   damage an ally through the normal healing branch. Enemy damage must name
   the correct victim. Full-health healing must not overflow.
2. Repeat with Contra Natura active, then deactivate it on a later turn.
   Only the native mode-dependent branches change. Contra Natura is naturally
   granted from level6, costs2PW and cannot be toggled twice in one turn.
3. Check critical and normal casts, exact once-only payment, per-target/turn
   limits, buff amounts/durations and temporary cast-marker consumption.
4. Try an invalid range, blocked LOS, occupied summon cell and unavailable
   recipient. No resources, states or turn progression may change on rejection.
5. End turns, move and reconnect once. Temporary states must use their actual
   expiry boundary; no repeated grant, extra effect or missing action book.

Juventud must install its scaled carrier; it is not an immediate direct heal.
Vínculo must reject enemies and an already linked target, charge2PA/1PW once,
and apply the link to the selected ally. Check its damage-triggered buffs and
cleanup separately from its initial state installation.

## Cunejo, all four profiles

1. Without Súper Cunejo II or Contra Natura, summon Cunejo182 on a free cell.
2. Equip Súper Cunejo II7991 and repeat: exactly one living Súper Cunejo1775
   must appear, with no invisible base Cunejo blocking its cell or summon limit.
3. Repeat both builds with Contra Natura: Darkcunejo5528 and
   Súperdarkcunejo5533 respectively. Naturaleza Muerta5455 changes separate
   cost/death behavior; it does not select the dark profile by itself.
4. Play every granted summon action. Check owner/team, healing recipient,
   dark debuff, push, swap, sacrificed summon, PA/PM and target identity.
5. Kill or sacrifice it, then summon again on the former cell. No stale QI
   blocker, duplicate timeline portrait, wrong death animation or lost turn.
6. Reconnect the owner during a summon turn and finish the fight normally.
   All summon books, markers and combat-only ownership must be cleared.

With Naturaleza Muerta5455, stand in the area left by a real Cunejo death and
advance several actual turns. Check light-element healing, the3918 guard and
Propagador's level cap without a frozen turn. Kill a newly summoned Cunejo:
the new death area must replace the old owned1814 area. Its current native
prototype has no timed removal mask; do not expect an invented fixed expiry.

## Marks, deferred effects and areas

1. Apply each mark to its legal recipient: do not assume all marks target
   enemies. Test allied Ting and Breo carriers with their qualifying damage
   or healing event; test enemy/death marks with the Aniripsa, an ally and a
   Cunejo as killers in separate attempts. Check the tooltip's recipient,
   area and one reaction.
2. Explosana's marked victim must explode on nearby eligible enemies exactly
   once. A dead carrier retained by the native corpse guard is not a new hit.
3. Equip Retraso5451. A qualifying heal is halved, the deferred amount is
   recorded in3899, and actual voluntary movement consumes/heals that amount.
   Do not expect Retraso to halve an ordinary incoming damage hit.
4. Cast Fuente salvadora. Check its area, owner, ally/enemy conditions,
   entry/exit effects and expiry; repeat with two nearby recipients.
5. Test a reaction that kills the last enemy. The fight must finish once,
   with no waiting ACK, duplicate reward or frozen next turn.

## Resurrection and second death

1. Let a real enemy defeat the allied player while two allies remain alive.
2. Cast Anisurrección1535 on that eligible allied corpse. It must restore PdV,
   the character model and timeline participation, and apply Convaleciente1144.
3. On the restored fighter's legitimate turn, move and cast an available action.
   Other fighters must keep their correct turn order and resource bars.
4. Attempt another resurrection where Convaleciente/property66 forbids it:
   reject with no payment or state changes.
5. Defeat the restored fighter again. The correct actor must receive the new
   death/removal animation once; no suppression from its first death.
6. Reconnect and surrender in separate attempts. Both clients must leave the
   fight cleanly; no stale portraits, spells, swords or disconnected client.

## All passive builds

Rotate every passive at its unlocked level and trigger its tooltip condition:
628,644,1415,1536,1537,5451,5453,5454,5455,5463,7987,7990,7991,7992,
7993,7994,7995,7996,7997,7998. Compare against the same build without that
passive. Check positive activation and a negative control, exact numerical
change, stack cap, duration, consumption and combinations permitted by slots.

Pay particular attention to self versus allied healing (Paroxismo Vital),
mark application (Marcador de Serie), initial health (Todos para Mí), zero and
positive tackle (Elixir de Viento), mode-dependent Transgresión/Ambivalencia,
mark conversion and Cunejo death/aura behavior. A passive's marker being
installed alone does not prove its dependent mechanics.

For Ambivalencia7998, test both targeted Contra Natura branches. Targeting an
ally improves the caster's subsequent healing. Targeting an enemy subscribes
to qualifying direct healing: heal self or an ally afterward and check the
marked enemy's secondary damage. A direct damage follow-up alone is a negative
control for that healing reaction.

## Shared multiplayer and dungeon finish

Complete a two-client PvP and a two-client PvM: both Ready buttons, first turn,
movement and spells, owner reconnect, surrender and normal victory. Complete
the next dungeon-room transition as well. Both clients must show the same
fighters and active turn; the correct personal books and PdV must remain.
After leaving, no combat UI or group swords may remain, the next mob must
exist, and neither client may disconnect. Monitor map-return duplicate
interactive-object errors as an independent previously observed issue.
