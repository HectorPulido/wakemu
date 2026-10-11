# Necromonde and Super-Villains manual review — V1

Both routes have complete source-only one-encounter candidates. Neither needs invented preliminary ordinary monsters, repeated bosses, or a boss rush. No runtime configuration or client file was changed.

## Super-Villains, native definition 79

[The dungeon guide](https://wakfu.guide/donjons/96-110/#repaire-des-super-vilains) explicitly describes one encounter against four named bosses. The installed pool matches those four species: Merkator 2708, Kralaman 2709, Megathon 2710 and Lardevil 2714. The candidate contains exactly one of each, all in the same combat.

Map 704 has a nine-cell entrance/exit lobby, three native separating doors 33319/33320/33321, and a 257-cell arena. Native arrival is `[3,0,0]`; exit source 20297 returns to map 709 at `[-4,4,0]`. All three doors remain present in configuration and open upon entry under an explicit same-stage local access policy. No combat is placed in the lobby. The directed engagement path crosses the real doorway into the arena and the exit remains reachable afterward.

Unverified mechanics: Merkator scaling with dead allies and ally boosts; Megathon imprisonment bubbles and counterattack posture; Kralaman rear teleport/debuff; Lardevil death triggers and charge glyphs. These are encounter-mechanics gaps, not unresolved map/roster blockers. The candidate must not be described as mechanically faithful until those systems are verified.

## Necromonde, native definition 196

[Ankama's official 1.84 trailer](https://www.youtube.com/watch?v=xDRZuyI6Drk) identifies Toross Mordal and the three-player dungeon. Installed definition 196 identifies map 1403 and a singleton native species pool, Toross 5589. One initial Toross is an explicit local encounter quantity, not an inferred ordinary-monster roster.

The 36-cell entrance/exit lobby is separated from the 645-cell arena by doors 34835/34836/34837/34838/34840. Native arrival is `[19,1,0]`; exit source 34833 returns to map 1365 at `[-120,25,-45]`. All five doors open upon entry with the same-stage policy; the boss is placed strictly beyond the lobby in the actual arena. No fabricated preliminary fight is introduced.

The optional native stele 34852 is retained as map content but its combat modifiers are not asserted implemented. Toross scripted phases/effects require combat-specific verification. The quest requirement remains bypassed under the user's all-open dungeon policy.

## Configuration and verification

Versioned configurations are in `reviewed-boss-lobby-arenas-v1/`; the report `REVIEWED-BOSS-LOBBY-ARENAS-20261010-V1.json` contains formation, engagement and exit witnesses plus evidence references. Both pass the existing six-player formation validator without changing combat geometry. Physical doors have source and destination stage 1, so they are natively published open before any victory. The one room contains the complete encounter, and normal completion settles it once.

`PYTHONPATH=server .runtime/local/verification-venv/bin/python -m unittest discover -s server/tests -p test_reviewed_boss_lobby_arenas.py`: 3/3 pass. Regressions verify initial gate opening, exact singleton boss quantities, no fabricated preliminary encounter, arena-only enemy placement and reachable engagement/exit evidence. PostgreSQL lifecycle gate is delegated to Luna before activation.

Manual acceptance after activation: enter with the full party; confirm the lobby doorway opens immediately; walk into the arena and engage the complete boss group; surrender and reenter once; complete the encounter; return through the lobby doorway and use the native exit. Super-Villains must have four distinct bosses simultaneously, and Necromonde one Toross. Boss-specific phases/effects are a separate acceptance scope.
