# Cra beacon, spellbook and movement code audit — 2026-10-08

Scope: current source and native catalogs, breed 9. No test execution, service operation or runtime edits. The companion JSON preserves 150 native effects from eleven relevant states, including criteria, level intervals, subscriptions and child references. “Implemented” below means the concrete code route exists; it is not a live-client acceptance claim.

## Three beacons

| Action | Creation effect | Native profile | Constructor states |
|---|---:|---:|---|
| 7793 | 348206 / family307 | 3798 | 7781, 1304 |
| 7792 | 348181 / family307 | 3799 | 7780, 1304 |
| 4807 | 150421 / family307 | 3800 | 7779, 1304 |

Native definitions are present in granted-spell-effect-trees and native-class-summon-initial-states. The307 route constructs the native profile, installs its real characteristics/book and initial states before controller/QI registration. `combat_summon_initialization.py:72` executes actual detached constructor PVs; `:116` suppresses only their redundant network outbox because the client constructor reconstructs those same initial states. This does not skip server state installation.

`combat_summon_handler.py:165` records the insertion point and `:216` inserts creation before the child packets. `combat_summon_codec.py` uses `combat_entity_creation_delivery.py` to send evaluated12613 with execute=true. This is necessary for immediate creation: `combat_retained_runtime.py:1163` finds no retained record and skips normalization, so the earlier13497 creation could not be repaired by that normalizer. This previous defect is fixed in current source.

Post-creation roots select `IsOwnSummon(profile)`, copy HP and resistance/mastery characteristics using913 groups, apply state7778, and apply the passive-dependent property below. For7793 these roots include348207,348208/348209,348210,350788,348455; for7792:348182,348183/348184,348185,350787,348454; for4807:150428,150429/151553,150431,177981,348453. Shared913/1047 child-level selection is wired at `combat_effect_runtime.py:930`; stat families are registry-bound at `:655`. Actor stats are serialized from actual registered summons (`combat_summon_stats.py:7`), including active-session snapshots (`combat_session_adapter.py:425`).

The direct elemental children of constructor states are357567/fire,357565/air,357566/earth, each with native criterion `False`. They are not missing automatic damage handlers: those definitions intentionally cannot execute. Beacon-related reactions must follow real class subscriptions/parent casts, not activate these false leaves.

## Balizas Discretas6947: line of sight, not invisibility

Passive6947 has a400 marker root348456. The functional branches are348455/348454/348453, family447, parameters[54,0], criterion `IsSpellInDeck(6947,"caster")`. Native property54 is **DONT_BLOCK_LOS**, category1/counter. It is not either invisibility property5 or18. The native beacon profiles initially contain properties1,11,114,47,15; neither5 nor18 is present.

The route is complete in source: `combat_fight_property.py:83` validates447, `:105` resolves actual registered/detached PV, `:135` increments the actual PB counter, and `:161` sends12613 with immediate versus retained execution policy. `combat_casting_los.py:29` reads current properties and excludes54 from LOS obstacles. `combat_obstacle_condition.py:11` independently keeps actor visibility separate from LOS blocking. Removing the retained447 row reverses its counter and delivers13560 (`combat_fight_property.py:165`). Thus the current code supports a visible beacon that does not obstruct LOS. No source evidence in this subset establishes that6947 should hide its actor.

## Automatic book and temporary7807

Innate3419 has subscription347168/event1028. Its649 children grant native bar2 slots0–4:347172→7752,348180→4807,348232→7793,348231→7792,347173→6349. Each has the actual guards `not HasEffectWithActionId("caster",933)` and `GetInstanceId() <> 862`. These actions are not inferred from the normal deck or injected as UI-only spells.

`combat_effect_runtime.py:592` registers649. `combat_spell_grant.py:47` evaluates native bar/slot/ref/level, `:115` records the native raw-reference object, `:152` delivers evaluated12613(false), and `:156` removes the object and emits13560. The runtime overlay preserves raw UIDs and distinct player progression (`combat_spell_grant_book.py:35`). Active reconnect uses complete retained replay via `combat_session_adapter.py:456`, rather than a separate partial649 list. Ready takes the pre-initialization baseline (`combat_ready.py:36`) then delivers initialization; combined actor snapshots send13912 before12873 (`combat_runtime_messages.py:300`) to preserve characteristics after client effect reset.

State7776 root351782 executes348170 and349693;349693 grants7807 in bar2/slot5 under the morph933 guard. State7777 is Flecha Luminosa, not the granting649 itself. State3430 reaches7777 through352662/352661/352660 when6945 is in deck. Actual7807 roots351408 and349680 execute1083 damage,3436 application and321 removal of7776/7777. Innate3419 also has351403 gated by `GetActiveSpellId()==7807`, event1024, with descendants351404/351784; other321/421 cleanup branches are retained in the JSON. Family1083 is in `combat_damage_healing.py:10`;321 is wired at `combat_effect_runtime.py:1361`; activated421 has the actual clone preparation hook (`combat_dispel.py:86`). No absent grant/removal handler was found in this route.

## Movement actions

| Action | Native path | Current code |
|---|---|---|
| Voltereta4774 |149442/302, criterion not PB11 and target cell free;352919/41 maximum-resource branch |302 is teleport_caster (`combat_displacement.py:18`), preflight/registration at:312/:373, native packet12613 at:121;41 is bound at `combat_effect_runtime.py:383` |
| Retirada Balizada4805 |149678/302 target-cell-free;243755/402 graphical null-cell runner | Same teleport route;402 registered at runtime:576 and implemented in `combat_cell_null.py:49` |
| Explorador4806 |352258/330→352259/126 and352260/844 (HasState7792)→352261/304 state3430,352262/321 state7792/event2288 | Registry stat route:655;844 level provider:925;304/321 retained handlers:1301/:1361 |

Explorador's older151534→151535→150486 state3433 branch has native criterion `False` at its root. Its nonexecution is not a missing movement implementation. Explorador's live352258 branch is a characteristic/state operation; treating every action named movement as a teleport would misclassify the native definition.

## Concrete gap classification

One concrete shared gap was established:321 does not publish native event2288 after state decurse. `combat_state_decurse.py:71` removes actual children/carriers, sends13560 and records the Python `state_removed` event at:89, but never invokes native2288 subscriptions. The current combat source has no2288 publisher. This affects Explorador effect352262 removing Precision7792, Precision state7792 effect350821 (level201–300), and innate3419 root398436 listening2287/2288. The state removal itself exists; the subsequent native reaction chain is incomplete. This is not a missing321 handler. No other absent handler or necessarily failing provider branch was established in this subset. The previous immediate307 delivery/order defects are now corrected in source. Remaining explicit generic guards (for example subscribed402 clones at `combat_cell_null.py:62`, or447 event clones at `combat_fight_property.py:87`) do not match the listed direct Cra definitions, so they are not counted as Cra gaps. Raw13497 for402 is a graphical null operation, not evidence that teleport302 failed; the movement packet is separately12613.

The JSON records exact data rather than converting unexecuted scenarios into missing mechanics. No code or services were changed for this audit.
