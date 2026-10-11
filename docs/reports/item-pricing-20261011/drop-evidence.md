# Native combat drop evidence for item pricing

The read-only export is `.runtime/local/item-pricing-20261011/drops.json`. Reproduce from the repository root:

```sh
python3 tools/export-item-drop-evidence.py
```

The exporter executes only PostgreSQL SELECT statements through the existing postgres service. It pins immutable release `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d` and verifies exact raw document hashes:

| Document | SHA256 |
|---|---|
| monster-encyclopedia.json | db31e2b205370fc73771573d33f374085ab1a27d222ef0601199eedf90792d36 |
| monsters.json | 5480cb2cf3611cbbdd268c66e467f3404645dcdeb98a7b9fbb2cc620f018acc4 |

There are 16,138 native combat rows matching 6,278 item references, before intersection with the curated inventory: 3,938 references have an unconditional route at baseline effective prospection 100, 2,102 have a supported conditional or higher-prospection route, and 238 have matching rows that this runtime cannot award. Every route has authoritative monster name and level metadata. Native world-property IDs classify bosses: 43 boss, 45 archmonster, 49 ultimate boss, 99 raid boss. Classification follows `server/tools/export_monster_growth_catalog.py`, without name heuristics.

## Probability semantics

`server/wakfu_server/storage/combat_drops.py` consumes native probability as a fraction: 0.01 means 1%, not 0.01%. Positive roll counts produce that many attempts per player; nonpositive values are the each-player sentinel and produce one attempt. The exporter records `probability_at_least_one_base = 1 - (1-p)^attempts` and `expected_quantity_base = p * attempts * (quantity_min + quantity_max) / 2`. Quantities are uniform draws within the native bounds. These estimates assume baseline modifiers and one defeated actor, not an entire multi-monster fight.

The runtime multiplies base probability by prospection, reward policy, challenge and other fight modifiers and caps effective chance at one. Native `csE` is retained as evidence, not treated as a probability multiplier. Minimum prospection `csF` gates eligibility. Prices should use a stable base rather than a player's temporary bonus.

The exporter retains all rows, including opaque complex criteria and external loot-table pointers, while marking those routes unsupported. Supported conditions are native dungeon, infinite-wave, downscale, stele, minimum stasis and minimum score checks. A conditional route remains dependent on the matching authoritative fight context. `best_supported_route` maximizes chance, breaking ties by lowest monster level; `best_unconditional_route` uses only rows without conditions and minimum prospection at most 100. Neither field claims that the monster is currently spawned or freely accessible. The complete routes allow separate handling of boss, condition and encounter effort instead of silently discarding that evidence.

An absent item reference means **no matching native combat-drop record was found**, not proof that the item has no acquisition route. Collection actions, quests, tokens, craft, events and unimplemented external tables require separate evidence. `matching_rows_unusable` means this runtime skips the matched rows, not that the original game never awards the object.

Validation checked source hashes, all source rows, complete monster metadata, probability bounds (0.000125–1), and quantity bounds (1–750). No source database, service or combat code changed.
