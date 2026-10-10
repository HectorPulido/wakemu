# Osamodas Dragon-form self-cast damage incident — 2026-10-10

## Live failure

At `2026-10-10T15:59:14Z` (10:59:14 in Bogotá), Osamodas actor 19 cast Látigo 7317 on its own cell in fight 161. The caster was at `[-12,-4,-1]` with state 7123 (Forma Dracónica); the adjacent Wonejo was at `[-13,-4,-1]` with 10 HP. The cast was accepted and spent 4 AP, but the Wonejo stayed at 10 HP. The trace is request `92d9783057ee46f1aa0e86a3722f142e` in `.runtime/local/logs/game-server.jsonl`.

The native root 326119 is the Dragon-form AoE branch. Its condition is:

```text
HasState(7123, "caster") and (GetEffectCaster() == GetEffectTarget() or
    (HasStateFromUser(7134, "target") and IsOwnSummon("target")))
```

The selected self-target cell reached this root with `target_id=null`; the condition trace recorded `skipped_condition`, so its damage children never ran. The cell had been deliberately selected as the AoE center. Clearing the fighter recipient for cell-area delivery had also erased the native raw-cell argument needed by the condition evaluator. This was a server-side target-context defect, not evidence that the low-resistance Wonejo merely displayed stale HP.

## Shared correction

The native cell resolver now retains an explicit `native_target_cell_argument` marker when `eZR.I` delivers `bft` with no selected `bfs` fighter. The condition adapter resolves the cell's first registered QI fighter for criteria while preserving the raw-cell context. Before child actor selection, the resolver clears that marker, so child effects resolve their own selected actors and do not inherit the parent's cell criterion. This keeps the area center and the effect's selected recipient as separate native inputs.

The correction is generic; it does not special-case Osamodas, spell7317, root326119 or Wonejo. The relevant source is `server/wakfu_server/combat/combat_effect_resolver.py`, with cell-condition adaptation in `combat_runtime_adapter.py` and `combat_casting_context.py`.

## Validation

The `server/tests/test_combat_osa_dragon_aoe_runtime.py` runs actual Osamodas class initialization, the native Ready-granted Dragon action 7349, state 7123, and the published spell trees. It places enemies on valid map 1134 QI surfaces and self-casts both Látigo 7317 and Tormenta de Arena 7312. Both casts damage the adjacent enemy while leaving an enemy five cells away unchanged. Without state 7123, the self-cast is rejected and actor HP remains unchanged.

The same runtime test now performs **three Dragon→Osamodas→Dragon cycles for each sex**. Every Dragon transition checks state 7123 and the sex-selected retained appearance runner (326546 for sex 0, 326547 for sex 1), its state-owner UID, and its 12613 delivery. Every return checks the exact 13560 removal UID/payload, the absence of state and visual runners from the fight checkpoint, and rejection of the Dragon-only self-cast after reverting. The first Dragon cycle also confirms self-centered Látigo damages the adjacent enemy. **4/4 tests passed with zero skips** in `.runtime/osamodas-incident-20261010/dragon-aoe-roundtrip-module.log`; the test respects the native two-table-turn interval by advancing through runtime turn boundaries.

After the initial-facing correction and expanded round-trip tests, the same focused gate passed **117/117 tests with zero failures/errors/skips in 71.649 seconds**. Final log: `.runtime/osamodas-incident-20261010/final-dragon-context-five-classes.log`.

The earlier focused shared gate covering conditions, effect target resolution, area entry/query/selection/events, captured-area activation, effect dispatch, state handling, and the selected Cra, Iop, Sacrier, Aniripsa and Osamodas production regressions passed **115/115 tests, with zero failures, errors or skips, in 63.141 seconds**. The gate used PostgreSQL's active native catalog revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`; log: `.runtime/osamodas-incident-20261010/dragon-context-focused-five-classes.log`. It used catalog reads only; no game-state database writes, service operations or deployment were performed.

The automated casts cover the self-centered Dragon branch. A real captured invocation used as the AoE center is not covered by these fixtures, so no conclusion is made about that separate ownership branch.

## Initial facing and Dragon rendering

The client log records `Animation Not found (players.jar!/26) 0_AnimStatique` immediately after Forma Dracónica casts at 11:29:57.360 and 11:31:20.260. Both Dragon rigs (26 and 27) contain idle clips for directions 1 and 5, but not 0. Native `YJ.en` prefixes the animation with the actor's direction; `aqj.s` returns without selecting a clip when that exact name is absent. This explains an invisible rig with an unsupported idle, consistent with the report that movement reveals the Dragon.

Fresh controlled actor creation previously forced direction 0 in ordinary PvE, hero admission, combat joining and duels. These paths now use a shared cardinal initial facing (1), also used by the Dragon runtime fixture. `combat_bootstrap.player_payload` now explicitly serializes the actor's actual direction instead of silently defaulting to 0. Existing orientation actions, later movement, and cast-facing rules remain authoritative; transformation does not force a new orientation or invent an animation fallback.

The initial-direction gate ran 14 tests with zero failures/errors and three isolated-PostgreSQL skips: hero, join and duel integration assertions were added but not executed in that environment. Bootstrap tests check both initial direction 1 and explicit direction 5 in the packet. Six orientation tests and the four Dragon runtime tests passed. One pre-existing orientation/unarmed integration fixture was excluded because it lacks complete native QI population. Log: `.runtime/osamodas-incident-20261010/player-initial-direction-gate.log`.

This prevents the demonstrated unsupported initial idle on fresh combat entry; it does not establish that every intermittent appearance report has the same cause. The repeated server-side transition test proves visual-effect selection, delivery, removal, and checkpoint cleanup, not rendered frames. A fresh-fight rendered acceptance test in both directions and an actual socket reconnect while transformed remain pending. Existing fights restored with direction 0 are not migrated by this change.

This correction is local to the current checkout. It has not been deployed or manually accepted in the client.

Native capture and facing provenance: [Dragon appearance facing capture audit](dragon-appearance-facing-capture-audit-20261010.md).
