# Remaining six classes — refreshed inventory, 2026-10-10

The user provisionally accepts **12/18** classes. This refresh inventories the six remaining classes; it does not itself establish manual acceptance. The current published and deployed catalog is `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`; the three-service deployment receipt reports World, AI and Ecology healthy on that pin. See [current closure status](current-closure-20261011.md) and [`LIVE_DEPLOYMENT.json`](../../monster-combat/bulk-1297-20261011/LIVE_DEPLOYMENT.json). The detailed class inventories and most class test artifacts below are historical snapshots (548, 677 or fede6) and must retain their own pins.

V16 actual-checkout execution is a historical, source-drifted result against catalog `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`: its durable receipt records 1,239 `ok`, two Sadida assertion failures and three session-cleanup fixture errors among 1,244 cases, while 44 server Python paths changed. Its structured summary separately has `setup_error: KeyError 4398584640`; use the per-case receipt for those historical counts. The later no-overlay V4 closure passed257/257 selected tests against the same catalog; both Sadida selectors are green. V4's one source-pin mismatch was `combat_effect_runtime.py`; it is a historical coherence limitation, not a current demonstrated defect. Same-dispatcher receipts passed135/135 and a separate 8140 branch6/6 at SHA `817ed895…`. The tracked `environment_seat=None` session fixture correction passed5/5. The Sacrier Ready selector passed. Xelor's inverse and2237 future-hour boundary selectors passed2/2 in V3 with stable source hashes. The complete area-query module passed6/6 against current runtime SHA `92c91d7a…` and dispatch SHA `fddbafd0…`, bd79 start=end, with no source drift. Older Xelor V1/V2 failures are historical and superseded for these selectors. Controller+Xelor28/28, Flags15/Xelor18/18, and Rogue robot6520/7951/7952 remain qualified. The V17 coherent full gate is in progress; no terminal result is claimed here. All six are ready for provisional manual acceptance, which has not yet been performed. See the [closure ledger](current-closure-20261011.md), [publication handoff](remaining-six-publication-handoff-20261011.md), and [`LIVE_DEPLOYMENT.json`](../../monster-combat/bulk-1297-20261011/LIVE_DEPLOYMENT.json).

## Comparable estimates and suggested order

These are approximate reusable implementation estimates, with roughly **±10–15 percentage points** uncertainty, not measured spell success, automated coverage or manual acceptance. The common rubric allocates25 points to published/shared foundations,30 to core mechanics,30 to passive/secondary interactions and15 to lifecycle/client integration. Scheduling also considers complexity and unresolved integration risks.

| Order | Class | Estimated implementation | Technical status | Main remaining qualification |
|---:|---|---:|---|---|
| 1 | [Enutrof / Anutrof](enutrof.md) | 75% | **READY_FOR_PROVISIONAL_MANUAL** | Event74 source contract and reward lifecycle remain explicit caller/manual boundaries, not demonstrated defects. |
| 2 | [Steamer / Steamer](steamer.md) | 70% | **READY_FOR_PROVISIONAL_MANUAL** | No current class-specific defect is established; perform form/rail/turret/resource/reconnect checks. |
| 3 | [Sadida / Sadida](sadida.md) | 70% | **READY_FOR_PROVISIONAL_MANUAL** | Both V16 failure selectors pass in V4; the separate 8140 branch receipt is 6/6. |
| 4 | [Rogue / Tymador](rogue.md) | 68% | **READY_FOR_PROVISIONAL_MANUAL** | Robot6520/7951/7952 qualified; finite7065/7090 coverage limits remain explicit. |
| 5 | [Eliotrope / Selotrop](eliotrope.md) | 65% | **READY_FOR_PROVISIONAL_MANUAL** | State3671 receiver cleanup is an unresolved ownership contract, not a confirmed defect. |
| 6 | [Xelor / Xelor](xelor.md) | 65% | **READY_FOR_PROVISIONAL_MANUAL** | Both hour-boundary selectors pass V3; perform clock/resource/lifecycle checks. |

## What the refresh establishes

Each detailed report inventories owned active/passive spells, granted actions, innates, states, resource consumers, areas and summon books where applicable. Each identifies its extraction scope: historical dependency graphs reconciled against current records are distinguished from freshly traversed current closures. All six have21 primary active spells; Enutrof has17 passives and the other five have20. Native empty summon books and literally disabled effect branches are not counted as missing gameplay.

Previously accepted classes contribute shared casting, conditional targeting, retained-effect safety, live summon properties, owner/controller identity, death retirement, multiplayer timeline/reconnect and cleanup paths. Steamer already has a real Microbot network and rail movement implementation. Enutrof already has deposit construction/grade and AP-as-MP routes. These advances improve implementation estimates but do not prove complete class semantics.

## Concrete concerns versus unverified behavior

- **Eliotrope:** the supported Gift→ally attack→giver back-attack path now positively qualifies Celada's conditional +60 branch. Native state3671 carrier cleanup/expiry remains unresolved: the observed cleanup selector targets the giver while the carrier is retained by the ally. This is a lifecycle boundary, not a missing Celada damage producer.
- **Xelor:** both current-hour boundary selectors now pass in V3; remaining center/reactive source branches stay bounded as caller/coverage questions. Native empty summon books are unrelated to those boundaries.
- **Rogue:** the inspected explicit HUD resource adapter lacks breed13. Alternate producers must be checked before declaring the resource display broken; robot7952 paid-facing/PUSH1 is now qualified by the integrated28/28 bd79 receipt.
- **Enutrof:** deposit event10006 delivery and actual prospecting/reward settlement remain unqualified; deposit construction is implemented.
- **Sadida and Rogue:** dedicated class semantic suites now exist, with stable Sadida 44/44 and corrected staged Rogue 9/9 evidence on release677. These are bounded historical suites, not bd79 runs and not complete client lifecycle acceptance.
- **Shared catalog/deployment:** the additive copied-book metadata is included in the published lineage and current bd79 service pin. This records catalog/service rollout only; the current V16 shared gate and class manual acceptance remain outstanding.

No new enabled missing handler was demonstrated merely from roster presence, native empty data or literalFalse branches. Remaining qualification must include positive and negative conditions, every passive branch that is enabled in this catalog, resource caps, rejected-action rollback, death, reconnect and a second fight.

## Automated evidence and limits

Luna's historical **36/36** seven-module run covered shared Xelor casting/passives, portal casting, rail movement, Microbot network/path and deposit lifecycle; it is shared primitive evidence, not a six-class result. V16 remains historical source-drifted evidence (1,244 cases, 1,239 `ok`, two Sadida assertions, three extracted fixture errors, 44 paths changed), not a coherent all-green gate. The later actual-checkout V4 run passed **257/257** on bd79, with one of50 source pins mismatching at the time; both Sadida selectors were green. Separate dispatcher receipts passed135/135 and8140 6/6. The session fixture correction is tracked (`c03db97d…`) and its five-case receipt passed; Sacrier Ready passed. Xelor's inverse and2237 future-hour boundaries passed2/2 in V3 with stable source hashes and bd79. A current full final gate is in progress; its result is not yet available. All six are ready for provisional manual acceptance. Manual checks remain unperformed; no100% completion claim is made.

## Current follow-up

Do not schedule from the original inventory order as if implementation had not advanced. All six are ready for provisional manual acceptance. The current full shared gate is in progress; V16's source-drifted 1,244-case receipt remains historical, while V4's 257/257 focused closure and later area-query6/6 are scoped receipts. Keep Enutrof event74, Rogue finite7065/7090 variant coverage and Eliotrope state3671 carrier cleanup visible as caller/coverage boundaries, not confirmed defects. Manual procedures can proceed independently of the full gate.
