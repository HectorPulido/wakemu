# Item inventory validation

Validation stage: native type enrichment is included. I checked `tools/inventory-game-items.py` and the generated CSVs against the frozen catalog and native type export on 2026-10-11. The generator consumes the cosmetic action export and the native type export. It retains structural evidence and overlapping categories; category membership does not establish that every item's gameplay behavior is implemented.

The frozen `item-stack-rules.json` contains 20,230 rows: 20,229 positive item references and reference `0`. The inventory contains each positive reference exactly once, with no missing or extra IDs and no duplicate source references. The native type export also contains reference `0`; it is outside the positive-item inventory. All CSV names match the snapshot, with native null names represented as empty cells. The catalog revision is `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`.

I rebuilt the rows in memory with the current generator and confirmed that every generated CSV's normalized rows match the checked-in file. Category keys match the parsed evidence keys, and every listed category has at least one evidence reason. Native type IDs and parent links resolve. The frozen input and CSV artifact SHA-256 values also match `summary.json`.

| Output | Rows |
| --- | ---: |
| All positive native items | 20,229 |
| Weapons and equipment | 11,196 |
| Dofus accessories | 2,229 |
| Pets and mounts | 179 |
| Cosmetics | 2,270 |
| Haven bag | 1,586 |
| Healing candidates | 226 |
| Smithmagic | 901 |
| Classified unique items | 16,340 |
| Unclassified items | 3,889 |
| Dofus-named items | 42 |
| Items with confirmed native healing effects | 62 |
| Fish resources (separate export) | 72 |

Categories overlap, so category totals should not be added to infer a unique item count. The healing category includes native bread, meal, and drink type candidates; `confirmed-healing.csv` separately lists references found in native healing-effect rules. `unclassified-items.csv` keeps records with no evidence from the implemented structural rules for further audit.

`PYTHONPATH=server:server/tests python3 -m unittest test_shop_http` passed: 7 tests, no failures. The isolated PostgreSQL shop suite was not run because its opt-in flag and isolated database URL are not configured; the suite requires `WAKFU_RUN_SHOP_POSTGRES_TESTS=1` and a separate test database.
