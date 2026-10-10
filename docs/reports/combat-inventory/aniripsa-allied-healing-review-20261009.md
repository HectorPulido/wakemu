# Aniripsa ANI-02 allied healing and Vínculo

## Scope and source inputs

`test_aniripsa_allied_healing_runtime.py` exercises original spell 779 and 781 through `prepare_server_spell` after production Ready/class initialization. It reuses the aptitude healing fixture, with optional deck and persisted initial-wound arguments; existing defaults are unchanged. Wounds are character HP installed before Ready, not combat characteristic edits. Runtime cases use the actual player snapshot, state catalog and native effect factory.

The published Aniripsa catalog gives spell 779 a cost of 3 AP, and spell 781 a cost of 2 AP plus 1 WP. Spell 781's criterion is `not IsEnnemy() and not IsTargetCellFree() and not HasState(3864, "target")`. Its roots 166867/167529 decurse states 3864/3890 and 166868 applies 3864. The tests check the actual resulting state rather than a synthetic state application.

## Prepared regressions

- Injured self and allied player: real healing, bounded HP, exactly one AP payment, unchanged source transaction.
- Full-HP ally: no HP overflow and native AP payment.
- Allied Vínculo: state 3864 plus AP/WP payment; hostile rejection leaves the source resources/events unchanged.
- Numeric consumption: signed-int maximum healing saturates HP then virtual HP; frozen HP redirects only available virtual capacity; healing resistance respects actual bounds and frozen/disabled guards.

## Verification status

Python compilation passed. Runtime validation is queued with the shared DB-capable validator. A host numeric invocation stopped during catalog imports because host Python lacks `psycopg`; no assertion ran. This report does not certify gameplay or manual acceptance, and no service was restarted.

Area-edge healing, additional spell branches, repeated linked-heal lifecycle and resources across a real turn cycle remain outside these first six regressions. No production semantic change has been made on the basis of an unexecuted test.
