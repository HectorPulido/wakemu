# Remaining low-level cohort: manual acceptance

Run this checklist only after the matching deployment receipt reports healthy world and AI. It complements automatic full-book validation; encounter-dependent spells retain their native prerequisites.

1. Reconnect the client and select a normal character with its existing deck. Run `!exitdungeon`, then `!tp 1134 -8 -7 -1`.
2. Run `!mob 6 4 2`, engage, and allow three enemy turns. Baby Tofus should move, attack and retreat when legal. PM-loss border glyphs should influence routing. Finish normally or run `!winfight`.
3. Run the commands below as separate fights. Engage, allow three enemy turns at different distances, and use an ordinary class attack. Expect legal costs and targets, visible effects, and the next player turn without a stall. Use `!winfight` between fights.

| Purpose | Command | Expected observation |
| --- | --- | --- |
| Basic attack | `!mob 1710 3 1` | Rata de Astrub moves and attacks. |
| Role actor books | `!mob 2199 1 2`, then separate fights with references2203,2204,2227 | Attacks and support actions have real recipients; conditional actions may be skipped. |
| Healing | `!mob 2617 4 2` | Injure one Miaumiau blanco without killing it. Its ally may heal the wounded monster when range and resources permit; no healing animation aimed at an empty cell. |
| Plant summoning | `!mob 2601 4 1` | Real summoned actors appear; fight turns continue. |
| Shrederches summoning | `!mob 2603 5 1` | Real summoned actors appear and retain their own native books. |
| Larva summoning | `!mob 2819 5 1` | Summoned larvae take their own turns and can damage a target. |
| Constructor and state handling | `!mob 3510 8 1`, then `!mob 5708 1 1` separately | Initial states and subsequent actions work without placement or turn stalls. |
| Native area geometry | `!mob 4012 5 1` | Odalach attacks valid recipients in its native geometry. |
| Other ordinary book | `!mob 5698 1 1` | Arakna menor hambrienta acts and returns the turn. |
| Resource-gated area book | `!mob 5710 1 1` | Other owned actions remain available. Its MP-cost area action requires sufficient actual MP; the automatic proof uses a real Enutrof buff. |

Use `!mob 2203 1 2`, `!mob 2204 1 2` and `!mob 2227 1 2` for the separate role actor fights. These commands do not create artificial resources or encounter prerequisites.

4. Conditional actors can also be spawned with `!mob 2778 5 1`, `!mob 3907 1 1` and `!mob 5361 1 1`. Do not expect their encounter-only action in an ordinary duel: the complete automatic proof creates the actual cursed opponent plus a class AP buff, opposing Seed, or allied Milkar respectively. Those dependencies are data imports, not general activation of high-level monsters.
5. Exercise existing Huppermage, Sram and Feca mechanics using their normal decks, including a glyph and a summon. Expect their established costs, damage, states and turn progression. Finish one fight and start another to check that effects do not leak.
6. Report a failure with character/class, monster reference, spell, turn, position and observed result. Do not spawn the seven trainer/racing exceptions or the five unresolved encounter/lifecycle references as an acceptance test of ordinary combat.

Operator verification:

```sh
docker compose ps
curl --fail http://127.0.0.1:18081/health
docker compose logs --since 15m world ai
```

Expect healthy world/AI and no new combat tracebacks. Health alone does not certify a spell.
