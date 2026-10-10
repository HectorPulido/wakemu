# Aniripsa runtime risk inventory — 2026-10-09

Inventory only. No gameplay implementation, database mutation, deployment or service restart was performed for this review. Code and published native definitions were inspected; class gameplay evidence comes from the companion baseline reports, not an invented manual acceptance result.

## Findings first

1. **Anisurrección1535 has a concrete resurrection lifecycle gap candidate.** Its resource handlers exist, but no complete owned resurrection producer was found. Neither level20 nor200 was rejected in the baseline: both lacked an eligible off-play ally and were never cast. This must be verified with an actual defeated allied fighter before declaring the ability broken or complete.
2. **Ally healing, marks, summon choices and conditional passive reactions remain insufficiently exercised.** The32/35 ordinary spell-level pairs and60 committed attempts are useful transaction coverage; they do not cover the three unavailable ally/KO pairs or all conditional branches.
3. **Contra Natura is a native state toggle and explicit effect graph.** The generic undead-healing guard must not be mislabeled its missing implementation: no family447/property20 application occurs in the current Aniripsa closure.
4. **No missing definitions or absent factory bindings were found in the current closure.** This proves catalog/routing presence, not end-to-end behavior.

## Evidence and limits

The companion `aniripsa-catalog-audit-20261009.json` reads published catalog revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`. The catalog artifact SHA256 at this review is `51cb408bfcb4bd4647f711533d56794e1ab7a337590032c285066030c52c827b`. Its current ownership is breed7,21 active and20 passive spells. The expanded dependency graph contains52 spells,974 effects,51 states,4 summon profiles and2 areas; missing definitions and absent factory bindings are empty. These counts include shared dependencies and are not counts of directly selectable class abilities.

`aniripsa-validation-current-20261009.md` records four legal Ready deck chunks,32/35 ordinary spell-level pairs prepared/committed,60/60 prepared attempts committed,20/20 passive cycles completed with only3 activations under their available conditions, and34 existing healing regressions passed/1 optional skipped. Anisurrección1535 at both levels and Vínculo de Amistad781 at200 had no eligible recipient. Grant references7977/7978/7979 are outside the ordinary-spell denominator.

## Resurrection: exact dependency and lifecycle distinction

The current1535 root at level200 is166893, family330. Native casting criterion is:

`(IsOffPlay("target") and not HasFightProperty("target", 66) and not IsEnnemy()) or #IsBreedId("target", 5162)#`

The root itself requires `IsOffPlay("target") and not IsEnnemy()` and runs these ordered children:

| Effect | Native definition | Existing implementation and remaining question |
| --- | --- | --- |
|166894|196, no parameters, flag15, fcE129/pointanD|`combat_current_hp_restore.NativeCurrentHPRestoreHandler` calculates default HP1 and writes PA. Does that actor also regain authoritative in-play membership? No producer establishing that was found.|
|167897|25, parameters30/0,2/0,4/0, no flags, fcE129/pointanD|`combat_healing_handler.NativeHealingHandler` supplies ordinary healing after the preceding HP write. A nonzero HP field alone does not restore corpse/population authority.|
|166895|304, state1144 level1, permanent, flag15, fcE129/pointanD|`combat_state_handler` installs Convaleciente; its permanent target clock and listener must survive a proper resurrection.|

State1144 contains149448 (family447, property66, flags9/15) and163833 (family330, flags9/15, subscription1010/1013), whose child163835 is family28 kill with flag15. The listener compares the triggering target with its caster, requires same teams and distinct target/caster. Thus second death/KO and original resurrection ownership need explicit testing, not simply a positive HP assertion.

`combat_current_hp_restore.py` and `combat_restore_strategy.py` explicitly distinguish resource assignment/`eGz.pHO` from death/population. The triggered1010 strategy sets only `restored=True`; its own source comment states that it neither clears death status nor changes fdy/QI. `combat_native_death_status.py` understands transition1, and `combat_death.py` documents12727/state1 as resurrection, but this review found no owned1535 producer coordinating that transition, global fighter status, QI, timeline reinsertion and client delivery. `Fight.apply_effect_healing` rejects zero-HP targets and explicitly keeps resurrection separate.

The generic flag15 healing guard (`Native KO healing lifecycle is not implemented`) is real, but167897 has no flag15. It is therefore **not** evidence that this exact1535 child takes that guard. Its root first invokes196. A real ally-corpse scenario must inspect the whole chain, not infer failure from a generic guarded branch.

## Healing, damage and conversion

Shared implementation exists in `combat_damage_healing.py`, `combat_healing_parameters.py`, `combat_healing_handler.py`, `combat_damage_handler.py` and `combat_ordinary_authority.py`. It separates elemental healing families, mastery/final modifiers, actual HP/virtual-HP gain, overflow, frozen resources and characteristic32 healing resistance. Ordinary authority enables healing resistance for players or the relevant native world property; an ordinary NPC is not automatically equivalent to a player. Healing publishes preparation/application phases1/2/3/4 and passes actual consumed value to callbacks.

Future verification must include a wounded ally, self, enemy, full-HP recipient and Cunejo; repeated healing must increase resistance only where the native authority allows it. Check caster/recipient heal modifiers, critical, area versus single-target, heal mastery, distance/melee and frozen HP. Existing arithmetic tests establish formulas but not every Aniripsa branch or client presentation.

Contra Natura7977 uses166896→367570/371819 and a separate toggle branch367556→367557/367559. The false-state branch applies3867 through367558; the true-state branch removes3867 through367560 and8020 through367640. Other branches apply8020 and check7992/7998, teams and carrying. This is an effect/state graph, not blanket inversion of every heal. Test its granted availability, both toggle directions, every elemental spell before/after, ally versus enemy and the deck-dependent Transgresión/Ambivalencia branches.

The generic `consume_healing` undead/property20 conversion deliberately rejects without a verified eXt damage branch, and ordinary authority derives undead from property20. No current Aniripsa family447 definition applies property20. This remains a cross-system limitation for an externally undead target, not a proven absent Contra Natura route.

## Marks, death events and reaction identity

Current mark/death consumers include367423/367427 (family330, HP<1, subscription1010) in the Marcaje Preciso644 closure, and Cunejo closure371989/371994/371999 (subscription1010, Naturaleza Muerta5455 and Súper Cunejo7991 deck criteria). Presence of listeners does not prove the relevant mark was installed or an actual death delivered.

`combat_death_events.deliver_owned_death` preserves the lethal running source, validates registered OFF_PLAY death, records the event before synchronous replay and suppresses duplicate sequence delivery. It publishes the local1013 boundary plus consumer-backed1010 caster/target/global routes. These producer channels and ordering are explicitly Wakemu server policy; native consumer masks/criteria are source evidence. Do not describe the server policy as recovered original server code.

Highest-risk tests are two Aniripsas marking one enemy; owner versus teammate versus summon lethal hit; indirect versus direct damage; multiple marked victims in one area; nested death damage killing a second victim; corpse after displacement; and victory from a delayed reaction. Check each mark pays/heals/damages once, names the right actor and leaves no corpse blocker or duplicate listener. Normal damage to an unmarked enemy does not cover these routes.

## Cunejo, grants and ownership

Published profiles182/1775/5528/5533 have ability books, initial states and characteristics. Granted7977/7978/7979 come from649 effects367635/367636/367637 with native conditions including real level>=6, non-morph and instance<>862. This does not make them unconditional active deck entries.

Shared summon creation/initialization/spellbook/count/retirement infrastructure exists in `combat_summon_handler.py`, `combat_summon_creation.py`, `combat_summon_initialization.py`, `combat_summon_spellbook.py`, `combat_summon_count.py` and `combat_summon_retirement.py`. Ordinary creation propagates caster owner/controller unless the native specification is self-controlled; retirement validates exact registration and only removes the appropriate QI entry after outer-chain settlement.

Cunejo includes AI-control family325 consumers367593/368072/368088/368097/371802/371811 with `IsOwnSummon(profile)` criteria. These are AI controls, not recall effects. The generic325 handler is registered in `combat_effect_runtime.py`. Test every profile selected by the actual passive/state conditions, autonomous turns and spellbook, control switching, owner death/disconnect, repeated summoning limit, summon death and replacement on its former cell. Do not infer all profiles work from a successful ordinary Ready.

## State and passive lifecycle

Generic304 application,321 state removal,421 selective dispel, retained subscriptions and native actor/global ownership are present. Permanent and turn-clock states must be checked on the correct owner, especially allied buffs and summon effects. The20 completed baseline cycles prove cycle stability;17 passives without observed activation remain conditional gameplay work, not absent passives.

Use each passive's actual catalog criterion to construct a legal scenario. Cover ally healing thresholds, over-heal, deck restrictions, mark consumption, Cunejo variants, turn-start/end delayed effects and state removal. Check no repeated cast or reconnect accumulates one-cast helpers or stale grants.

## Reusable Cra, Iop and Sacrier work

| Shared work already implemented | Relevance and required Aniripsa follow-up |
| --- | --- |
|Atomic spell previews and RNG rollback|Fail a nested heal/mark/summon child; retain resources, states, roster, packets and RNG exactly.|
|Authoritative QI/LOS and corpse retirement|Attack/heal behind walls, after death/displacement and around summons; do not count retired actors as blockers.|
|Caster/target selection and nonpoint fresh-child server policy|Protect intentional point targets in1535 while enumerating actual area recipients for marks/heals. Test two allies/enemies rather than one actor.|
|Native cost receipts|Paid resources and triggered effects must use the real once-paid receipt; special event variants must not be invented.|
|Successful1025 removal delivery|Ensure temporary cast listeners expire after activation; interrupted transactions retain rollback.|
|Native death delivery identity and settled reactions|Correct victim animation, mark owner, lethal source, once-only cleanup and final outcome.|
|Terminal turn-start ACK guard|A delayed heal/damage/summon reaction ending combat must deliver committed packets without rearming a nonexistent turn.|
|Multiowner participation/readiness/recovery and finish cleanup|Two-player PVM/PVP, reconnect, surrender and dungeon progression remain acceptance conditions.|
|Generic421 flag17 semantics|Definition presence still requires each conditional branch to execute; do not apply421-specific claims to321/325.|

## Targeted next acceptance systems

1. **Two real allies and an enemy:** all ally/self healing, full-HP behavior, resistance growth, Vínculo781 and modifiers. Record before/after HP, resistance, states and resources.
2. **Contra Natura and complete deck:** before/after each elemental ability on ally/enemy, both toggles, granted spells and dependent passives.
3. **Marks and real deaths:** two owners, direct/indirect/summon kills, area multi-kill, nested lethal reaction and last-enemy victory; record exact listener IDs and source identity.
4. **Cunejo variants:** native summon choices, control/AI, spellbook, limits, death, replacement cell, owner reconnect/death and retirement.
5. **Anisurrección:** keep another ally alive so the fight remains active; defeat a real allied fighter; cast1535 legally on its registered corpse. Assert HP, state1144/property66, global status, QI occupancy, timeline/controller,12727 transition1, movement/casting and second-death behavior. Never manufacture onlyHP0 as a substitute.
6. **Lifecycle resilience:** delayed reaction on a turn ACK, victory/surrender, two-owner reconnect and next dungeon room. Assert no stale combat UI, blocked turn, vanished world group or stranded participant.

These are future complete-system probes. This inventory does not authorize an assertion that all conditional branches or client behavior already passed.

## ANI-01 local implementation follow-up

Implementation was subsequently authorized. New `combat_resurrection.py` supplies
the general inverse lifecycle for a flagged196 runner restoring an actual
registered OFF_PLAY corpse. It requires its existing owned QI slot; it does not
resurrect a finally OUT_OF_PLAY/retired fighter or guess a slot from HP alone.
The196 handler captures that authority before PA writes and completes the
inverse before post-application reactions. Ordinary living196 restoration is
unchanged. The complete operation remains inside the existing transaction
preview and RNG rollback boundary.

Additional original-client evidence was inspected with JDK22 javap:

- `aTS` state1 calls `buH.be(big)`; `aTS.F` clears the death flag.
- `buH.be` calls `fbX.D`.
- `fbX.D` invokes `fem.rD` unless the native no-timeline property applies,
  then delegates to `fcb.D`.
- `fem.rD` removes the saved `feu` removal record, reads its saved position,
  reinserts the identity and updates the timeline.
- `fcb.D` calls `fdt.bu` (IN_PLAY) and `eGj.baH`; HP assignment itself is
  still separate in `eXO.fPy`.

The source-linked pairing of a successful flagged196 HP restoration with that
state1 publisher is an explicit Wakemu server policy because the original
server publisher is unavailable. It is not claimed to be JavaeXO behavior.
The implementation restores timeline membership/counters while preserving the
current actor, consumes the saved removal record, changes actual fighter/death
status and emits12727/state1. `RuntimeMessages.prepare_delivery` clears the
previous death-report suppression only when that resurrection packet is
published, allowing a later actual death of the same identity to be delivered.

`test_combat_resurrection_runtime.py` constructs real three-player snapshots and
an adjacent registered Wonejo5525, uses its owned7962 damage roots to defeat an
allied player, then invokes actual1535. It checks failure rollback during166895,
HP/state1144, QI slot, timeline/current owner, death status, state1 publication,
a legitimate restored owner's next-turn request and subsequent real death
publication. Automated execution is delegated to Luna and remains pending at
this update. No services were changed.

Controlled OFF_PLAY corpses retain their indexed, movement-blocking QI slot
(`combat_qi_fight.py`); native teleport/forced obstruction checks inspect that
slot without filtering by IN_PLAY (`combat_displacement.py`). Thus ordinary
movement cannot place a second fighter onto the corpse cell. Revival does not
invent relocation: original `fcb.D` does not contain such a placement branch.
Explicit native movement overrides/ignored slots are a separate untested
intersection. The resurrection regression also checks the exact reinserted SY
counter and single timeline/base-order membership. A preexisting base-order
entry is preserved rather than inserted twice.

The current implementation deliberately requires an owned saved timeline row
for an absent target. Native property114 skips `fem.rD`; revival of such
non-timeline actors is not yet covered by this implementation or regression.
Final OUT_OF_PLAY actors whose QI slot was retired are also outside the tested
OFF_PLAY restoration boundary.
