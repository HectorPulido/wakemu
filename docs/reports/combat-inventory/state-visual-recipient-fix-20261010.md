# Native state visual recipient binding

## Incident and proven cause

The live Dragon Form cast logged both state 7123 visual children 326546 and 326547 as `no_effect`, while its ordinary point-area child 325961 completed. These two family-400 null runners carry the sex-specific `APPEARANCE_CHANGE` actions 4776/4778 and `CHANGE_HEIGHT` actions 4777/4779. Their area is `anA` (empty), with `fcE` selector mask 1. Enumerating that area produces no targets, so the sex criteria and evaluated-effect delivery are never reached.

The shipped client's `eZk.c(Qe,boolean)` initializes each immediate state child with a null target at bytecode offsets 215–263, then checks the parent `bbA()` at offsets 307–329 and calls `child.g(parent.bfs)` before `bal()`. `eZk.bbA()` returns literal true. `Qe.g(PV)` calls `d(Collections.singletonList(PV))`: the state recipient is already selected, without consulting area, selector or `aZX` again. The server instead explicitly reset target selection on state installation.

## General correction

`EffectInvocation.native_preselected_target` represents this distinct `Qe.g(PV)` contract. Immediate state roots use the actual state recipient; subscription registration retains its existing event-specific targeting. The resolver validates actor scope and source identity, then selects the bound recipient. This flag is consumed before the handler executes, so a group root's children retain their own area and relationship selection. This is separate from `native_explicit_target`, which models an argument to `Qe.a` and still consults `aZX`.

Retained family-400 delivery, UID ownership, state removal and reconnect payload persistence continue through their existing shared paths. No spell IDs, sexes or appearance action IDs are hardcoded in the correction.

## Validation and limits

Focused `test_combat_effect_resolver` and `test_combat_state_handler` passed 21 tests before the final one-shot dispatch regression. The final resolver suite passed 9 tests, including that additional regression: an explicitly bound state recipient does not constrain subsequent area children. Tests cover empty-area selection, `aZX`, ally versus caster/self selection, absent targets, and native state-child binding. The broader gate and owned Dragon transaction audit are tracked by the coordinating agent.

The native parser and bytecode contract establish the missing delivery cause; they do not constitute proof of rendered graphics. Manual acceptance must activate Dragon Form for both sexes, verify appearance and height, remove/reapply the state, reconnect while active, and finish combat with the base appearance restored. Existing combat damage, healing, group areas and subscriptions must remain unchanged.

Cross-class published-catalog scope is documented in [the visual state inventory](class-visual-state-recipient-inventory-20261010.md). Its complete scan found 205 visual effect/state ownership pairs across 95 states; only these two Dragon roots matched the exact empty-area and mask-1 failure.

## Final production-path offline audit

The shared gate passed **174 tests, zero failures/errors/skips**, in86.123s.
Full log: `.runtime/osamodas-incident-20261010/final-regression-visual-state.log`.
Actual7349 transactions for sex0 and sex1 installed state7123 at2AP, selected
respectively visual326546 and326547, and rejected the opposite sex branch.
Both delivered12613 with the owned visual runner. The active-effect reconnect
projection preserved its exact generic effect, UID and payload hash without
mutating the fight. Returning from Dragon removed state7123 and delivered13560
for that exact visual UID, leaving no visual row. Artifacts:
`.runtime/osamodas-incident-20261010/dragon-visual-sex-0.json` and
`dragon-visual-sex-1.json`. These checks do not exercise real socket reconnect
or graphical rendering. No deployment or restart occurred.
