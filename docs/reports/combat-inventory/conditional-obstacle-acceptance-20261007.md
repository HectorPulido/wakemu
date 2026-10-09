# Conditional obstacle and casting acceptance

## Reported failure

Hector reports that Cra's “Flecha Perseguidora” cannot pass through walls while its special state is active. The translated name must be matched to the installed spell identity before attributing the failure to a definition. This is an open gameplay report, not a verified fix.

The subsequent [native conditional restriction review](native-conditional-casting-restrictions-20261007.md) identifies 46 class-reachable references with conditional line-of-sight tables. Installed spell4813, Flecha Buscadora, changes LOS when state7757 (Tiro Preciso) exists on the caster and state7792 (Precisión) is at least30. The original implementation passed36 state/level comparisons. The current source selects the conditional table before geometry; the earlier baseline-LOS blocker was removed by shared casting integration. These findings do not establish the running process's version or client state synchronization, and do not conclusively identify the translated name in Hector's report.

## Shared requirements

Conditional casting must select the native rule using the actual caster, state levels and passive deck. That selected rule must reach the ordinary casting validator and any independent client eligibility publication. Baseline flags must not overwrite the selected conditional result.

Removing line of sight does not by itself remove range, line/diagonal restrictions, destination occupancy, target selectors or resource costs. Each restriction must retain its independent native authority. A wall between caster and destination differs from selecting the wall as the destination.

The regression family must cover:

1. No required state: an intervening native obstacle rejects the cast when baseline line of sight is required.
2. Required state below the native threshold: the obstacle still rejects the cast.
3. Required state at the threshold and above: the selected no-line-of-sight rule admits an otherwise legal destination beyond the obstacle.
4. State removal or expiration: the next cast uses the baseline rule again.
5. State on another actor: it must not activate a caster-only condition.
6. Each relevant passive branch: use its actual selected table, preserving costs and range.
7. An illegal destination or insufficient resources: no-line-of-sight permission must not bypass the unrelated rejection.
8. Transaction failure: no cost, state or retained effect is partially published.

Use real native QI obstacle surfaces and casting metadata for integration cases; flat synthetic maps cannot establish wall behavior. Compare the selected flags with the original native implementation and test the entire set of class spells with conditional line-of-sight entries, rather than installing a spell-ID exception.

## Verification boundary

Automated verification is offline. Server/client live parity and the reported gameplay sequence remain pending Hector's final whole-system acceptance. No restart, deployment or container operation is authorized by this document.
