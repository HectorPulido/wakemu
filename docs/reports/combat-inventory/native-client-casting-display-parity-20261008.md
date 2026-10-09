# Bulk client tooltip and target-mask range comparison

The current installed native contract has two distinct consumers: `bPO.elJ` renders the tooltip maximum, while `fcO`/`fcj.a` validates the actual target mask. Their differences must not be corrected by making the server use the tooltip formula.

The [bulk result](native-client-casting-display-parity-20261008.json) covers all18 classes and813 class-owned/granted references, every exported positive level and level0, baseline and conditional tables. All records are present and input hashes remained stable. The tool reads only the small casting catalogs; it does not load runtime effect catalogs, connect a client, or repeat the earlier native range oracle.

| Comparison | Evaluations |
|---|---:|
| All selected tables/levels |359168|
| Seven input snapshot scenarios |2514176|
| Tooltip and target-mask maximum equal |2024628|
| Native carried extra range difference |112914|
| Native property2 range cap difference |223376|
| Maximum below1 skips target-mask RANGE adjustment |148830|
| Tooltip clamps to minimum independently |4428|

These are formula/input scenarios, not reachable gameplay cases or a defect count. The probes use RANGE−3/0/+3, category adjustments0/+2/−2, carried presence and property2. The actual actor/state/equipment producers still determine which combination can occur. Results are indexed by class; concrete native spell/level/conditional-table examples are in the JSON.

For example, spell623 at level1 has minimum1/maximum4 and modifiable range. A carried input yields tooltip4 versus target-mask5; property2 instead yields tooltip4 versus mask1. Spell636's fixed conditional minimum3/maximum3 combined with category−2 yields tooltip3 versus mask1. These reproduce the previously proved native consumer distinction across real exported definitions.

There are286 references with conditional casting branches. The tooltip supplies a null target during table selection, whereas a cast supplies the actual selected target/cell. A table-by-table formula comparison cannot establish that both consumers select the same branch. A visible discrepancy must therefore record whether it concerns a tooltip value, highlighted target mask, or server acceptance, plus the actual target, state levels, carried status, category modifiers and RANGE snapshot.

Current source review still finds the shared server casting path using the selected complete conditional table, live RANGE11 and category map with Java integer wrapping. Characteristic and category packets have separate producers; their earlier54 primitive parity checks do not prove active reconnect reconstruction. The [delivery review](native-range-client-delivery-review-20261008.md) records that independent reconnect boundary. No new incorrect current range arithmetic was demonstrated by this bulk comparison.

Costs are independent of range. Targeted original `fyF`/`fyQ` disassembly reads AP/MP/WP from the selected native cost table; it does not itself transfer AP to MP for property50. The native PB50 guard and state702 conditional cost tables are a separate shared casting dependency being integrated by the owning agent. Neither a range fix nor a tooltip change may invent that resource conversion.

Regenerate with:

```sh
PYTHONPATH=server .runtime/local/verification-venv/bin/python server/tools/audit_client_casting_display_parity.py --output docs/reports/combat-inventory/native-client-casting-display-parity-20261008.json
```
