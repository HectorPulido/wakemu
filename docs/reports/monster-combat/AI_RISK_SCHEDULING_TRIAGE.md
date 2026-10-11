# Native risk scheduling after monster acceptance

Read-only investigation, 2026-10-10 local time. No production code, original tests, services, or database contents were changed for this investigation.

## Observed decisions

The world JSON log contains 45 tactical actions after 2026-10-11T00:15Z in fights 178–181. Two fight178 actions are fallback decisions without protocol3 risk evidence. The remaining43 decisions belong to Wonejo179 (9), Tofu180 (24), and white Jalato181 (10).

| Fight | Decisions | Alternative forecasts | Complete forecasts | Rival actions expanded | Forecasts with positive known risk |
| --- | ---: | ---: | ---: | ---: | ---: |
|179|9|44|0|0|1|
|180|24|132|0|1|0|
|181|10|57|0|1|0|

All233 alternative forecasts report `rival_search_deadline_reached`. Therefore these logs do not establish that the monsters compared complete native glyph risks and deliberately preferred danger. They establish that the forecasts were incomplete. One Wonejo and one Tofu decision skipped rival forecasting altogether.

Private evidence: `.runtime/monster-local-unit-20261010/latest-risk-raw.json`, `latest-risk-summary.json`, and `latest-risk-query-timings.json`. The last file includes operation-level calls, total/max wall time, decision slice, risk reserve, actual risk time, and owner budget for every decision. These files contain live-session data and are not publication artifacts.

## Budget mechanism and evidence

`query_search.update_turn_budget` sets the decision wall slice to `(nativeBudgetMs - commitReserveMs) * searchTimeFraction`, with defaults500ms and0.25. Rival search reserves `min(500ms, decisionSlice * 0.25)`. Every shortlisted alternative shares one risk deadline. The root baseline is evaluated first; its full forecast can consume the remaining window before any alternative is projected.

Maximum individual `project_turn` times in the recorded decisions are approximately80–146ms for Wonejo,80–198ms for Tofu, and80–444ms for white Jalato. The cost includes native lifecycle processing. Repertoire, rival previews, multiple rivals, and transport add further cost. A white Jalato decision used3010ms in rival search despite a500ms reserve; synchronous requests are not preempted when the deadline passes.

The last white Jalato decision had a1203.49ms own slice and300.87ms risk reserve. Its single `project_turn` cost375.55ms, including328.65ms in `projection_boundary`. No rival action was expanded. The root and its alternatives all remained unknown.

The first Wonejo decision had a2195.69ms decision slice but7868.73ms native wait, used the mandatory root-action reserve, and skipped risk search. This is distinct from an evaluated hazard preference.

## Scoring asymmetry

When every forecast has lower bound0 and uncertainty25, the baseline bonus25 and alternative uncertainty penalty25 cancel. Ranking then follows ordinary damage, resource cost, coordination, and distance utility.

There is also an asymmetric case: Wonejo179 turn6 has a root baseline with certified end-turn lower bound0.5, while the selected movement from[-15,-6,-1] to[-14,-6,-1] has no certified response and lower bound0. The baseline contributes25.5 and the unknown alternative loses25, yielding an extra0.5 for an alternative whose safety was not evaluated. Unknown lower bound0 must not be interpreted as evidence that the alternative is safer than a baseline with observed damage.

## Lifecycle result discarded on deadline

`query_threat.forecast` obtains `projected` from native `project_turn`, but initializes `outcomes=[]`. It records actors only after a further native `preview:end_turn` or rival candidate succeeds. If projection itself crosses the deadline, certified lifecycle HP/resource changes in `projected.actors` are absent from the estimated lower bound. The comment says lifecycle deltas remain part of the response, but that requires a subsequent successful query in the current implementation.

This is a code-level limitation, not proof that a particular acceptance glyph dealt damage at that boundary. Proving individual glyph damage additionally requires the corresponding graph and native event trace.

## Minimal general improvement to evaluate

Separate native lifecycle risk from optional rival action search. First project the root and best own alternative, retaining each successful projection's consequential actor deltas immediately. Only then spend remaining time on rival attacks, with round-robin alternative scheduling. A third retreat alternative is useful only when time permits. Compare alternatives at equivalent coverage; missing rival exploration must not create a safety bonus relative to a baseline with known damage.

A scheduler alone cannot guarantee two completed projections within an unchanged deadline: a synchronous native query can exceed all remaining time. A real guarantee needs a bounded/cancellable native operation or a bounded batch lifecycle query. Otherwise expose insufficient coverage explicitly and preserve the deadline rather than claiming two alternatives were assessed.

Proposed independent regression tests, preserving existing assertions:

- Projection reduces actor HP, crosses deadline, and returns a certified lifecycle lower bound while rival completeness remains false.
- Two alternatives receive lifecycle projection before either receives optional repertoire/attack expansion.
- A baseline with known harm and an unprojected alternative do not produce a spurious safety improvement.
- A slow projection prevents a second query after deadline and records incomplete coverage honestly.
- Known-safe and known-harmful lifecycle outcomes rank by native damage when both are evaluated, independently of enumeration order.

Tofu retreat and beacon preference remain separate policy concerns. Current generic distance utility rewards approach, and summoned opponents are legal targets; these logs alone do not justify species-specific retreat rules or ignoring summons. No such rules were added.

## Narrow correction and focused verification

Following review, `query_threat.forecast` now records the native `project_turn` actor outcome immediately, checking that every existing actor remains represented. A deadline reached after that query leaves the forecast incomplete but retains its certified lifecycle lower bound. Rival ordering places registered summons after primary enemies; every living enemy still receives a detail row, including explicit unknown rows when the deadline is exhausted. End-turn ordering and the broader search scheduler were not changed.

New tests in `server/ai-service/tests/test_native_risk_projection.py` cover retained7HP lifecycle harm after deadline, rejected missing actors, and primary-enemy-first scheduling with truthful incomplete summon coverage. Original tests remain unchanged.

Command: `PYTHONPATH=server/ai-service:server/ai-service/tests .runtime/local/verification-venv/bin/python -m unittest test_query_threat test_native_risk_projection`.

Result:11 tests passed in0.012s. This verifies the narrow coroutine behavior with a fake native provider; it does not certify live glyph avoidance or solve alternative scheduling fairness.

## Conservative comparison of unevaluated alternatives

The planner now compares partial forecasts with an explicit coverage imputation. For each rival, an incomplete response with zero expanded actions receives at least the highest certified lower bound observed for that rival among the evaluated alternatives. This prevents the live baseline-risk=0.5 versus unevaluated-move-risk=0 case from rewarding missing work. The imputation changes ranking only: native forecast damage, lower bounds and completeness remain untouched. Diagnostics expose `coverageImputation` and a separate utility component; the adjusted diagnostic score matches the selected score.

Six new regressions cover unknown-vs-known comparison, distinct rivals, complete zero risk, actual explored differences, unchanged unknown status and a complete search case which would otherwise spend MP solely for a spurious safety advantage. Existing tests are unchanged. The combined final isolated batch passes 186 tests, including source guards, turn/context contracts, target priorities, risk projection/coverage and static-cache behavior. This does not guarantee full rival exploration or Tofu hit-and-run under the existing deadlines.

## Post-cast repositioning memory

The native NPC producer emits `npc_cast` with `actor_id`, `spell_id`, `target_id`, and `turn_id` only (`combat_npc_spell.prepare_validated_npc_spell`). The complete graph retains `runtime.fight.events` and `runtime.fight.turn_id`, so committed-cast history can survive a fresh plan after movement without external AI state. Filter both actor and current turn; older casts and another actor's casts cannot latch the current actor's phase.

A cast event proves a successful native cast transaction, not damage: empty and support casts also produce it. A future helper should be named accordingly. Offensive outcome changes remain native-preview evidence. Repositioning must preserve useful offensive/support continuations and avoid assuming an enemy's future reach from geometric distance alone. Current-turn memory can prevent approach/retreat oscillation after re-planning, but is not itself evidence that retreat is safe or that remaining attacks are useless.

`test_native_hit_and_run.py` adds three separate graph-authority characterizations (fresh encoding after movement, actor/turn history, and empty-cast limitations). Command: `PYTHONPATH=server/ai-service:server/ai-service/tests .runtime/local/verification-venv/bin/python -m unittest test_native_hit_and_run`. Result:3 passed in0.001s. No movement policy or original test was changed by this investigation.

The implemented root-owned memory helper additionally requires positive `damage` attributed to the actor followed by its committed `npc_cast` in the current turn. Native `turn_started`/`turn_ended` events reset the latch; another cast closes pending damage. The new tests now exercise that real helper rather than a copied detector. They also verify bounded post-attack distance preference (maximum1.5 position units), that5HP offensive benefit outweighs the maximum retreat bonus, and that retreat-first candidate ordering retains approach routes. This is a positional preference, not a proof of enemy reach or glyph safety.

Focused command: `PYTHONPATH=server/ai-service:server/ai-service/tests .runtime/local/verification-venv/bin/python -m unittest test_native_hit_and_run test_query_search`. Result:64 tests passed in0.067s. All existing query-search assertions remain unchanged.
