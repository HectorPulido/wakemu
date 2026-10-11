# Pandawa implementation inventory — 2026-10-10

## Pinned source

PostgreSQL complete published revision `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`. Read-only inventory:38 own spells (21 active,17 passive),5 referenced granted actions,943 effects,44 states,1 area. Zero missing records in the traversed executable closure. This is structural evidence, not complete gameplay certification. Shared common passives are counted separately.

## Owned spell inventory

| ID | Name | Kind | Level |
|---:|---|---|---:|
| 4702 | Escupe Fuegos | active | 1 |
| 4703 | Ronda General | active | 3 |
| 4704 | Golpe Lechoso | active | 9 |
| 4705 | Frasco Explosivo | active | 15 |
| 4706 | Lactortazos | active | 21 |
| 4707 | Escupe Leches | active | 1 |
| 4708 | Nube de Leche | active | 5 |
| 4709 | Tequileche | active | 11 |
| 4710 | Tsunami | active | 17 |
| 4711 | Fuente de Leches | active | 23 |
| 4712 | Triple Karma Gnosborne | active | 1 |
| 4713 | Six Roses | active | 7 |
| 4714 | Golpe de Tonel | active | 13 |
| 4715 | Lucha Cubalibre | active | 19 |
| 4716 | Barriltzkrieg | active | 25 |
| 4717 | Golpe de Bambú | active | 3 |
| 4719 | Éter | active | 45 |
| 4720 | Resaca | active | 60 |
| 4721 | Happy Hour | active | 30 |
| 4722 | Cóctel | passive | 25 |
| 4723 | Maestro de la Embriaguez | passive | 30 |
| 4724 | Tonel sin Fondo | passive | 10 |
| 4725 | Tonel Agresivo | passive | 55 |
| 4726 | Instinto Lechoso | passive | 40 |
| 5148 | Bambutella | passive | 10 |
| 5149 | Cianosis | passive | 35 |
| 5151 | Pandemia | passive | 20 |
| 5152 | Barrilisto | passive | 15 |
| 6844 | Sed | active | 15 |
| 6845 | Pandenkulo | active | 75 |
| 6846 | Piripi | passive | 100 |
| 8595 | Paso Firme | passive | 45 |
| 8596 | Túnel Visión | passive | 70 |
| 8597 | Fermentación Láctica | passive | 80 |
| 8598 | La Gota que Colma el Vaso | passive | 50 |
| 8599 | Cianótico | passive | 65 |
| 8600 | Pandaperitivo | passive | 60 |
| 8601 | La Última | passive | 90 |

## Source-qualified mechanisms

- Innate7558: root340650 listens1028 and grants Karcham6847, Chamrak6848, Barrel4718, Toneportation8591 and Drunkenness8592 through native649. Grants exclude transformation933 and instance862; these conditions must remain intact.
- Barrel4718→147263/family307 constructs native profile3794, descriptor level−2. Constructor initial states and profile-only properties must be verified independently of the spell closure.
- Carry/release families333/334 and345 are shared source-backed handlers. Own-barrel criteria explicitly require3794; PB11 restricts eligible placement/carry branches.
- Innate417069 listens1001 when a3794 summon exists.417329 listens1002 for end-turn transitions.417331 listens2223; an observed actual4702 Tipsy removal now verifies its native321 source and successful listener execution.
- Drunk3300 has native damage/healing modifiers conditional on passive4722; state6107/3316 are Tipsy,9334/3367 Hangover. False branches remain intentionally false, not missing implementations.
- Resource68 and its client state3300 must be distinguished from the native named states and UI presentation. No direct flat resource behavior is inferred from labels.

## Validation plan

A bounded normalcast matrix covers21 actives across baseline plus17 legal single-passive variants (36 decks,378 normal action rows), with actual Ready grants reported separately. It preserves resource costs and native eligibility; missing contexts are not engine failures. Targeted acceptance must cover own barrel creation/initial states, ally/enemy/own-barrel carry, carrier movement, legitimate throw, occupied-cell rollback, drunk/tipsy/hangover transitions, passive variants, turn clocks and death cleanup.

## Current limits

The inventory traversal follows state application304, area315/339, grants649 and nested426. Profile307 constructor3794 initial-state dependencies are now exported in the supplemental constructor closure with no missing definitions. Other native reference families still require separate qualification. Targeted gameplay results are recorded below; matrix success alone is not complete semantic acceptance. No service or catalog publication was performed.

Native2223 is not assumed absent: several321 definitions (for example145429 and417093 removing6107) declare2223 in their produced mask index6. Its delivery is through the shared decurse event producer. The fresh Last Drop regression observes2223 from actual family321 with a positive runner UID and the original caster7→target−7, then verifies417331 executes and preserves the baseline1WP versus passive armor comparison.

## Bounded normal-cast result

The current published `c97c...` matrix completed36/36 legal Ready configurations with stable source hashes and zero engine failures. It committed342 ordinary casts (19 distinct active spells across baseline plus17 single-passive configurations) and108 actual granted actions. The only two ordinary spells lacking a nominal context were Barrel Bash4714 and Thirst6844: both require an actual owned barrel. The missing grant contexts were Chamrak6848 (requires a carried actor) and Toneportation8591 (requires a barrel). These are explicit prerequisites, not unimplemented spell labels. Actual follow-up tests provide those contexts separately. Raw evidence: `.runtime/pandawa-review-20261010/normal-matrix.json`.

The companion `pandawa-passive-branches-20261010.json` enumerates all17 passives and every explicit deck-criterion branch in this conservative closure. Passives with no explicit deck predicate still have their own root recipes; absence from the predicate list does not mean they do nothing. The normal matrix is not proof of every conditional passive reaction.

## Manual acceptance battery

Use a Pandawa with the named actions legally available at the current level. Ready must expose the innate actions4718/6847/6848/8591/8592; do not insert these into ordinary deck slots manually.

1. **Barrel and transport:** summon Tonel4718 on a client-highlighted legal free cell. Carry it with Karcham6847. Finish the owned turn and inspect Drunk3300 and the barrel/carrier alignment. Throw with Chamrak6848 to a legal destination; the pair must separate without an invisible blocking actor. Repeat against an enemy, then reject an occupied or otherwise invalid destination and confirm costs/position remain unchanged.
2. **Mode-sensitive actions:** with the owned barrel present, use Barrel Bash4714, Thirst6844 and Toneportation8591 on their client-highlighted native targets. Confirm the target restrictions differ; a fresh fight without a barrel must not silently accept barrel-only actions.
3. **Drunk and inverse transition:** use Drunkenness8592 on self. Record3300 and native resources. Repeat the legitimate toggle/turn sequence and inspect9349/3367/9334 as actually produced; do not expect every similarly named state simultaneously. Finish further turns and confirm transient effects and spell costs recover when the source state is removed.
4. **Milk Cloud4708:** cast on a legal target. Its native glyph837 must belong to this Pandawa, deliver the actual healing callback on eligible recipients and expire after its native clock. A second Pandawa must not take ownership of the first player's cloud.
5. **Passive comparison:** compare one passive at a time with an otherwise identical legal build. Cocktail4722 changes the native Drunk damage bonus to healing; Fermentation8597 requires the carried-barrel/end-turn condition for armor. Other passive-specific branches are listed in the machine inventory and remain separate from the nominal cast matrix.
6. **Death and persistence:** kill a carried actor and kill a carrier using an actual third attack source. Confirm both carry references, QI blocking and timeline remain coherent. Reconnect during carry, end the fight, and enter another fight: no stale carry pair, glyph, barrel ownership or temporary book may survive incorrectly.

These are manual probes pending client execution, not claims that their visuals or every edge branch have passed.

## Semantic acceptance status

All17 legal passive variants completed the bounded normal-cast matrix. The following distinctions prevent nominal coverage from being mistaken for completed conditional behavior:

| Passive | Additional semantic evidence | Remaining acceptance |
| --- | --- | --- |
|4722 Cocktail|Actual3300 changes damage+50 to healing+25; both branches passed|Client presentation|
|4723 Master of Drunkenness|Actual8592 extra cost and next-turn interval positive/negative passed|Client range display|
|4724 Bottomless Barrel|Actual adjacent auto-carry/direction and baseline negative passed|Client presentation|
|4725 Aggressive Barrel|Actual unheld destruction, baseline negative, carried exclusion and surrounding allied/enemy Tipsy recipients passed|Client presentation|
|4726 Milky Instinct|Actual constructor6107/9356 and real owner-start countdown3→level1 nativekill, baseline negative passed|Client countdown/death presentation|
|5148 Bambutella|Actual Drunk dodge +400 at level200 and baseline negative passed; native signed tackle retained|Positive tackle build passed; client display remains manual|
|5149 Cyanosis|Actual enemy6107→3690, start damage and6107 cleanup; baseline negative passed|Client poison presentation|
|5151 Pandemic|Actual incoming−20 reduction and4704 outgoing Tipsy+20 exclusion with baseline comparisons passed|Client damage presentation|
|5152 Barrel Wisdom|Actual constructor4163, baseline negative and native LOS/barrel transparency consumer passed|Client presentation|
|6846 Tipsy|Actual Drunk→enemy carry→throw range comparison passed|Client range display|
|8595 Firm Step|Actual8591 baseline/passive LOS and linear flags passed|Client target highlighting|
|8596 Tunnel Vision|Actual opposing melee−20 and distance+20 modifiers, damage comparisons and baseline negatives passed|Client directional damage presentation|
|8597 Fermentation|Actual held-barrel end armor and direct back-hit fullclear versus nonback residualarmor passed|Client armor presentation|
|8598 Last Drop|Actual owned Tipsy removal gives baseline1WP/noarmor versus passive0WP/5%maxHP armor, passed|Client armor/resource presentation|
|8599 Cyanotic|Actual injured ally6107→9366→recipient-start healing and cleanup passed; baseline negative passed|Client healing presentation|
|8600 Pandaperitivo|Actual held-barrel4705 release establishes9368 restriction marker onlywithpassive; baseline negative passed|Actual adjacent allied/enemy Tipsy recipients and repeated restriction passed; client presentation|
|8601 Last One|Actual end1037 attraction, baseline negative and registered-enemy blocked path passed|Client movement presentation|

Actual constructor, enemy carry→throw, Drunkenness, Cocktail and own-barrel active/grant contexts passed. Actual third-player4784 kills passed for both carried actor and carrier; carry references and QI remain coherent without a production patch. Milk Cloud actual creation/ownership, real-turn expiry and absence of dangling retained manager records passed in a fresh rerun. No production carry-cleanup fix is claimed. The held-barrel test now inspects the actual end1002 preview: state3300 has native duration1 with a target start clock, so its absence after the next start is not by itself a missing event producer.

## Shared own-summon selector correction

The actual4725 acceptance exposed a missing relationship in the existing Wakemu fresh-child selection policy. Native418035 is a SELF end1002 listener; its child418036 requests fcE4096 (own living summon) before418038 applies native kill28. The fresh relationship mask previously included ally/enemy/area relationships but omitted4096, leaving the transmitted owner selected and causing the barrel-breed criterion to reject it. The shared mask now includes4096. Native target filtering still requires eGj,dTE,dpu ownership and rejects baG/baK; already chosen Qe.g/event replay PVs remain bound. This is an extension of the explicit server fresh-selection policy, not a claim that native aZX changed. Actual4725 positive and carried-barrel negative passed after this correction. Shared resolver/direct-target regressions passed23/23; the final Pandawa runtime/barrel/carry-death aggregate passed13/13 without skips. The23-test batch includes the separate own-summon policy regression.


## Automated verification record

Luna executed the opt-in current-revision runtime modules with read-only PostgreSQL catalog `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`, `WAKFU_TEST_GRANTEDCAST=1`, and GC disabled. Final aggregate: `test_combat_pandawa_runtime test_combat_pandawa_barrel_passives_runtime test_combat_pandawa_carry_death_runtime`:13 tests passed, zero failures/errors/skips. Shared `test_combat_effect_resolver test_combat_direct_target test_combat_pandawa_summon_selection`:23 tests passed. No deployment, restart or catalog activation was performed by this workstream. Source resolver SHA256 at freeze: `5552f286f6dcd699f3bd5bb361213a7aa559b671e2c1ee63884b17210513ed2a`.

The provisional result covers all21 active spells with lawful runtime casts across the bounded matrix and prerequisites, all17 legal passive configurations nominally, and the targeted positive/negative mechanisms listed above. It does not certify every passive reaction, client visual, reconnect permutation or manual scenario.

## Additional passive cycle qualification

Read-only PG records qualify8592 separately from translated descriptions: baseline cost is1WP, conditional4723 cost2WP; sober baseline range0–4 versus4723 range1–1. Native limit interval is2 versus0 with4723 (per-turn cap1). Interval acceptance requires an actual runtime start/table-turn boundary before the first recorded cast; a Ready-only fixture still has placeholder table turn0 and must not be used to infer cooldown behavior. No production counter was altered.

The8601 source is418468 subscribed to1037, followed by own-barrel crossRing2–20 selector418469 and native301 attraction418471. Actual aligned-barrel owner attraction and baseline no-movement comparison passed. This uses the existing explicit server regeneration boundary; no1002 alias was introduced.

For5149, owner-end418057→418059 adds3690 while6107 may still coexist. Poison state3690's1001 root160735 applies1083damage, then321 children418056/418074 remove3690 and6107. Tests inspect end conversion separately from start damage/cleanup; an end-only disappearance expectation would contradict this ordering. The corrected full-cycle test passed, including actual damage and cleanup.


The additional `test_combat_pandawa_passive_cycles_runtime` (2), `test_combat_pandawa_poison_runtime` (1) and `test_combat_pandawa_pandemic_runtime` (1) passed4/4 with zero errors/skips. These add actual cost/interval, attraction, poison cleanup and opposing-player incoming-damage evidence; they are separate from the earlier13-test aggregate. Production remained frozen throughout these test-only additions.

Fresh `test_combat_pandawa_mode_passives_runtime` passed2/2:5148 native Drunk dodge gain400 at level200 (the level-group multiplier is200%, not100%), and6846 actual Drunk→enemy carry→throw range comparison. The melee method of `test_combat_pandawa_tunnel_vision_runtime` passed1/1. `test_combat_pandawa_ally_heal_runtime` passed1/1 with a coherent injured ally snapshot, actual8592, owner-end conversion, recipient-start healing and cleanup. Fresh Last Drop and both Tunnel Vision methods passed3/3. Actual Pandaperitivo held-barrel release and restriction marker establishment passed1/1; repeated restriction subsequently passed; nearby recipients remain a separate acceptance branch. These results are additional scoped gates, not a rerun of the complete aggregate.

### Supplemental passive manual battery

Use a level200 Pandawa and change one passive at a time outside combat. Keep the same equipment, opponents and spell levels for each baseline comparison. These checks are pending client execution even where server integration passed.

1. Equip8599, start with an injured allied player, cast the granted8592 on that ally, then end the Pandawa turn. At the ally's actual turn start, expect healing and removal of the converted9366/Tipsy6107 state. Repeat without8599: no healing from this conversion.
2. Equip8598, summon a barrel to create a legitimate WP deficit, apply8592 to an enemy and remove that owned Tipsy state with4702. Expect armor equal to5% of the Pandawa's maximum HP instead of the baseline1WP recovery. This is an armor replacement, not increased WP recovery.
3. Equip8596, become Drunk using8592 on self and receive the same opposing-player attack first at melee distance, then beyond melee in a separate otherwise equal case. Expect the native final modifier−20 for melee and+20 for distance; compare with no passive. Do not infer this from elemental labels.
4. Equip8600, summon and carry the actual owned barrel, then use the held-barrel4705 mode to release it. Inspect the barrel restriction marker9368 and nearby Tipsy recipients. A second attempt with an already marked barrel must satisfy the source's `not HasState(9368, "target")` gate before any repeated passive activation is expected. The subsequent automated test also qualifies repeated same-turn restriction; nearby recipients remain a separate acceptance branch.

All17 legal Pandawa passives now have at least one source-qualified semantic runtime branch, with baseline/negative comparisons where specified in the table. This is not exhaustive branch coverage: barrel LOS, surrounding recipients and client presentation remain explicit risks until the final gates below close. Positive tackle and repeated Pandaperitivo restriction subsequently passed. The latest fresh gate was `test_combat_pandawa_last_drop_runtime test_combat_pandawa_tunnel_vision_runtime`:3/3 passed; separate `test_combat_pandawa_aperitif_runtime`:1/1 passed.

## Owned turn identity qualification

The added actual4726 countdown test exposed a concrete context gap: native9356 starts at level3;417630 subscribes global1001 and requires `GetTriggeringEffectCasterIsSameAsCaster()`,417631 decreases9356 by1, and417632's kill branch is restricted to level1. Existing external turn events deliberately carried a null native Qe, making that identity predicate always false. The shared correction adds separate scalar owned-turn facts (policy, actor, turn, phase, event) and validates them against the actual active turn. It qualifies only the identity predicate while the native triggering runner, UID, caster/target aliases, PK and PL remain absent. This is explicit Wakemu server boundary policy; no recovered original server caller is claimed. Foreign actor, stale turn, mismatched event/phase and attempts to combine a native source or cast boundary are rejected. Luna fresh combined gate passed43/43 without skips, including3 owned-turn guard tests, actual4726 countdown,11 turn-event tests, Pandawa runtime and actual8597 back-hit/nonback armor comparison.

The first outgoing Pandemic comparison used4702, whose native root145685 executes145427 (removes6107) before145419 (damage). Absence of the Tipsy modifier after that removal is expected. The corrected comparison uses4704, whose native range is exactly2 and whose closure has no6107-removal branch, with a real terrain-derived opponent position at distance2. The corrected actual4704 comparison passed1/1; retained417589/417590 trace remains available in failure diagnostics. The already verified incoming−20 branch remains valid.

The latest qualified inverse lifecycle is native4726 barrel9356 countdown followed by actual417632 kill at statelevel1; the owned-turn context correction made this route executable without a synthetic running effect. Fermentation8597 direct back-hit removes all existing held-barrel armor, while an actual nonback low-level hit leaves positive armor. These tests passed in the43-test shared gate.

### Additional scoped execution history

The following extensions were outside the original43-test gate. Their subsequent individual outcomes are recorded explicitly:

- `test_combat_pandawa_mode_passives_runtime.test_bambutella_loses_real_aptitude_tackle_in_positive_build`: native aptitude18×20 supplies120 tackle before snapshots; compare actual Drunk loss against the baseline. PostgreSQL stat7 has signed-int bounds, so the source-qualified expectation is120−400=−280; the corrected case passed its fresh runtime gate.
- `test_combat_pandawa_aperitif_runtime`: extended initial-marker case repeats real carry→4705 on the already9368-marked barrel and asserts the restricted children are not executed; both methods passed the fresh final rerun.
- `test_combat_pandawa_passive_cycles_runtime.test_last_one_actual_attraction_stops_at_registered_enemy_blocker`: subsequently passed fresh1/1; actual registered enemy between owner/barrel and native418471 attempted without moving participants through the blocker.

The shared owned-turn production correction and its43-test gate remain unchanged. The additional outgoing Pandemic test passed separately1/1 after selecting a spell that does not remove Tipsy before damage.

### Final positive tackle and repeated Aperitif gates

Fresh Luna runs passed the positive5148 build and repeated8600 methods. Native aptitude18×20 supplies120 TACKLE; Drunk removes400, yielding−280 under the native signed-int bounds (no zero clamp). The repeated8600 test uses AP8 from major aptitude2 and owned equipped amulet2021, creates the barrel in the preceding turn, then performs carry→throw→carry→throw in one owned turn. Both throws use native-selected eligible free cells. Marker9368 exists before the repeat;418445 is reached while418447/418448 are suppressed. No resource/state injection or production change was used. Cross-turn marker persistence is not asserted: the native marker expires at the next boundary. Nearby ally-recipient combinations and client presentation remain separate manual/semantic branches.

## Final technical branch closure

The fresh Last Drop and both Aperitif methods passed against current complete published revision `13c8122abba26ca40757c48df137540a5f0e6defdc6676cde6fd19ac6b84b33d`. The original traversal revision above remains historical source evidence. Last Drop now observes actual2223 from the original321 runner and successful417331 execution. Two new surrounding-recipient tests initially used diagonal target cells and correctly failed native alignment with `twU`; their constructors now use an aligned free cell with actual nearby allied and enemy players. The new5152 LOS test exposed a general live-property consumer defect: registered summon authority returned immutable constructor properties after native447 had changed the actor PB. The provider now validates and reads current counters/current properties, preserving the constructor record, overlap/removal semantics and preview isolation. Fresh execution passed the generic summon module21/21, actual5152 transparency/LOS and4725 surrounding allied/enemy recipients. The first Pandaperitivo nearby fixture correctly hit its native restriction:4718 constructor147236 includes418439→418442, applying9368 immediately when8600 is equipped and construction distance exceeds0. The same-turn throw selects the barrel but correctly suppresses418445. The corrected positive advances actual turns through marker expiry, verifies absence before and after carry, and then throws toward allied/enemy recipients. Its fresh final-frozen execution passed, including both baseline/passive cases and the original allied/enemy recipient assertions. The renamed constructor test also passed its birth-marker assertion and same-turn release preservation. The complete client battery is [Pandawa manual acceptance](pandawa-manual-acceptance-20261010.md).

Deployment boundary: the live-property correction is validated local checkout code, not a live deployment. Parent read-only verification found runtime `combat_summon.py` SHA256 `1ac72b92569d2dce0f456b6531ea599f7b9695ff2e543bd3e5c1228ecd97990b`, while corrected local source is `a60ba7fb5a1e0531e73f077d80e7dac63cfb13dad7b4335be2713575d9698892`. No service was restarted for this work.

Fresh final-frozen runtime execution passed all three added technical methods:4725 surrounding allied/enemy recipients,5152 actual native LOS transparency, and8600 actual throw recipients after native restriction expiry. The constructor-marker and Last Drop2223 assertions are source-qualified; repeated8600 restriction remains covered separately. The complete51-module aggregate was still running when these individual outcomes were recorded; its final result belongs to the parent release report. Manual client acceptance remains pending, and the local PB fix has not been deployed by this workstream.
