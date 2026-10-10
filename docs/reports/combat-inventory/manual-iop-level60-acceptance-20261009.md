# Iop level 60 whole-system manual acceptance

Character: Prueba Oficios, ID 4, native breed 8, persisted level 60, base maximum
HP 650, XP at the native level-60 threshold. Reconnect outside combat to load the
new book and resources. Deployment r52. User announces the start; correlate
fight ID, actor, spell reference, timestamp and actual effect diagnostics.

## Scope

The published catalog exposes 20 of 21 active spells and 12 of 20 Iop passives
at level 60. This is complete acceptance for the available level-60 system,
not certification of inaccessible higher-level abilities. Eleven active deck
slots and three passive slots are unlocked at this level. Higher-level coverage
includes Hora de Gloria and the remaining eight passives; retain them as pending.

## Decks and baseline

Deck A, no passives initially: Juicio, Fulgor, Carga, Jabs, Rafaga, Bofetada,
Casca, Sacudida, Focalizacion, Virtud, Postura. Granted Borrasca, Uppercut, Salto
and Estandarte are not active-deck slots.

Deck B: Super Puno Yopuka, Espada Celeste, Ira de Yopuka, Lanza Rocas,
Cuchillo de Carnicero, Estragos, Espada de Yopuka, Amplificacion, Duelo.

Use normal equipment and the same durable target. Record AP/MP/WP, effective
level, masteries, resistances, armor, orientation and critical branch before
comparing numbers. End a turn or start a fresh encounter between independent
combo cases; all actions within one combo must fit the same actual turn. Never
inject resources or states to force success. A target dying early invalidates
completion. Keep Cra present to exercise the shared fight and grant isolation.

## Combo pass

1. Borrasca twice, Uppercut, then Jabs: Preparation 3462 reaches level 20;
   next direct attack applies its modifier and consumes Preparation.
2. Repeat independently with Bofetada as the final attack; no retained-manager
   rejection, duplicate modifier, resource charge on a rejected cast or stuck turn.
3. Rafaga twice then Bofetada: completed push combo pushes two legal cells,
   respecting obstacles, occupied cells and the border; native cleanup follows.
4. Bofetada, Rafaga, Borrasca: additional damage branch completes, then cleans up.
5. With missing HP, Borrasca, Jabs, Jabs: native lifesteal heals within maximum HP.
6. Uppercut, Jabs, Uppercut, Rafaga: complete AP combo awards two AP, accounting
   separately for ordinary costs and the Motivation prerequisite.
7. Wrong order and end-turn interruption must not award a completed combo bonus.

## Distance, element and movement pass

Carga pre-cast distance one starts push combo; distance two starts additional
 damage combo. Uppercut next to a target, two legal retreat steps, then Carga
at distance three advances Combo PA from one to two within the same turn.

Juicio then a legal fire attack consumes the target's Juicio state and applies
its native 15 percent modifier; Juicio then Sacudida does not consume that fire
reaction. Element labels alone are not evidence of the reaction.

Exercise Salto and each displacement attack against clear paths, blocked paths,
occupied destinations and arena boundaries. Verify final position on both clients,
resource costs and return to idle animation. Test valid/invalid LOS and range;
a retired monster must not remain a normal blocking obstacle after actual QI
retirement. Record the exact cell and rejection if clients disagree.

Sacudida's armor reaction requires a real armored enemy: observe armor before
and after a legal triggering attack. A target without armor cannot validate it.

## Banner and passive pass

First verify Estandarte is granted without Portaestandarte: innate Guerrero
unlocks it from level 36. Place on a legal empty cell; account for the tooltip's
additional one AP. Inspect owner, HP, aura and allied elemental resistance.
Enter/leave aura, use the banner spell on an available aura cell to teleport,
then target the banner to remove it and recover the tooltip's two WP subject to
maximum. Test occupied cells and a second owner's summon as invalid targets
where native ownership requires it. Repeat creation/removal.

Outside combat equip Portaestandarte 8422. Repeat the above and its SELF variant:
stationary state 8965 appears; legal voluntary movement removes that state.
Forced movement and death are distinct native triggers, not substitutes.

At level 60 rotate the twelve available Iop passives individually before
combinations: Virilidad, Compulsión, Autoridad, Duelista, Rey de la Colina,
Valentía, Precipitación, Minisalto, Impetuoso, Demostración, Conquista,
Portaestandarte. Use installed Spanish UI names as authoritative. Record each
passive tooltip, equipped deck, actual trigger, state/stat result and expiry;
merely owning an icon is not a passed activation. Higher-level eight remain pending.

## Remaining active spells and shared lifecycle

Rotate Deck B. For every available active, verify its installed tooltip's direct
and secondary effects, normal and observed critical behavior, AP/MP/WP costs,
range/LOS, occupied/empty targeting, turn limits, cooldown, state expiry and
cleanup. Exercise Focalizacion, Virtud, Postura, Amplificacion and Duelo in their
actual prerequisite scenarios; do not count a legal rejection as effect success.

With Cra in the same fight: use beacons, alternate both player and NPC turns,
confirm no private spellbook crossover. Disconnect/reconnect each owner separately
while the other remains; verify roster, grants, states, resources and turn.
Withdraw one owner and continue with the other. Complete victory, inspect rewards,
world interfaces and dungeon progression; repeat surrender on a fresh fight.
A last-owner abort must restore a retryable encounter, never duplicate rewards or
silently advance the dungeon.

## Evidence handling

The server logs provide numerical modifiers, selected effects and rejected casts;
manual observation provides rendering, animations, spell availability and turn
usability. Neither substitutes for the other. Record observed passes, failures
and cases not executable at level 60 separately.
