# Manual acceptance plan: automatic monster activation

Status: prepared offline. Run only after complete current-source validation, catalog activation and deployment verification pass. These commands do not prove the candidates are enabled now.

1. Log in with the usual character and class deck. Confirm one familiar attack has its expected cost, damage and states.
2. Run each command below as a separate fight. Use a suitable character level for high-level monsters. Engage, allow three complete monster turns, change distance and cast normal class spells. Expect legal targets, attacks with visible effects, movement and continued player turns without stalls.

- `!mob 1482 1 1` — Miaumiau negro (native actor level 1).
- `!mob 2202 50 1` — Papá Nowel (native actor level 50).
- `!mob 1339 100 1` — Gelatina de frambuesa (native actor level 100).
- `!mob 3516 150 1` — Krosmoglob de seguridad (native actor level 150).
- `!mob 3906 200 1` — Magicarpa (native actor level 200).

3. Finish each fight normally, then repeat one using `!winfight`. Expect return to the world without disconnecting, followed by a new fight with fresh resources and no leaked states.
4. Run `!mob 6 4 2` for the existing Baby Tofu regression. Expect attacks followed by retreat when legal; avoid unnecessary entry into PM-loss scenario glyphs. Place a summon or beacon and observe target selection.
5. Repeat the complete sequence using established Huppermage, Sram and Feca decks. Confirm their states, glyphs, summons and resource costs still behave normally.

If a failure occurs, record the exact monster reference, actor level, class, spell and turn, and approximate time for log correlation. This is representative system acceptance, not visual certification of every monster. The exact690 deferred references remain disabled.
