# Sacrier runtime risk audit — 2026-10-09

## Scope and confidence

Read-only implementation review of breed 11 special mechanics. No production code, database or service was modified. This document records code-backed capabilities, explicit unsupported branches and acceptance gaps; existence of a handler or historical successful fixture does not certify a whole spell or class. Current test execution belongs to the separate validation audit. Native effect definitions and reverse-engineered runners are evidence; server event-production policies explicitly labeled Wakemu remain policies, not recovered original server behavior.

## Concrete findings first

- **Confirmed runtime blocker:** current passive activation rejects Immolation 7224 with `Unaudited native dispel flags: [17]`; exact failing flag-sensitive family is421 (leaf162668); family321 state removals use a different handler and are not blocked by this validator (see below).
- **Confirmed missing metadata:** innate 3702 conditionally installs absent state 759 through 316596/316608/316615. These branches have ordinary team and HP-accumulator conditions, not literal `False` criteria.
- **Sacrifice 5044 is not blocked by ratio -2:** its sole exported redirect 161467 uses ratio 100. Complete ally protection, deferred swap and low-HP cleanup still need current normal-entry replay.
- **Refusal 5052 is a 20% HP threshold armor/reaction chain:** the current closure has no protected-kill 332 or revival runner. Audit those actual thresholds, rather than inventing revival behavior from its name.
- **Pact 7217 has a current cost-group implementation:** the historical initialization failure is not current proof of absence. Its family 912 specifically consumes paid signed-byte eWf costs, not family 910 live spell-cost resolution.
- Current catalog evidence: revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`; audit JSON SHA256 `c23272fb00f818b1aac2e19a4eda01823239f007d938972645189604d405d583` (after dynamic reconciliation). `combat_cost_level_group.py` SHA256 `32ed361873ee65cd1bfd93a359c3a69e96bfc55d030390af6a73ca4fda279aaa`.

## Highest-risk paths

|Priority|System|Implemented evidence|Remaining risk / required verification|
|---|---|---|---|
|P0|Damage redirection / Sacrifice|`combat_redirect_runner.py:52`, `combat_runner_target.py:52`: native family 1000 changes the actual triggering runner target while retaining caster and anchor. `test_combat_redirect_runner.py` checks damage/heal target consumption and stale identity rejection.|No complete actual 5044 ally protection → incoming attack → position exchange → expiration trace established by this review. The only current Sacrier redirect 161467 uses ratio100; ratio-2 is not reachable in this closure. Include two protectors, source death and area attacks; avoid loops/double payment.|
|P0|Self-lethal / reactive-lethal damage|`combat_runner_target_life.py` uses real native baG/baK status, not HP alone. `combat_death_events.py:14` requires actual OFF_PLAY registration, lethal source and one sequence delivery. `test_combat_lethal_reactions.py` covers actual Cinetosis 5041 → Atracción 5030 lethal listener.|Verify owner death during self-damage and simultaneous owner/enemy deaths, PvP KO vs PvM death, retained listeners, timeline removal, visual actor identity, reconnect and dungeon outcome. A one-NPC lethal reaction is not proof of owner revival or near-death passive semantics.|
|P0|Temporary action book / Vengeance|`combat_morph_handler.py`, `combat_morph_spellbook.py`, `combat_morph_dependencies.py`; historical `native-morph933-lifecycle-review-20261008.md` records actual 8587 → profile 5900, independent 8588/8589/8590, restore and expired/foreign UID negatives.|Live grants/action bar, reconnect while transformed, turn expiration, self-death during form, two players and form cancellation must be checked. These directly resemble the Cra/Iop wrong action book and owner-authority failures.|
|P1|Current/max/raw/virtual HP|`combat_hp_raw.py` separates raw and effective HP; `combat_hp_level_group.py` has 1047 and characteristic group evaluation, Java int32 arithmetic and explicit zero-maximum rejection. Heart of Blood tests explain native Vitality scaling.|Do not infer expected self-damage/heal from exploration max HP. Test HP maxima changing with missing HP, armor, equipment/aptitudes/passives, negative raw bounds, exact threshold crossings and nested damage before a child HP query.|
|P1|Self-damage storage and consumption|`test_combat_heart_blood.py` covers 5028-generated state 4840, actual innate grant 6065, healing/armor, 9312/9314 consumption, usage limit, transaction isolation and RNG rollback.|Multi-target blood spells must produce correct owner self effects exactly once per native branch; stored damage must not be counted twice by armor, redirected attacks or nested reactions. Verify next-turn and next-fight reset, zero store, lethal self-hit and rejected 6065.|
|P1|Berserker/Furor and damage based on lost HP|`test_combat_turn_events.py:325` checks actual breed 11 state 9313 recalculation to 50 at half HP at turn start without mutating the source fight. `combat_hud_resource.py` explicitly maps breed 11 HUD stat 50 to state 9312, not HP-percent state 9313.|Half-HP test does not establish every live damage/heal update. Test exact 50% boundary and both directions, percentage rounding, armor-only hit, damage redirection, healing and maximum HP changes. Do not confuse Furor resource with percentage HP icon.|
|P1|Attraction / teleport / transposition / collision|`combat_displacement.py` covers audited native pull/push, teleport, swap; selected surface provenance is checked. `combat_displacement_events.py` distinguishes movement runner events and collision 204. `combat_displacement_collision.py` provides collision semantics.|Check 5030, 5042, 5043 and chained 5041 against walls, elevation, diagonal/linear predicates, occupied cells, dead actors, stabilized/carried actors, summons and boundary cells. Verify exact triggering distance and once-only reaction after displacement, not merely final position.|
|P1|Armor and damage absorption|`combat_armor.py`, `combat_damage_handler.py`, actual 5033+5053 scenario in `test_combat_armor_pipeline.py` verifies armor lifecycle and post-application rollback.|Verify partial/exact/excess absorption, self-damage flags, armor gain/removal at owner and target turn boundaries, missing-HP formula, redirected hit order and owner/source attribution. Initial aptitude armor 36 is separate from Sacrier spell armor.|
|P1|Passives and turn subscriptions|`combat_turn_events.py`, `combat_event_replay.py`, `combat_state_carrier.py`; state 3702's -1000 duration is deliberately preserved, not normalized to generic -1.|Every passive needs an actual unlocked and equipped deck activation, correct state ownership, triggered branch and removal check. Catalog activation counts alone do not prove timing, threshold, native RNG or interaction correctness.|
|P1|Refusal threshold armor and general lethal lifecycle|5052 currently contains armor1013, HP-level1047 and trigger-value430, with native20% damage/heal thresholds; no revival/protected-kill332 appears in its closure.|Verify exact threshold crossing and armor/source-value effects. Independently test self-lethal and PvP/PvM status cleanup; do not ascribe revival to Refusal based on its name.|

## Concrete shared engine gaps, not hypothetical missing class spells

- `combat_runner_target.py` rejects ratio -2 generically, but current Sacrier closure never requests it. This is not a Sacrier blocker.
- Missing live source-runner target binding and stale source UID are explicit errors. Actual Sacrifice must supply both through ordinary event delivery.
- `combat_death_events.py` raises if a global KO observer requires a native PV collection producer that is unavailable. This is deliberately stricter than pretending the observer succeeded.
- `combat_ordinary_death.py` requires explicit evidence for dynamic corpse gates. New Sacrier reaction branches can reveal unsupported status contexts even when ordinary positive-HP spells work.
- `combat_displacement.py` rejects unavailable selected surface provenance and unknown parameter variants. A rejected branch needs its actual definition and terrain context captured; bypassing LOS or permitting arbitrary destination cells would regress Cra.
- These branches are verified source restrictions. Their reachability in the current Sacrier spell/passive closure must be measured separately before assigning a spell a broken status.

## Existing Sacrier evidence worth preserving

`test_combat_heart_blood.py` has three actual initialization/cast/commit tests. Its level-20 example obtains 140/330 HP from native innate modifiers, uses real granted 6065 for 1 AP and 1 WP, obtains 47 armor from native child-level rounding and proves failed repeated cast preserves snapshot/RNG. Level-200 case obtains grants 6065/8586 without inserting them in the deck. These numbers are fixture-specific, not promised universal tooltips.

Historical four-class acceptance documents also record 5028 at 3 AP with state 4840 level 5, self-damage `floor(combat_maxHP * .01 * 5)`, and native 8587 prerequisite 9322 obtained through ordinary damage/turns. Use those as test design evidence, then replay current code and catalog; do not substitute injected prerequisite states. Historical 933 audit states all three temporary children were individually tested; the earlier inverse-cone failure is superseded there and must not be reported as a current confirmed failure without a rerun.

## Reuse from Cra and Iop, without class-specific patches

1. **Explicit group target transmission:** current `combat_effect_dispatch.py` preserves original on-target/transmit-target semantics. Mandatory for blood self/ally/enemy nested groups and Sacrifice. Do not revert this to cure one marker issue.
2. **Preparation consumption policy:** `combat_attack_preparation.py` tracks real primary direct damage sources and successful modifiers, then enables original cleanup. Reuse structurally only where the same native branch/criterion pattern exists; do not hardcode Sacrier spell IDs or claim every HP bonus should consume like Iop Preparation.
3. **Owner/grant authority:** original granted action UIDs, state owner and invocation properties replace actor-shift guessed UIDs. Apply to 6065, 8586, 8587 and morph actions. The shared summon owner/stat ordering fixes remain relevant when Sacrier targets summons, although Sacrier is not a beacon class.
4. **Death, LOS and occupancy:** actual registered death state, source-qualified damage/death payloads and arena/surface geometry must agree across targeting, movement, visual scripts and finish. A corpse must not become an invisible LOS blocker because a UI actor disappeared.
5. **Transactions:** preserve clone/preview, original-fight immutability, RNG rollback, resource payment once, actual retained manager authority and checkpoint serialization across all nested damage/armor/movement and morph branches.
6. **Turn guard:** `combat_turn_guard.py` provides atomic retry claims and bounded transient retries. It must not fabricate ACKs, skip deterministic missing implementations or award a victory for an unfinished fight. UUID primitive retry state avoids the previous unserializable-context freeze.
7. **Aptitude initialization and tackle:** build-level cap validation, actual HP/armor bonuses and native lock/dodge payment apply generally. Barrier renewal is a documented Wakemu policy, not a substitute for Sacrier-specific timer behavior.
8. **Multiplayer lifecycle:** group start/readiness, participant ownership, first turn, disconnect/reconnect, surrender, shared result delivery, party flags and dungeon continuation remain mandatory Sacrier acceptance cases because prior failures were shared systems, not Iop attacks.

## Acceptance order

First replay actual initialization and grants, ordinary enemy damage, owner self-damage/storage, 6065 healing/armor/consumption, HP thresholds and one complete fight cleanup. Then exercise all displacement/5041 reactions, ally protection and redirected lethal hit. Finally run temporary book, every passive and combinations, multiplayer PvP and PvM, surrender, mid-turn reconnect and dungeon advancement. Include negative casts (resources, LOS, occupied cell, invalid owner, expired action) with unchanged HP/resources/state/RNG and one subsequent legal cast. Capture actual packet actor/source identities for any wrong death animation.

This is a risk inventory, not a claim that all listed risks are reproduced bugs or that the class is accepted as 3/18.

## Focused current-catalog follow-up: confirmed reachability and corrected leads

Source: `sacro-catalog-audit-20261009.json`, published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`. This is structural reachability, with exact criteria inspected; live combat outcomes remain separate.

### Sacrifice 5044: the ratio -2 gap does not affect this exported closure

The entire Sacrier closure contains exactly one family 1000 definition: **161467**, one parameter with pairs `[100, 0]`. `NativeRedirectRunnerHandler._calculate` consequently yields **ratio 100, on_target False**. The unsupported ratio -2 replay branch identified above is an engine restriction but **is not a current Sacrier missing implementation**.

Actual chain: roots 416705 and 416709 exclude carried targets; 416706/416711 install state 89 only when target lacks 6058, alongside scar 6058 and owner state 4800. State 89 installs listener **161466**, subscribed on native target-mask slot 1 event 2, criterion `not IsTriggeredByIndirectEffect() and GetTriggeringEffectActionId() <> 915`. Its ordered children are 161467 redirection and **196836**, which requires no existing target effect 196837 and positive triggering value. It registers **196837**, a one-duration delayed group with subscriptions 1015/1025 and event mask 1002; its child **161468/family422** swaps only if neither actor has fight property 11 and neither is carried.

Concrete acceptance consequence: direct damage must redirect to the original state caster, and the position exchange is a separately timed original child, not an unconditional immediate teleport. Indirect damage/action915 and zero triggering damage should not be treated as identical to positive direct damage. Duplicate marker prevention, delayed manager identity and owner/target preservation are the specific risks. State4800 listener **417169** removes owner state4800 and target state89 when caster HP is below10% or the owned sacrifice count falls below1; test that low-HP cleanup actually runs. Generic family1000 unit tests prove runner redirection arithmetic, not this complete deferred swap/cleanup chain.

### Refusal 5052: current data is threshold armor/reaction, not an unimplemented revival

Current 5052 closure families are `[80,304,330,400,430,1013,1047]`. It contains **neither family332 protected kill nor a revival runner**. Therefore a missing revival/protected-kill conclusion for this passive would be unsupported by current definitions.

Root **353207** subscribes to event2 and requires current HP>=20% with `HP - triggeringValue < maxHP*.20`. Child316715 further requires target total HP below20%, then316716 marker and316717 install state **3633 Muerte Acechante**. The state includes **353208/1047 →353209/1013 armor**, **353210/80**, and healing listener **353211**, whose criterion `(HP + triggeringValue) >= maxHP*.20` drives **353212/1047 →353213/1047 →353214/430** and353215 marker. Family430 is bound to `NativeTriggerValueHandler`, and1013 to the armor handler. Correct outstanding tests are exact below/equal/above20% damage and healing thresholds, armor consumption, source value mutation and once-only state transition. A suicide/lethal event must additionally prove ordinary death behavior, but should not be described as “Refusal revival missing” based on the name alone.

### Pact of Wakfu 7217: historical initialization rejection is insufficient

`passive-initialization-audit.md` records the old failure “Subscribed effect requires native event delivery” for **353414/family912**. Current `combat_effect_runtime.py` binds cost-based native group912 through `native_cost_group_level`; `combat_cost_level_group.py` implements family912 against actual paid signed-byte eWf costs; the live spell-cost/container branch belongs to family910. This is an implemented subscribed path with an authority contract, not a presently absent handler.

Root **353411** subscribes to1003 and feeds **353412/family999**, then353413 installs Vitality3231 at the derived group level. Separate **353414/family912** subscribes to60/2263 and feeds **417524/family1047** then417525. These subscriptions mean an initialization-only forced immediate execution cannot certify or disprove Pact: replay a legal equipped passive and actual qualifying payment event with its paid/native cost source, then inspect HP/vitality and post-event effects. The current passive audit verifies the startup vitality branch; complete cost-listener replay is not established.

### Confirmed missing definition: innate closure state 759

Unlike the ratio -2 and Refusal-revival leads, current merged metadata genuinely lacks **state759**. Innate3702 closure reaches three native304 installers with parameters `[759,0,1,0,-1,0]`: **316596**, under197716 requiring `GetTeamId(triggeringCaster) <> GetTeamId(target)` and event2; **316608**, under316606 requiring `maxHP(caster)*.02 <= level(6872,target)`; and **316615**, under316613 requiring `maxHP(caster)*.2 <= level(6872,target)`. These are ordinary team/HP accumulator conditions, **not literal False branches**. Removal316760 also references759 under316594.

Consequently this is a concrete metadata completion item affecting a conditionally reachable innate reaction. It is not proof every normal Sacrier hit fails: activation still depends on actual event subscriptions and state6872 progression. Recover the original state definition and its dependencies rather than inserting an empty placeholder, then replay the actual team/threshold paths and removal. The catalog audit reports no missing handler family in the overall934-effect closure; that count does not erase this absent state.


### Confirmed family421 dispel flag17 blocker; family321 is separate

Fresh passive activation reported by the validation agent reached **7224 Inmolación** and rejected with `Unaudited native dispel flags: [17]`. Exact flag-sensitive leaf **162668/family421**, parameters `[162664,0]`, removes an effect. `combat_dispel.py:19` validates flags against3/5/6/20/24 and rejects17 before application. This is a confirmed runtime engine gap.

The current reconciled Sacrier catalog contains **ten family421 definitions with flag17**: **160986** (removes160983, extra8586/innate3702), **162668** (removes162664,7224), **196951/196952/196957/196958** (remove196944/196945/196955/196956,5034 Tormenta Espiritual), and **283404/283472/283442/283389** (remove283403/283471/283441/283388, shared finisher dependencies). Only7224 has this fresh observed activation failure; others are structurally reachable conditional routes needing replay.

**Correction:** four family321 definitions also carry17 (160985,162669,196891,196894), but `combat_state_decurse.py` handles321 without calling `dispel_flags`. Their flag17 presence does not establish this rejection; Sacrifice5044's321 leaves must not be labeled blocked by421's validator. Fix421 semantics generally from original eXe evidence and test all ten definitions/root systems. Preserve distinct state-removal and effect-dispel ownership and event contracts.

### Pact cost/event source qualification

`combat_cost_level_group.py` distinguishes912/eYt from910/eYv. For912 a real `runner_class=eWf` supplies signed-byte `action_costs={ap,mp,wp}` and produces a float32 weighted total (weights parameter pairs6/7/8); non-eWf or absent source yields native override-1, preserving incoming level. It does **not** demand a spell container or resolve live fyF costs; those checks belong to910. `combat_cost_payment_events.py` explicitly wraps synthetic payment30 events with actual paid eWf costs and `spell_context.present=False`, so Pact must be tested against actual payment sources.

353414 subscribes to event IDs60/2263 in target-mask slot3. Numerical event60 must not be confused with replay channel60: `combat_cast_events._deliver` uses channel60 for external1024/1025 boundaries and supplies a null-source external event, which is not an eWf payment. Thus a successful generic after-cast event is not proof Pact received event60 paid costs. This review did not recover an intrinsic registry proof that every ordinary spell payment emits all desired60/2263/74 event IDs; do not claim those producers from matching numbers or from family912 binding alone. Current exact353414 export lists60/2263, not74. Any74 dependency requires its own definition/producer evidence.


The dynamically reconciled current intrinsic stat-event registry was also inspected: none of its listed runner event sets contains60,74 or2263. Therefore that registry does not independently prove Pact353414 producer delivery; actual eWf payment source instrumentation remains necessary. The reconciled catalog now includes1029effects/49spells/52states and5900profile, superseding the earlier934-effect structural-only scope where counts were stated above.

### Current Columnata5037 normal-entry branch rejection

The parent normal-cast review found rejected **self-targeted Columnata5037 at levels20 and200**: exact path **196997 →416129 →416131/family1013**, with armor target NPC **-7**, fails `Invalid native armor fight/target`. Record this as **two confirmed branch rejections**, not proof every Columnata cast fails: other prepared variants existed among the35 reviewed spell/level pairs. The validation agent is isolating whether the enemy died before armor execution or the nested branch received an incorrect target. Both are plausible explanations, not established causes. Preserve this exact source/target/level reproduction and compare actual effect flags, post-damage NPC status and group target transmission before changing armor eligibility or retargeting. No implementation fix or successful rerun is claimed here.

## Implementation follow-up (local source only; not deployed)

SAC-02: `combat_dispel.py` now accepts flag17 as an audited eXe no-op. Native `eVl` bytecode defines ID17 (`rwN`, ordinal15) as `BUFF_BYPASS_OUT_FIGHT_MAX`; original `eXe.c/E` does not read that flag or PA maxima. This preserves inherited generic trigger flags and does not change which retained effects are selected. The regression accepts17 while still rejecting17+6 without event lifecycle authority. Family321 is unchanged.

SAC-04: original `eWf.bbx` bytecode now establishes the missing cost publisher identity precisely: positive AP (`fMH`) emits55, MP (`fMG`) emits65, WP (`fMF`) emits60, fourth resource emits73. Constructor and reset set both special booleansfalse; `mh(true)` adds74 and `mi(true)` adds conditional2188/2234/2263. No original normal-cast caller setting those booleans was recovered, so the new general normal-spell receipt uses constructor defaults and **does not fabricate74 or2263**. Pact's60 alternative is sufficient to expose its paid-WP branch when all other native criteria pass.

Ordinary `combat_spell_transaction.py` formerly paid AP/MP/WP directly with no eWf receipt. It now replays already-paid preview costs through the existing `NativeCostPaymentEvents` adapter, post-application channels3/4 and original signed-byte source descriptor, before normal spell roots inside the active spell/cast transaction scope. No resources are paid twice, and all listener reactions/packets remain inside the unpublished preview and shared rollback/RNG boundary. The server placement before roots is explicitly a **Wakemu policy**, not recovered original server caller order. Minimal focused dispatchers without the retained event factory keep their previous behavior.

New `test_combat_paid_cost_events.py` verifies native event masks, zero/single/mixed payments, unchanged paid plan, same actor and UID-1 source, and invalid costs rejected before publishing. Focused actual Pact and cross-class regressions are delegated for fresh execution; compilation passed. Native evidence files: `.runtime/combat-review-20261007/eVl.javap`, `.runtime/eXe-subscription.txt`, `/tmp/sacro-eWf-javap.txt` (original client jar, `javap -c -p eWf`). No service was restarted or deployed.

### One-cast helper cleanup and native Cinetosis duplicate source

Current runtime isolation identified native416000 (before-cast1024) installing416001 with **removal mask index2=[1025]**. External1025 was previously delivered only on activation channels6/60/61; these cannot select mask2. The successful cast therefore left its one-cast helper retained and subsequent casts accumulated native416114/2128 reactions. The independently retired synthetic2128 fallback was an additional duplicate source, handled by the movement agent.

The general successful cast boundary now delivers1025 activation first, then native removal channels**4/40/41**, preserving local/reversed/global ownership and original subscription masks. This removal-phase producer is explicitly documented Wakemu policy because the original server external boundary caller is unavailable. It is not a per-spell deduplication or forced removal by reference. Interrupted casts never reach either successful1025 delivery; the entire preview and RNG remain under transaction rollback. Added actual Sacrier two-cast regression requires416001 creation on each normal5028 cast but no retained416001 after either; interrupted root255621 also checks unchanged original snapshot/RNG. Compilation passed; fresh runtime validation is pending.

### Terminal turn-start reaction ACK follow-up

The actual passive replay (`/tmp/sacro-passives-class11-current.json`, Inmolación7224,
`npc_pass_end_ack_own_start`) reached its family421 runner162668 successfully,
then failed with `No current duration owner`. This message comes from
`combat_turn_duration.current_turn_duration`, not retained effect expiration.
`RuntimeMessages.turn_started` already preserves reaction packets and returns
when callbacks leave no current actor, but `acknowledge_turn` unconditionally
armed a successor deadline (and could refresh a pending recovery packet).

The local correction gates recovery/deadline work after collecting the pending
ACK packets: a finished fight or absent current actor returns the committed
packets, clears deadline and pending recovery ownership, and does not invent a
successor. This is a server lifecycle policy, not a claim about an original Java
ACK implementation. A focused terminal ACK regression checks packet preservation
and cleared ownership; the actual20-passive replay is delegated for confirmation.
No service restart or deployment was performed by this audit agent.

Validation follow-up: Luna's fresh initialized gameplay run passed
`test_combat_sacro_pact_runtime`: paid WP reaches353414 exactly once,417524's
native1047 value produces real immediate7903 HP loss during417525, and a forced
child failure rolls back the fight and RNG. The persistent7903-state expectation
was removed because this runner consumes its immediate self-loss and expires;
no state was injected to satisfy the test. Luna also passed the terminal ACK
regression. The Cinetosis helper fixture requires a nonadjacent native-eligible
5041 target; its initial adjacent setup was rejected at range (`twI`), and the
collision audit owner is adapting the existing proven geometry before rerun.
