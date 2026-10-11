# Pending low-level cohort: complete manual acceptance

Run after the matching deployment is marked healthy. These are native reference IDs, including quest/story actors; the list is not a list of ordinary wild species or a balance certification.

1. Reconnect the client, select an existing character with its normal deck, run `!exitdungeon`, then `!tp 1134 -8 -7 -1` in local chat.
2. Check existing AI behavior with `!mob 6 4 2`: let a Baby Tofu move, attack and retreat. A PM-loss border glyph must influence routing, and native PM loss must stop a route that becomes unaffordable. Finish the fight; use `!winfight` after observing the behavior if cleanup is needed.
3. Run each row below as a separate fight. Engage the spawned group, use a normal class spell, then allow three monster turns, both near and away from the monster when possible. Expect legal movement/casts, native animations/resource changes and a complete return to the player's turn. Support/conditional spells need not trigger on every turn. The offline receipt certifies every owned spell independently; the AI chooses its action according to the actual fight.
4. During the sequence, exercise an established Huppermage mechanic, Sram mechanic and Feca mechanic with their usual decks. Expect their existing costs, damage, states, summons and glyph behavior. Finish each fight (normal outcome or `!winfight` cleanup), then begin the next with fresh resources and no leaked effects.
5. Report any issue with character/class, monster reference, spell, turn and observed result. In particular, record any missing initial state, mismatched displayed stats, stalled turn or incorrect target.

| Monster | Command | Native owned spells |
|---|---|---|
| Jalatín de Haluín | `!mob 2090 1 1` | Baba Negra (800) |
| Alma de arquera sin descanso | `!mob 3264 8 1` | Flecha Fulminante (4820), Flecha Ardiente (4769) |
| Alma de general sin descanso | `!mob 3265 8 1` | Bofetada (4787), Jabs (4785) |
| Alma de lancera sin descanso | `!mob 3266 8 1` | Lengua Raspadora (2065), Pulguita (2073) |
| Alma agitada | `!mob 4013 4 1` | Stasificación (5710), Destello de Stasis (5711) |
| Jalató stasiado | `!mob 4014 3 1` | Mordedura Stasiada (5731) |
| Tofu corrupto | `!mob 4015 2 1` | Pico Stasiado (5732) |
| Abuelito de hielo | `!mob 5251 1 1` | Helasesinato (7138), Resbalielo (7139) |
| El último viajero | `!mob 5252 1 1` | Cronómetro Invertido (7150), Torrente del Tiempo Definitivo (7151) |
| Jinete | `!mob 5656 1 1` | Knighting (8288) |

The existing Wonejo, Miaumiau and Jalatín checks remain in [MANUAL_ACCEPTANCE.md](MANUAL_ACCEPTANCE.md). Pending references are listed in [PENDING_UNDER_10.csv](PENDING_UNDER_10.csv); their presence in the static coverage inventory does not authorize activation.

Operator checks after the sequence:

```sh
docker compose ps
curl --fail http://127.0.0.1:18081/health
docker compose logs --since 15m world ai
```

Expect healthy world/AI and no new combat exceptions. Health alone is not a spell execution test.
