# Remaining six classes — refreshed inventory, 2026-10-10

The user provisionally accepts **12/18** classes. This refresh inventories the six remaining classes; it does not itself establish gameplay or manual acceptance. The current published and deployed catalog is `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`; the three-service deployment receipt reports World, AI and Ecology healthy on that pin. See [current closure status](current-closure-20261011.md) and [`LIVE_DEPLOYMENT.json`](../../monster-combat/bulk-1297-20261011/LIVE_DEPLOYMENT.json). The detailed class inventories and most class test artifacts below are historical snapshots (548, 677 or fede6) and must retain their own pins.

The integrated V14 gate ran **1,246 tests with 6 failures, 0 errors and 0 skips** on fede6, before the bd79 deployment. Five failures were stale literal catalog checks; those assertions were revised without removing behavior checks. Four supplemental selectors passed and are integrated with backups. The corrected V15.1 full18 run against bd79/current sources is now executing (coordinator PID 85147); its result is pending. The previously observed Rogue robot7952 movement discrepancy remains separately open. Neither the deployment receipt nor the historical V14 count constitutes six-class acceptance. The [closure ledger](current-closure-20261011.md) now lists finite next proofs and separates unqualified behavior from manual-only checks and original-server contract questions.

## Comparable estimates and suggested order

These are approximate reusable implementation estimates, with roughly **±10–15 percentage points** uncertainty, not measured spell success, automated coverage or manual acceptance. The common rubric allocates25 points to published/shared foundations,30 to core mechanics,30 to passive/secondary interactions and15 to lifecycle/client integration. Scheduling also considers complexity and unresolved integration risks.

| Order | Class | Estimated implementation | Main unfinished qualification |
|---:|---|---:|---|
| 1 | [Enutrof / Anutrof](enutrof.md) | 75% | Deposits: production, mining, upgrades, consumption and event10006; treasure/reward settlement; Drheller control and Perfórserker resource restoration. |
| 2 | [Steamer / Steamer](steamer.md) | 70% | Complete cast-to-Microbot-to-rail sequence; turret ownership/control; WP/SP conversion; both form transitions and passive branches. |
| 3 | [Sadida / Sadida](sadida.md) | 70% | Controlled doll swarm and books, Voodoll damage/armor links, poison/healing chains, multiple-owner death and cleanup. |
| 4 | [Rogue / Tymador](rogue.md) | 68% | Bomb timers, chains, walls and elemental conversion; simultaneous deaths; Tymobot control and resource HUD updates. |
| 5 | [Eliotrope / Selotrop](eliotrope.md) | 65% | Paired portal travel in both directions, routed LOS/range, movement cost and blocked exits; exaltation resources and portal lifecycle. |
| 6 | [Xelor / Xelor](xelor.md) | 65% | Dial center/hour production, AP theft/refund and delayed reactions, clock ordering, expiry and complete turn/death/reconnect lifecycle. |

## What the refresh establishes

Each detailed report inventories owned active/passive spells, granted actions, innates, states, resource consumers, areas and summon books where applicable. Each identifies its extraction scope: historical dependency graphs reconciled against current records are distinguished from freshly traversed current closures. All six have21 primary active spells; Enutrof has17 passives and the other five have20. Native empty summon books and literally disabled effect branches are not counted as missing gameplay.

Previously accepted classes contribute shared casting, conditional targeting, retained-effect safety, live summon properties, owner/controller identity, death retirement, multiplayer timeline/reconnect and cleanup paths. Steamer already has a real Microbot network and rail movement implementation. Enutrof already has deposit construction/grade and AP-as-MP routes. These advances improve implementation estimates but do not prove complete class semantics.

## Concrete concerns versus unverified behavior

- **Eliotrope:** the supported Gift→ally attack→giver back-attack path now positively qualifies Celada's conditional +60 branch. Native state3671 carrier cleanup/expiry remains unresolved: the observed cleanup selector targets the giver while the carrier is retained by the ally. This is a lifecycle boundary, not a missing Celada damage producer.
- **Xelor:** the prior bounded summon integration created14 of15 expected areas. The center production via effect352198/event2251 remains unresolved. Native empty summon books are unrelated to this concern.
- **Rogue:** the inspected explicit HUD resource adapter lacks breed13. Alternate producers must be checked before declaring the resource display broken; the robot7952 movement discrepancy also remains open.
- **Enutrof:** deposit event10006 delivery and actual prospecting/reward settlement remain unqualified; deposit construction is implemented.
- **Sadida and Rogue:** dedicated class semantic suites now exist, with stable Sadida 44/44 and corrected staged Rogue 9/9 evidence on release677. These are bounded historical suites, not bd79 runs and not complete client lifecycle acceptance.
- **Shared catalog/deployment:** the additive copied-book metadata is included in the published lineage and current bd79 service pin. This records catalog/service rollout only; the current V14 class gate and class manual acceptance remain outstanding.

No new enabled missing handler was demonstrated merely from roster presence, native empty data or literalFalse branches. Remaining qualification must include positive and negative conditions, every passive branch that is enabled in this catalog, resource caps, rejected-action rollback, death, reconnect and a second fight.

## Automated evidence and limits

Luna's historical **36/36** seven-module run covered shared Xelor casting/passives, portal casting, rail movement, Microbot network/path and deposit lifecycle. It is shared primitive evidence, not six complete class pipelines or a bd79 run. Later class-specific aggregates are listed in the current closure ledger; the latest integrated V14 full18 run is **1,246 tests, 6 failures, 0 errors/skips** and needs its corrected repeat.

## Current follow-up

Do not schedule from the original inventory order as if implementation had not advanced. The immediate acceptance gate is the corrected full18 rerun against bd79/current sources; keep Enutrof event74 and Rogue robot7952, plus Eliotrope state3671 carrier cleanup, visible as individual boundaries. Manual client acceptance follows only after the automated result and deployed-source alignment are recorded.
