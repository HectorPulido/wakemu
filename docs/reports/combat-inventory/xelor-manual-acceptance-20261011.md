# Xelor complete manual acceptance — 2026-10-11

Status: **PREPARED / NOT READY**. This is the acceptance procedure, not a claim that every branch works. Its cited Xelor inventory and gameplay evidence are historical and primarily pinned to PostgreSQL release677 (`xelor-current-catalog-20261011.json`); deployed services now use bd79 `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`, with no Xelor suite run against that release yet. Five resource/dial pipeline regressions have passing historical evidence. Several current-hour, conditional-target and passive branches remain unqualified or have failing tests awaiting attribution. The current full18 repeat remains pending. A successful normal cast or Ready screen does not qualify a passive.

The owned roster denominator is21 actives and20 passives, with extra actions3909,5345 and7794. The source inventory is [xelor.md](remaining-six-refresh-20261010/xelor.md) and the machine roster is [xelor.json](remaining-six-refresh-20261010/xelor.json); current semantic matrices are linked from the [Xelor status report](xelor-passive-semantic-status-20261011.md). These exports/tests retain their documented historical release pins.

## Preparation and evidence

1. Select an ordinary Xelor test character. Outside combat, enter exactly `!nivel 200` if below200; `!level 200` is the supported alias. This raises level permanently, cannot lower it and requires existing console permission. Reconnect after changing level. Set the native spell deck through the client UI; do not inject states, HP, AP, summons or granted spells.
2. Keep equipment, characteristics, pets and consumables unchanged throughout each comparison. Record their AP/MP/WP modifiers. The clean native fixture has AP6/MP3/WP12; ordinary equipment/passives can change these totals, so compare **actual deltas** as well as displayed values.
3. Use a consenting second player's friendly challenge first, then ordinary PvM. Existing `!mob 4 8 1` creates one native profile4 level8 enemy where spawning is permitted. Finish or surrender before spawning another group. This enemy is weak at level200 and only suitable for short/death checks. Use a normal durable opponent for multi-turn, resource and healing comparisons; do not judge a nonlethal reaction using an enemy killed by the first hit.
4. Run two legal active rotations. Deck A: Martillhora749, Perturbación750, Suspensión751, Rayoscuro752, Polvo753, Aguja754, Premonición757, Reloj763, Tempus Fugit765, Rueda Dentada766, Hora Punta767, Regreso Espontáneo771. Deck B: Simetría772, Ralentización775, Contrarreloj776, Sinistro777, Reloj de Arena783, Desincronización1417, Paradoja1418, Devoción2839, Regulador5344; add already tested normal spells if desired, remaining within12 active slots. Start without optional passives.
5. At each fight record the time, character names, fight ID if visible, deck, current actor, AP/MP/WP, positions, HP and relevant state levels. Capture before/after screenshots for a discrepancy. Server observer command is `docker compose logs --since 10m world`; do not expose credentials or private logs in commits.

## Opening, ownership and resource transactions

1. Ready both players. The actual initiative winner acts first; a Xelor must not act merely because its client window is selected. On the first **owned** turn, the active portrait, countdown, movement and usable spell bar must agree in both clients. An inactive character cannot spend resources or move. End several turns and confirm every living participant receives exactly one turn in the native order.
2. Confirm the three legitimate combat grants5345 (dial),3909 and7794 appear without adding hidden ordinary deck entries. No unrelated class spell replaces the Xelor bar; the second player's deck remains its own.
3. With no relevant cost modifiers, cast3909 once: AP+1, WP−1 and6752level1. Try it again during the same turn: native one-cast-per-turn rejection, no additional payment, state increase, movement or partial animation. End real turns until the Xelor owns another turn. The next lawful3909 selects AP+2/WP−2 and6752level2. Do not bypass the first rejection to simulate escalation.
4. Cast775 on a genuinely eligible durable enemy: cost AP1/WP1, then observe its native AP-loss/state behavior. An AP-cancelling passive can replace the direct reduction; use the passive controls below. Cast2839 separately: WP−4. Payments and resulting reactions occur once; a rejected action never charges twice or changes the other player's resources.
5. Try an occupied/blocked/out-of-range target and an unaffordable action. Record a normal rejection; the fight continues with the same current actor, legal resources and remaining time. No disconnect, recovery loop or half-committed state is acceptable.

## Dial, current hour and mechanisms

1. On a lawful open placement, cast granted5345. With clean costs, AP−2 and unchanged WP. One owned dial3791 appears, current-hour6759 starts at12 and the ordinary complete layout has twelve distinct native hour references1546–1557. Place sufficiently far from invalid terrain to inspect the complete footprint. With altered-layout passive7189, compare its native layout against the baseline rather than assuming every geometric point is valid terrain.
2. Cast a genuine WP-paid spell such as775. Current hour must advance by the actual paid WP amount;12 plus1 wraps to1. Confirm no duplicate hour advance on one payment. Plain413004 success legitimately skips fallback413005 under native limit1/count-success mode. A separate actual Suspensión751 on the owned dial installs9245level2; paid775 increases it to3 while current hour remains12. After a lawful turn, recast751 to release the stored amount and wrap current hour to3, clearing9245. This sequence passed the actual677 probe; the stronger phase-tagged regression also passed2/2 in permanent-clock-candidate-current.log. Do not expect9245 on every paid spell. Record what the client shows; do not invent a persistent state requirement.
3. Locate the owned current-hour area1558 and compare its position before/after advancement. Its actual creation/transition and owner interaction still require focused qualification. Test current-hour movement only after locating the real area; clicking another player's dial must not grant your own benefit.
4. On a later actual owned turn, place a new dial on another legal **empty** cell. The old dial dies, every old owned-hour UID is retired and the new dial has its own12-hour layout/current12. Same-cell placement can reject the native free-cell condition; that rejection is not a cleanup failure. The second player's dial/hours remain intact.
5. Cast777 Sinistro twice across actual owned turns: baseline replacement versus passive7190's legitimate retention must agree with the tooltip/native mechanism limit. Repeat766 Rueda Dentada and observe its genuine movement/damage trigger. Summons have their native ability books; do not expect a player spell bar or turn on a mechanism whose native book is empty.
6. Cast **Regulador5344** on a legal empty cell. This is a mechanism summon, profile5444, with state7784; **it is not a teleport spell**. Recasting follows the owned replacement rule. The old owned5444 may be retired, but foreign mechanisms must survive. Normal-cast baseline currently lacked an eligible context, so this remains a required explicit manual branch.
7. Kill the dial/mechanism normally, then repeat placement and hour interactions. No invisible occupant, stale LOS blocker, duplicate group entry or immortal state remains. Repeat with two Xelors' mechanisms nearby and confirm ownership isolation.

## Complete active rotation

Use each row in its indicated legal context. Compare the actual current tooltip for level/build-dependent amounts and costs. This table specifies the branch to exercise; it does not claim all rows passed automated semantics.

| Active | Required context and observation |
|---|---|
| Martillhora749 | Hit a durable enemy in the indicated footprint; compare damage/secondary branch at odd and even current hour. |
| Perturbación750 | Hit a legal enemy and inspect its advertised secondary effect after real clock advancement. |
| Suspensión751 | Compare ordinary paid-hour advancement before/after its advertised suspension condition; no double payment. |
| Rayoscuro752 | Exercise the explicit owned-dial/occupied-target prerequisite shown by native eligibility, then damage/target selection. Baseline no-eligible context remains unqualified. |
| Polvo753 | Cast with a valid footprint; observe6743 and damage, then real expiration/removal. |
| Aguja754 | Use native eligible range and AP-dependent casting branch. Check normal damage and remaining-AP branch without forcing eligibility. 754 requires range2–4; dial placement can swap the caster adjacent to its target. The corrected legal placement probe reaches all four controls; do not force adjacency. |
| Premonición757 | Try a legal empty cell and a legitimate non-carried target context; inspect the advertised placement/return behavior. |
| Reloj763 | Compare its native HP/resource reaction on a durable enemy and after genuine state setup. |
| Tempus Fugit765 | Exercise its native movement branch on valid terrain; final actor/QI position, movement animation and subsequent targeting agree. |
| Rueda Dentada766 | Create the owned mechanism and trigger its actual advertised reaction; repeat with a foreign mechanism nearby. |
| Hora Punta767 | Hit an eligible actor and observe the indicated displacement/secondary branch; blocked destinations reject or resolve according to the tooltip. |
| Regreso Espontáneo771 | Set up its native previous-position/return context through actual actions; no stale previous-fight position is reused. |
| Simetría772 | Compare actual odd/even clock branches and valid target geometry; verify both clients agree on the resulting positions. |
| Ralentización775 | AP/WP receipt and hostile AP removal, plus cancellation/distance controls below. |
| Contrarreloj776 | Apply6760/6780 to legal non-carried targets, move normally and reach its actual trigger/expiration. Include an owned mechanism and an unrelated ally. |
| Sinistro777 | Actual birth, book, repeated placement/replacement and death;7190 control as above. |
| Reloj de Arena783 | Apply6745, then trigger its actual delayed behavior and expiry; no effect leaks to the next fight. |
| Desincronización1417 | Compare native clock/state-dependent branches, actual payment and resulting order; no synthetic clock insertion. |
| Paradoja1418 | Exercise valid non-carried targets/positions and its native displacement footprint; no actor overlap or other-target animation. |
| Devoción2839 | Actual WP−4 and corresponding clock advance where enabled; repeated/rejected requests remain atomic. |
| Regulador5344 | Owned5444 mechanism/state7784 creation and replacement, not teleportation. |

## Every passive: legal individual controls

Equip the named passive through the native UI, keeping the same active deck/build/opponent, and repeat against a no-passive baseline in a fresh fight. Do not equip mutually changing clock passives together for the first comparison. There are20 owned passives; older/shared catalog entries are not additional current owned choices. Reactive rows require their actual trigger, not only an icon at Ready.

| Passive | Required comparison |
|---|---|
| Memoria756 | Native maximum WP increases by6 and opening MP decreases by2 versus baseline; actual spending/recovery respects the new cap. |
| Maestro de la Esfera758 | Create the owned dial, advance through genuine rollover and exercise its external349619 consumer; compare foreign ownership. Exact reactive numerical qualification pending. |
| Relojería761 | Exercise the current native tooltip's mechanism/hour trigger with and without the passive. Independent numerical acceptance remains pending. |
| Tac Tic764 | Record native Tick/Tock state, end/ACK actual turns twice and confirm alternation rather than duplicate/missing transitions. |
| Curso del Tiempo785 | Compare a fresh identical setup without/with785. Pay Devoción2839 on a legal enemy (4WP), place the actual granted Reloj5345 (2PA), then use real movement to align owner and enemy on opposite sides of the occupied clock. Cast Paradoja1418 on the clock (4PA). Verify the actual swap and a single1WP refund to the owner only with785; the enemy receives none. The automated reference pays2MP to restore alignment after clock placement; preserve enough MP and clear cells. |
| Presagio5351 | Spend WP, cause actual hostile AP removal with775 and compare the native WP reward against baseline and cap. A prevented removal must not be treated as successful removal. |
| Prontitud5352 | Exploratory: inspect the current tooltip and authoritative conditional casting tables before asserting an even/odd/AP-cost benefit. Its own False root is not proof of an enabled effect, and no independent current consumer has yet been qualified. |
| Tic Tac5353 | Repeat the two genuine turn-boundary alternations independently of764. |
| Contrahorario7184 | Repeat actual turn alternation and paid-WP reactions in its corresponding native state; compare no-passive behavior. |
| Deja Vu7185 | On actual odd versus even current hour, compare outgoing damage and its native healing reaction against baseline. Native odd branch applies−25 final modifier; the legal numerical probe reaches22/22/22/17 for baseline-even/baseline-odd/passive-even/passive-odd. Native stochastic rounding permits16 or17 from a22-point baseline with−25%; the strengthened exact-modifier observer passed in deja-vu-legal-final.log against677. |
| Conocimiento del Pasado7186 | Trigger owned-dial state6761's413760/413761 consumer and compare against no-passive; numerical qualification pending. |
| Presagios Violentos7187 | Move through actual terrain onto the **owned** current-hour1558 area, then reach the next actual owned turn-start1001 while remaining there; repeat with a foreign hour/no passive. The2237 entry publisher is not yet source-proved; do not promise an immediate entry benefit. Actual1001 positive-turn branch passed in own-hour-candidate.log against677 (candidate SHA d28f8ea80d11cee4c3ed6d9ed26e810edd83b05acab3120fc7ccd25f340e3d7f); arrival-only2237 remains unqualified. |
| Dimensión Oscura7188 | Compare actual guarded damage/clock consumers against baseline and their stated prerequisites; reactive numerical qualification pending. |
| Ralentización del Tiempo7189 | Place the dial at a common legal center and compare alternate native hour geometry and associated casting prerequisites; invalid terrain points must remain absent. |
| Remanencia7190 | Create two actual Sinistros across genuine turns; compare legitimate retained population versus baseline replacement, then kill/remove one. |
| Mecanismos Especializados7191 | Trigger its actual mechanism consumer, not merely a birth/icon. Actual7191 spatial control passed in remaining-boundaries-current.log: enabled349690 swaps owner(-8,-7) and clock(-11,-7), while baseline retains positions. Other numerical/ownership guards remain pending. |
| Permutación Momentánea7192 | Exercise the real mechanism movement/swap trigger and compare positions/ownership against baseline. Actual7192/312897 swaps owner and clock in remaining-boundaries-current.log against677; baseline retains positions. Other guard boundaries remain pending. |
| Mago de Combate7193 | Use775 at distance2 and distance3. Its near branch can **cancel direct AP removal** and apply its alternate state/reaction; do not require AP reduction and the cancelling branch simultaneously. Check the complementary far control. |
| Marchitación7195 | Repeat775 at distance2 and distance3; the corresponding distant branch can replace/cancel direct AP removal and apply6774. Check complementary near control. |
| Asimilación7196 | Maximum WP decreases by6 versus baseline; after actual WP payment, kill a real enemy and verify the native reward once, respecting the reduced cap. Nonlethal hits and unrelated/foreign deaths do not grant a duplicate reward. |

Granted7794 also needs its own actual charged-versus-uncharged control. Build6779 through real rollover, cast7794 legally, inspect scaled6744 and consumption of6779/owned-dial7887. Do not insert counters manually. The actual granted-7794 probe produced6744level6 with no charge versus12 with one naturally built charge, and consumed6779/7887. The strengthened permanent regression additionally proves7887 was present before cleanup; that full candidate passed in permanent-dejavu-charge-current.log against677.

## Full lifecycle and regression acceptance

1. Repeat friendly PvP with both characters, then party PvM and a real dungeon room. Ready and first turn agree across clients. A defeated actor never gets a live turn, AP or movement; a final removed NPC/summon releases its obstacle, while reversible player KO preserves its registered resurrection slot; a surviving actor never receives another actor's death animation.
2. During an ongoing fight disconnect one client normally, reconnect and compare the full participant roster, enemies, owned mechanisms/hours, positions, states, true current actor and spell bars. The remaining client continues or waits according to the normal reconnect policy; no permanent frozen turn. Repeat with the second client reconnecting first. JSON checkpoint tests alone do not prove this client path.
3. Finish a fight normally; repeat by surrendering one character. Neither client is expelled to login, remains flagged in combat or retains a countdown/spell bar from the previous fight. Party sword indicators clear consistently. Start a fresh fight: no old dial, hour, state, counter or previous-position pointer survives.
4. Complete a dungeon room with both characters. Both leave combat and reach the next populated room together. If a fight aborts, its monster group must remain or recover through the normal dungeon policy; no permanently empty room blocking progress.
5. Repeat a basic Cra beacon/arrow sequence and an Iop attack/combo in a separate normal fight. Shared targeting, resource, turn and death handling must preserve these already provisionally qualified classes.

Acceptance stays **NOT READY** until unresolved active prerequisites, current-hour/9245/1558,7794 and reactive passive branches have meaningful positive/negative evidence, and the multi-client lifecycle checks pass. Record failures with the exact step/deck/time rather than declaring the whole class complete from a successful opening.
