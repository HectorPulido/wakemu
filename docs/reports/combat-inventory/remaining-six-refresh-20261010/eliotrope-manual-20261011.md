# Eliotrope manual acceptance battery

This is an acceptance plan, not a claim that all cases have passed. Deployed World/AI/Ecology use catalog `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`; the class evidence in this guide remains historical on PostgreSQL `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`, not a bd79 rerun. Newer integrated tests positively qualify actual Gift→ally attack→giver back-attack Celada +60 and the paired one-use modifier; the remaining boundary is state3671 carrier cleanup/expiry, not acquisition or damage. See the superseding qualification section below and the [six-class closure ledger](current-closure-20261011.md). Manual client presentation remains separate.

## Roster and source reference

The published class inventory is21 owned actives,20 passives and three extra/granted actions. See the [typed inventory](eliotrope.md), [current semantic status](eliotrope-semantic-status-20261011.md) and [mode/passive qualification](eliotrope-mode-passive-qualification-20261011.md). These source/behavior reports are pinned to their stated historical revisions and do not establish the running image.

## Basic modes and portal use

Use an Eliotrope with Portal (4678), Exaltation (4682), Pulsation (4692), and Ardent Aegis (4668) available through the ordinary action bar. Begin a normal fight with an enemy six cells away and an unobstructed route. Do not use administrative resource or state injection.

1. In initial Calm, attempt Ardent Aegis on the occupied enemy cell. The native criterion rejects it; AP/WP, HP, and portal population remain unchanged. In Calm this spell requires a free target cell. This rejection must not be interpreted as a portal defect.
2. Attempt Pulsation against an enemy outside its displayed ordinary range. Expect an ordinary range rejection without spending resources.
3. Place one Portal near yourself and a distinct second Portal toward the enemy, both on cells accepted by the native placement UI. Cast Pulsation at the same enemy. Expect accepted portal routing, normal cost payment, and damage. Keep the enemy beyond ordinary range so this demonstrates portal use rather than merely the presence of portals.
4. Recast Portal on one existing owned Portal cell. Expect that Portal to disappear; the other remains usable. Repeat the out-of-range attack with only one Portal: expect rejection without payment.
5. Cast Exaltation on yourself. Expect Exalted (3303) replacing Calm (3386). After the next legitimate owned turn, cast it again. Expect exactly one Calm carrier and no Exalted carrier.

## Portalivio replacement

Equip Portalivio (7206) through the normal passive deck. Place two distinct Portals, advance to the next owned turn, and place a third distinct Portal. The source branch 346477 selects replacement at two team type-19 areas: expect exactly two Portals afterward, with one old Portal replaced. The strict two-portal replacement and checkpoint case passed in the pinned `677` 35-distinct core gate (`.runtime/class-closure-20261011/345-final-bundle.log`). This is automated server evidence, not live-client or deployed-image acceptance; verify both clients see the replacement and keep the two-portal cap.

## Remaining required acceptance

Foreign-owner Portal interaction, owner death, live-client reconnect, all enabled passive branches, and active prerequisite combinations remain under qualification. The JSON checkpoint reconstruction case passed in the pinned core gate; that is not a graphical reconnect test. Native literal-False effects are dormant source branches and must not be enabled to make this battery pass. Walking into a Portal is not assumed to teleport without recovered native activation evidence.

## Celestial Gift and historical Ambush qualification notes

Earlier gift-acquisition and orientation tests used a staged point-PV candidate on revision677 and did not qualify the Celada branch. That historical limitation is superseded by the later actual-production test below: a real ally Gift turn followed by the giver's back attack qualifies the +60 branch. The documented native chain is state3671 → 351709 → 159742 → 351766; do not add states or infer the positive from a facing-only comparison.

For the manual test use two allied player characters and an enemy that will survive several attacks. Equip Celestial Gift7813, Pulsation4692, Celada4687 and the native prerequisite spell4686 where required. Keep equipment/resistance identical across matched fights. Cast Gift on the ally, let the ally make a real attack on its turn, and have the original giver attack the enemy's back. Compare passive-off baseline+40 with passive-on conditional+60, preserving actual source/recipient, damage and resource records. Do not inject state3671. Front attacks are a separate negative/control branch; the passive does not promise a front bonus.

The gift carrier has native infinite duration. Do not expect it to disappear merely because the giver attacked; carrier cleanup and the Meditation7720 subgroup are separate source contexts. Their complete gameplay qualification remains pending.

### Generated modifier lifetime and Meditation follow-up

The preceding observations were historical and their Celada conclusion has been superseded by the actual supported positive below. The native carrier is infinite-duration in the observed route; the generated one-use attack modifier and the ally's retained carrier are distinct. Keep carrier cleanup/expiry as a separate manual observation rather than treating damage qualification as proof that the carrier should disappear.

For Meditation7720, use an allied recipient with missing HP and keep all ordinary equipment and resistance constant between paired fights. Configure the passive normally before combat; do not add states or resources administratively.

1. Cast Celestial Gift7813 on that ally, with the normal4686 prerequisite present.
2. Let the ally make one ordinary attack during their real turn and finish it.
3. On the giver's next turn, use paid movement into Pulsation4692's displayed range and cast it on the injured ally rather than an enemy. Expect the native allied healing branch. In the fixed automated fixture it restores47 HP without Meditation and56 with it; the equipped branch executes395997(+20 final healing) and registers395998, both original giver7→ally8.
4. Keep the native gift carrier distinction: the first healing flow does not prove that3671 should disappear. The following real healing-trigger lifecycle is being qualified separately; no immediate carrier cleanup is assumed.

All new positive gift and Meditation cases currently require the staged point-PV execution candidate; they are not claims about the deployed server. Formal focused evidence is `.runtime/eliotrope-review-20261011/celada-focused-current.log` (**3/3 PASS**) and `.runtime/eliotrope-review-20261011/meditation-actual-healing-consumer-current.log` (four actual paired cases). The exact client damage/healing varies with the player's build; compare matched builds and the stated conditional behavior.

The next-trigger Meditation probe is terminal: a second legitimate Pulsation heal during the same giver turn returned to the matched47 HP baseline in both passive cases; only the first heal received the56 HP boosted result. The actual gift carrier remained on allied recipient8 with original source7. This establishes the healing bonus as one-use in that sequence; it does not demonstrate that395999 cleans the carrier. Evidence: `meditation-second-healing-consumer-current.log` (four cases); the following-heal unittest subsequently passed1/1 as recorded below.

Final following-heal unittest: **1/1 PASS**, `.runtime/eliotrope-review-20261011/meditation-second-healing-unittest-current.log`, unchanged SHA `73c0654135b6dcc98adb6b4698c99a18e8d99ab3d6b87672a507aeb001c30b88`. The actual first-heal47/56 and second-heal47 results, source7→recipient8 ownership and persistent infinite carrier are asserted. This supersedes the preceding queued-test status; carrier cleanup is not claimed.


### Celada supported sequence and ownership limit

Test Celada4687 through the actual ally-gift7813 route with4686, not an unrelated ordinary attack. After the ally's actual attack, use the original giver's next attack from the back: the source-defined replacement is+60 final damage, replacing the ordinary+40 gift branch. The passive does not promise a front bonus; matched automated fixtures produce lower front damage with it. A following attack no longer consumes that generated one-use bonus. Meditation7720 has a separately validated one-use+20 final-healing branch.

The gift carrier3671 stays on the ally with original giver ownership and native duration−1 in current evidence. Do not require it to disappear after one attack or turn as a manual expected result: its cleanup boundary is unqualified. Verify that a new fight does not inherit the prior fight's carrier; that lifecycle check remains queued for its private automated extension, so manual acceptance must record it separately.
