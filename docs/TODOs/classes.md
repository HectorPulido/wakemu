# Class testing checklist

18 classes. Tick a class after its required **A** check passes; **B** is optional follow-up. Append failures or unavailable setups after **Notes:**; unavailable means NOT RUN, not PASS. This is a targeted manual checklist, not certification of every spell/passive. Spell names retain their Spanish client labels so they are easy to find.

## Preparation

Use unlocked actions, a durable enemy and enough space. Compare payment/effects with current tooltips, not fixed damage numbers. Start without optional passives unless specified. If needed, `!nivel 200` permanently raises a test character's level; reconnect afterward. With test-provider permission, `!mob 4 8 3` creates three weak Gobballs in exploration; they are unsuitable for sustained level-200 tests. Ordinary encounters also work.

Across these fights, check normal turns, correct spell bars/resources, movement and a playable return after victory. Report class, A/B, failing step and time; keep a stuck fight open if possible. Do not inject resources or states.

## Classes

- [ ] **Cra (Ocra)** — Beacons and ranged control. **Notes:**

  **A:** Place a fire beacon with an enemy in its reaction area; hit it with a fire attack. Expect one reaction against the eligible enemy. Later use "Desbalizaje": beacon disappears, its cell is released and turns continue.

  **B:** Use "Flecha Azotadora". Actual MP loss must survive the enemy's upcoming turn start, then expire after that turn; maximum MP stays unchanged.

- [ ] **Iop (Yopuka)** — Ordered combos and Preparation. **Notes:**

  **A:** With two clear cells behind a living target, use "Ráfaga" → "Ráfaga" → "Bofetada" in one turn. Expect the completed combo's two-cell push, normal costs and no stalled turn.

  **B:** Starting without Preparation, use "Borrasca" → "Borrasca" → "Uppercut" → "Jabs". Preparation rises by 20 before "Jabs", then is consumed.

- [ ] **Sacrier (Sacrógrito)** — Self-damage storage, healing and armor. **Notes:**

  **A:** Note HP/armor, use "Sangre a Sangre" beside a durable enemy, then "Corazón Sanguíneo" on yourself while storage is available. Expect enemy/self damage, then stored-damage restoration and native armor. Storage must be consumed rather than reused.

- [ ] **Eniripsa (Aniripsa)** — Healing summons and resurrection. **Notes:**

  **A:** Equip "Súper Cunejo II", stay outside "Contra Natura" and summon "Cunejo". Expect exactly one super summon with its own usable turn/bar. Let it die while combat continues; a later legal resummon must leave no blocked old cell or timeline slot.

  **B:** With other allies alive, use "Anisurrección" on a defeated ally. Its model/turn return and it can move/cast; a later death animates only that fighter once.

- [ ] **Osamodas** — Persistent captures and controlled creatures. **Notes:**

  **A:** If necessary, spawn `!mob 4 8 1`, cast "Invocación" on the living Gobball and defeat it: one capture. Reconnect to confirm persistence. In a new multi-enemy fight, summon it on a free cell and use its own movement/action on its turn. Capture remains after victory without duplication.

  **B:** Without "Trascendencia Dracónica", enter "Forma Dracónica" and use "Pesante" on yourself with an adjacent enemy. Expect area damage. Transform back and again when legal: both models update immediately.

- [ ] **Ouginak (Uginak)** — Prey ownership and "Wauwau" control. **Notes:**

  **A:** Mark an enemy with "Presa", summon "Wauwau" and play a legal move/action on its genuine turn. Expect the correct marked enemy, one summon/timeline slot and its own resources. Continue another owner turn without a bar swap or zero-second deadlock.

- [ ] **Masqueraider (Zobal)** — Controlled copy and cleanup. **Notes:**

  **A:** Use "Espíritu Enmascarado" and play its genuine turn. Let the copy die while combat continues, finish and start another fight. Expect appropriate copied spells, independent payment, correct death identity and no stale copy/bar/timeline entry. Respect recast restrictions.

- [ ] **Huppermage (Hipermago)** — Runes and Quadramental Breeze. **Notes:**

  **A:** Without optional passives, use "Flujo de Energía" then "Flecha de Luz" with enough Breeze. Expect a fire rune, damage and one advertised Breeze payment. End-turn recovery respects its maximum; no negative Breeze or substituted AP/MP accounting.

- [ ] **Sram** — Invisibility and enemy-triggered traps. **Notes:**

  **A:** Use "Invisibilidad", move two cells without attacking and end your turn. Enemies must not track the hidden location directly; incidental area hits remain legal. While still invisible next turn, attack with "Estafa": normal reveal, correct damage and continued control. Teammate translucency is expected.

  **B:** Place "Trampa de Repulsión" away from yourself with knockback space. Let an enemy enter during its AI turn. Enemy moves, Sram stays put and the exhausted trap disappears; crossing again causes no repeat activation or obstruction.

- [ ] **Feca** — Glyph timing and expiration. **Notes:**

  **A:** Without optional passives, cast "Fecalistófedes" on an empty cell beside an enemy; provide the glyph branch's costs (baseline 5 AP/2 WP). Expect a five-cell cross, no immediate creation/entry damage, one pulse at enemy turn start and removal at the next Feca turn start. No later ghost pulses.

- [ ] **Pandawa** — Carry, movement and throw. **Notes:**

  **A:** Use "Karcham" on an adjacent eligible, non-stabilized character, move a cell and "Chamrak" onto a free legal cell. Target follows then appears once; old occupancy/carry relation clear. A second throw without carrying rejects without payment and subsequent actions work.

- [ ] **Ecaflip (Zurcarák)** — Card grants and recovery. **Notes:**

  **A:** Inspect granted cards, play a legal card, then use "Mala Suerte" when legal. Recover a played card with no duplicate grants or changes to another player's hand. In a fresh fight, "Mala Suerte" before any card was played rejects without payment or a stalled turn.

- [ ] **Enutrof (Anutrof)** — Transformation and companion lifecycle. **Notes:**

  **A:** Note AP/MP, enter "Perfórserker", move and exit when legal. At the following owner turn, temporary exit-related MP consumption expires; normal movement and attacks work. Forms/resources remain coherent in both directions.

  **B:** Play a companion action, let it die while combat continues, then use "Llamada del Compañero" legally. Exactly one replacement gets a usable book/turn; old cell and portrait are released.

- [ ] **Foggernaut (Steamer)** — Microbots, transfers and turret resources. **Notes:**

  **A:** Place a "Microbot" and use "Transición" on an eligible ally: ally transfers, owner stays, normal payment (baseline 1 AP/1 WP). Later, with a turret beside another free "Microbot", target that "Microbot": only the existing turret transfers.

  **B:** With sufficient PS and WP below maximum, use "Sobretensión" on an owned turret (baseline 3 AP/2 PS). Turret disappears,2 WP restore up to maximum, and its cell/timeline slot are released.

- [ ] **Sadida** — Doll creation, targeting and owned resources. **Notes:**

  **A:** Place "Semilla" and cast "Vaporizar" on it. On the doll's genuine turn, use its ranged attack against an aligned enemy two or three cells away. Expect damage and doll AP payment, unchanged owner/other-player bars, then another normal round.

  **B:** Summon "La Vudul" and create a tree with "Semilla" → "Semilla" on the same seed. On Vudul's turn use action 8140 on the tree. Friendly armor only; record its recipient and verify absorption with a real hit.

- [ ] **Rogue (Tymador)** — Bomb improvement and final detonation. **Notes:**

  **A:** Place a bomb and summon "Tymobot" with a clear line to it. On the robot's turn use bomb improvement 6520. The same bomb improves; robot pays its own AP, owner's bar/resources stay correct and turns continue.

  **B:** Detonate an elemental bomb beside a durable enemy. Expect one explosion/damage application and removal. Later place another bomb on its old cell: no ghost blocker, repeat explosion or stale portrait.

- [ ] **Eliotrope (Selotrop)** — "Portal" routes and mutually exclusive modes. **Notes:**

  **A:** Confirm "Pulsación" rejects an enemy outside direct range. Place two "Portales" making a legal route and attack through them: damage/payment once. Remove one by recasting "Portal" on it; the distant attack now rejects without payment or an invisible remaining route.

  **B:** Use "Exaltación", then again on the next permitted turn: Sereno → Exaltado → Sereno. No simultaneous modes, missing model/bar or broken subsequent attack.

- [ ] **Xelor** — AP-loss duration and dial lifecycle. **Notes:**

  **A:** Without "Mago de Combate" or "Marchitación", use "Ralentización" and note actual AP loss. It survives the upcoming enemy turn start, then expires after that turn; maximum AP remains unchanged. A popup alone is insufficient.

  **B:** Place "Esfera/Reloj" 5345, cast "Ralentización" with normal WP payment: hour advances once,12 →1. Later replace the dial legally: old dial/hours clear, new one starts at 12 and old cells are released.
