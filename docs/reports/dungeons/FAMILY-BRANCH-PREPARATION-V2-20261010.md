# Local family encounters on native branched terrain — V2, 2026-10-10

This source-only preparation resolves 13 of the 19 baseline physical-graph blockers, producing 33 encounter stages. It does not alter runtime data, combat, spells or client assets. PostgreSQL lifecycle approval is tracked separately.

## Explicit local policy

The generator groups parallel native gates connecting the same terrain regions into one frontier. It selects the mandatory entry-to-exit gate spine when possible. If exterior exits are near the entrance, it selects the deepest directed-reachable native gate-separated region as the local final encounter and proves the walking return to the literal native exterior approach. This is a local stage order, not a reconstruction of official room order.

Every native terrain cell, edge and gate ID is retained. Annex regions share their gate-separated stage; their gates open with that stage. A directed reachability counterexample check rejects any topology where future encounter terrain is reachable before its frontier opens. Each stage uses family members from the native dungeon pool, with the identified actual boss reserved for the final stage. Six-player combat formation, encounter engagement, locked/open frontier movement and native exterior exit paths are checked.

## Results

| Dungeon | Status | Stages | Blocker |
| --- | --- | ---: | --- |
| Blópera | offline_configuration_prepared | 2 |  |
| Base del Susurro | offline_configuration_prepared | 3 |  |
| Ciudad Prohibida | blocked | — | Native six-player combat formation fails at every tested monster quantity (8, 6, 4, 3, 2, 1); anchor search remains possible. |
| Mazmorra Abráknida | offline_configuration_prepared | 3 |  |
| Mazmorra iBúho | offline_configuration_prepared | 2 |  |
| Mazmorra de Anutropía | offline_configuration_prepared | 2 |  |
| Mazmorra Ferocirraptores | offline_configuration_prepared | 2 |  |
| Mazmorra Pezgajosos Abisales | offline_configuration_prepared | 3 |  |
| Mazmorra Riktus de Élite | blocked | — | No directed-reachable native bridge-separated final region |
| Mazmorra de los Idos | offline_configuration_prepared | 2 |  |
| Mazmorra Tripulación del Pulpo | offline_configuration_prepared | 2 |  |
| Mekafábrica | blocked | — | Native six-player combat formation fails at every tested monster quantity (8, 6, 4, 3, 2, 1); anchor search remains possible. |
| Patapinxería | offline_configuration_prepared | 2 |  |
| Larventura | offline_configuration_prepared | 4 |  |
| El Hammalmejil | blocked | — | No directed-reachable native bridge-separated final region |
| Miasmausoleo | offline_configuration_prepared | 3 |  |
| Campos Hupremos | offline_configuration_prepared | 3 |  |
| Necromundo | blocked | — | No resolved non-boss family for preliminary rooms |
| Guarida de los Supervillanos | blocked | — | Exactly one identified native family boss required for this preparer |

## Verification

Seven focused branch tests and four scope/geometry audit tests pass. The tests cover parallel gate frontiers, a true gate-free bypass counterexample, annex preservation, directed movement failure, literal exit coordinates and the return-to-entrance proof. The V2 report and candidate files are frozen for independent PostgreSQL validation.

```sh
PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_native_branch_spine.py
PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_remaining_dungeon_geometry_audit.py
```

The only existing tool changes are optional physical walking-return proof support and correcting the offline roster validator to use the runtime destination-room frontier. Default exit binding behavior is preserved. No server gameplay logic changed.
