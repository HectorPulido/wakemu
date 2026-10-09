# Native conditional casting restrictions

## General scope and current source

The class-reachable casting catalog has 851 references. Forty-six have conditional tables that change LOS; the complete inventory is `class-conditional-los-inventory-20261007.json`. This includes class-linked actions and owned summon abilities, rather than only the base 722 named class spells. No monster spell population was exported for this review.

Casting restrictions belong to the complete selected fyP: costs, minimum/maximum, LOS, cardinal/diagonal constraints, straight-path option, free-cell rule, modifiable range and self-target permission. The current normal source selects this table against the current authoritative condition context **before geometry**, then applies native range and shared fcj checks. It does not perform a baseline LOS ray or walkable-cell check first. This differs from the earlier source described in `range-review-20261007.md`; that historical blocker was removed by the shared casting integration.

The native bytecode `fyF.a(fyG,Object,Object,Object)` obtains the selected table and returns its cwL. When selected LOS is false, fcj uses actual QI.j target-surface eligibility; it does not query fcr. Removing LOS therefore does not remove native bounds, range, target-surface, free-cell, criterion or selector requirements. Alignment and cwV straight-path checks remain independent selected restrictions.

Every request obtains fresh actor aliases from the current state ledger and owned deck authority. No selected table is cached across state changes. The casting catalog itself is immutable cached data; the state-dependent selection is performed for every request. Normal diagnostics now expose the actual selected restriction flags and effective range alongside the ordered rejection stage.

## Native example, without relying on translation

The installed Spanish spell namespace has no Ocra spell named “Flecha Perseguidora”. Original spell 4813 is `content.3.4813 = Flecha Buscadora`. It is the Ocra action whose LOS table changes with `HasState(7757,"caster")` and `GetStateLevel(7792,"caster") >= 30`.

These are **state** identifiers: `content.8.7757 = Tiro Preciso`, `content.8.7792 = Precisión`. Spell 7792 is separately named Baliza de Contacto in `content.3`; that shared numeric value must not be confused with the state namespace.

For 4813, LOS is false only when both state prerequisites hold. Passive 6949 changes the selected range from 4–9 to 6–11; it does not remove the state threshold. The four original conditional tables explicitly cover passive on/off and threshold met/unmet. Removing Tiro Preciso or reducing Precisión to 29 restores LOS on the next request.

Ocra linked action 4807, Baliza de Destrucción, has another conditional LOS change from owned passive 6961. Both use the shared complete-table mechanism; no spell-ID exception was introduced.

## Offline verification and limits

`ProbeNativeConditionalLos.java` calls the installed original 4813 definition's **fyF.a**, with typed eHg state authority and actual fyG level. It passed 36 combinations of levels 1/20/200, Tiro Preciso present/absent and Precisión -1/0/29/30/31/100. Its actor is explicitly non-eGj, so native deck membership is false; this oracle establishes the original state threshold and selected LOS, not player deck serialization.

`test_combat_conditional_los` checks the installed complete tables across 72 player-state/passive/level combinations, reselects after state/threshold loss, and verifies the general geometry routing: selected LOS true queries the ray; false queries QI.j without a ray. Together with `test_combat_casting_range`, six test methods pass.

No server was restarted, no client session was run, and no current running-world behavior is certified. This source verification does not prove that the running process has loaded the changes or that client state packets contain the correct current levels. The general manual obstacle acceptance plan must verify conditional restrictions on/off and state removal across complete systems. State acquisition/consumption and packet-level synchronization remain separate acceptance evidence.
