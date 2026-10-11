# Remaining six classes — refreshed inventory, 2026-10-10

The user provisionally accepts **12/18** classes. This refresh inventories the six remaining classes; it does not implement mechanics, activate catalog changes, restart services or accept another class. The authoritative read-only PostgreSQL release is `548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd`.

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

- **Eliotrope:** the inspected movement and area-event paths did not reveal a paired portal crossing that relocates the actor. This is a scoped source-review gap requiring a complete traversal test, not proof that no alternate path exists anywhere.
- **Xelor:** the prior bounded summon integration created14 of15 expected areas. The center production via effect352198/event2251 remains unresolved. Native empty summon books are unrelated to this concern.
- **Rogue:** the inspected explicit HUD resource adapter lacks breed13. Alternate producers must be checked before declaring the resource display broken.
- **Enutrof:** deposit event10006 delivery and actual prospecting/reward settlement remain unqualified; deposit construction is implemented.
- **Sadida and Rogue:** no dedicated doll/Voodoll or bomb semantic test modules were found. Generic summon or area checks cannot certify these chains.
- **Shared catalog:** a copied-book metadata correction was validated separately but remains inactive; preserve the current monster release when eventually publishing it. It is not silently counted as deployed here.

No new enabled missing handler was demonstrated merely from roster presence, native empty data or literalFalse branches. Remaining qualification must include positive and negative conditions, every passive branch that is enabled in this catalog, resource caps, rejected-action rollback, death, reconnect and a second fight.

## Automated evidence and limits

Luna ran **36/36 existing tests**, seven modules, zero failures/errors/skips: Xelor casting/passives, portal casting, rail movement, Microbot network/path and deposit lifecycle. Source/test hashes remained stable. Evidence: `.runtime/remaining-six-refresh-20261010/README.md` and its logs/hashes. This is shared primitive coverage, not six complete class pipelines. The earlier182-test shared/class gate remains separately scoped; neither result certifies the global repository suite or all six classes.

## Next implementation target

Enutrof is the suggested next class. Complete owned-action integration and passive/lifecycle qualification before promoting it. Steamer and Sadida follow; Rogue, Eliotrope and Xelor require more complex chain/routing/time integration. No implementation has been started by this refresh.
