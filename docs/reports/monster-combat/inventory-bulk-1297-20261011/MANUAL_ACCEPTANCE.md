# Manual acceptance: automatic monster activation

Run after the deployment receipt passes.

1. Log in using your normal character and deck. Use a familiar class attack and confirm its normal AP/WP costs, damage and states.
2. Run each command below as a separate fight. Engage, allow three monster turns, vary your distance, and attack using the normal class deck. Expect valid occupied targets, legal resource costs and movement, visible spell effects, and continued player turns without stalls.
   - `!mob 1482 1 1` — Miaumiau negro.
   - `!mob 2202 50 1` — Papá Nowel.
   - `!mob 1339 100 1` — Gelatina de frambuesa.
   - `!mob 3516 150 1` — Krosmoglob de seguridad.
   - `!mob 3906 200 1` — Magicarpa.
3. Finish each fight normally or use `!winfight`. Expect return to the world without disconnecting, then a new fight with fresh resources and no leaked states.
4. Run `!mob 6 4 2`. Baby Tofus should still attack and retreat when legal, and PM-loss border glyphs should affect routing. Use the established Huppermage, Sram and Feca decks during the complete sequence to confirm their normal mechanics.

This is a representative system acceptance test, not a claim of visual review for every monster. Deferred references remain disabled and retain their blocker evidence in the inventory.
