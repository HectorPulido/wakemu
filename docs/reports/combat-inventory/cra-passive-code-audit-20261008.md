# Cra passive current-code audit

Read-only audit of **breed 9: 19 passives and innate 3419** on 2026-10-08. No runtime changes, scenarios, tests, service operations or execution certification were performed. Names retain the installed ledger localization; IDs define scope.

Two concrete integration findings emerge: eZi321 removes states but omits its produced runner events (including 2288), and external event 1010 has a Cra subscriber but no explicit current production origin. The second finding does not establish what native transition should produce1010; it must not be replaced by a guessed death event. No absent effect handler or absent textual condition route was found in the inspected core.

## Scope and denominator

The core typed compact closure has 331 effect references and 325 original metadata rows. It follows child order, 304→state,649→granted spell, 315→area, and 307→the exact initial states of profiles 3798/3799/3800 (their native action books are empty). The older metadata projection omits six beacon-state rows; this is an export limitation, not a demonstrated runtime omission.

The broader [current data inventory](cra-code-dependency-inventory-20261008.json) includes 21 active spells, 19 passives, 6 granted spells and both innates3419/4464. Its 1198 effects/42 states/46 spells/3 profiles/1 area include shared cosmetic branches from 4464. That broader union has zero missing runtime effects/states/routes/casting metadata according to the independent data inspection. It is not a claim that 1198 mechanisms were individually reviewed here.

## Proven incomplete code

1. **State reduction/removal loses source events.** [NativeStateDecurseHandler](../../../server/wakfu_server/combat/combat_state_decurse.py:16) implements removal/reapplication but has no runner preparation, lifecycle phase emission or event_lifecycle provider. [Factory binding](../../../server/wakfu_server/combat/combat_effect_runtime.py:1361) supplies reapply only. Effects 350821,347121,352099,352104 and 352262 advertise produced 2288; innate 3419 listener 398436 listens to 2287 and 2288 and executes 398437/398438 for state 7792. By comparison, [304 phase production](../../../server/wakfu_server/combat/combat_state_handler.py:186) forwards PK masks. The retained wrapper does not emit these phases on the handler’s behalf. This is missing reaction propagation, not missing removal.

2. **External1010 has no owned producer.** Listener 351404 (criterion `GetTeamId("caster") <> GetTeamId("target")`) executes 351405/395194. Original eFK explicitly lists 1010 as external. Current death policy emits 1013/channel6; searching all server Python yields 1010 only in corpse-bypass/restore-strategy consumers. No original transition/channel is inferred. This is a bounded producer gap requiring a source-backed policy, not evidence that1013 capture delivery is wrong.

## Per-passive code classification

“Present” below means the referenced code route/provider exists and was inspected; it does not mean manually or automatically tested. Marker 400 is intentional: the innate and conditional tables read the passive from the actual deck.

| Passive | Direct mechanism and shared dependencies | Current code finding |
|---|---|---|
|6945 Arquero Astuto|marker 400; innate/dependency deck checks 350803,352326,352660,352661,352662; casting refs 7807|Routes present; no specific omission proved|
|6946 Explorador Especializado|marker 400; innate/dependency deck checks 394942,395195|Routes present; no specific omission proved|
|6947 Balizas Discretas|marker 400; innate/dependency deck checks 348453,348454,348455,349649,397179|Routes present; no specific omission proved|
|6948 Tomar Partido|marker 400; innate/dependency deck checks 395864,395870,395876|Routes present; no specific omission proved|
|6949 Distancia Focal|marker 400; casting refs 4769,4809,4810,4811,4812,4813,4814,4815,4816,4817,4818,4819,4820,4821,4822|Routes present; no specific omission proved|
|6950 Precisión Voraz|marker 400; innate/dependency deck checks 352101,352264; casting refs 7752|Routes present; no specific omission proved|
|6951 La Senda del Arquero|families 31,41,56,57,193,304,321,330,400,447,451,649,1020,1083; innate/dependency deck checks 394946,394947|Routes present; shared321 produced-event gap in closure|
|6952 Desbalizaje Masivo|marker 400; innate/dependency deck checks 350809,350810; casting refs 6349|Routes present; no specific omission proved|
|6953 Estudio Balístico|marker 400; casting refs 4807,7792,7793|Routes present; no specific omission proved|
|6955 Paradoja del Ocra|marker 400; innate/dependency deck checks 394942|Routes present; no specific omission proved|
|6956 Explorador Intocable|families 176,177,330,913|Routes present; no specific omission proved|
|6957 Instinto de Cazador|families 330,430; casting refs 4807,7792,7793|Native direct listener350835 criterion False; keep disabled; casting checks present|
|6958 Balizaje Cercano|marker 400; casting refs 4807,6349,7792,7793|Routes present; no specific omission proved|
|6959 Tirador Solitario|marker 400; innate/dependency deck checks 350882,351587,394942|Routes present; no specific omission proved|
|6960 Mente Aguzada|marker 400; innate/dependency deck checks 350815,350819|Routes present; no specific omission proved|
|6961 El Arte de las Balizas|marker 400; casting refs 4807,7792,7793|Routes present; no specific omission proved|
|6962 Tiro Divergente|families 304,330,400,447,912,1093; innate/dependency deck checks 395232|912 branch348490 is native False; other alignment/1093 paths present|
|6963 Perforación Ocra|marker 400; innate/dependency deck checks 350801,350802,352337|Routes present; no specific omission proved|
|7795 Flecha Protectora|families 80,321,844|Routes present; no specific omission proved|

## Current shared providers inspected

- [Native conditional casting selection](../../../server/wakfu_server/combat/combat_native_spell_casting.py:17) evaluates full tables; [ordinary target validation](../../../server/wakfu_server/combat/combat_cast.py:115) resolves the selected range and calls the shared native casting query. 6949 supplies range/LOS changes across 15 elemental spell definitions; 6961 supplies beacon LOS changes;6953/6957/6958 alter beacon costs/range/eligibility. These are not missing merely because their direct passive root is 400.
- [Condition evaluator](../../../server/wakfu_server/combat/combat_conditions.py:949) and [actual range provider](../../../server/wakfu_server/combat/combat_runtime_adapter.py:411) supply enemy/ally count, actual affiliations and native in-play metadata. Actual deck/exclusion comes from OrdinaryActorAuthority, rather than accepting passive names as class-wide defaults.
- [Current retained-condition evidence](../../../server/wakfu_server/combat/combat_runtime_adapter.py:246) supplies HasEffectWithSpecificId/ActionId from owned carriers; state predicates retain their first-match/source semantics. Unknown authority remains a rejection, not false success.
- [Cast boundaries](../../../server/wakfu_server/combat/combat_cast_events.py:66) deliver 1024/1025 with active spell context; [start boundary](../../../server/wakfu_server/combat/combat_start_events.py:14) delivers 1028/1003; turn start/end/regeneration delivers1001/1002/1037. These origins explicitly document Wakemu server policy instead of claiming a missing original server caller was recovered.
- Damage/resource/state produced events 2/74/79/2287 are supplied by their actual runner paths; direct source events are separate from external lifecycle boundaries. Preserve native literalFalse branches and retained subscription/channel ownership.

## Evidence format

The companion JSON contains every core effect reference per seed, state dependencies, families, exact deck-condition reverse references, conditional casting expressions, source hashes, condition route lines, family bindings and issue anchors. The six incomplete older metadata rows are explicitly separated from runtime data availability. No “not tested” entry is counted as absent code.

## Shared cosmetic follow-up: implemented server policy

The broader innate4464 cosmetic boundary is now implemented through the explicit `wakemu.owned-finisher-boundaries-v1` policy. Events1018/1012/1015 use the original subscription/removal masks and real lethal source; no recovered original external publisher is claimed. A real owned initialization/cast test reaches original1099 leaf185395, assigns script1100010 to victim-7 before lethal damage, then presents12727/state2 before cleanup13560 with newer delivery action IDs. This bounded automated positive-tree result is not manual client acceptance. See [native finisher boundary](native-finisher-event-boundary-20261008.md) for the source limits and general relativefKX/replay corrections.
