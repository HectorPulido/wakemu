# All-level monster family coverage

Offline estimate on 2026-10-10. Same method and source evidence as [the level-100 report](LEVEL_100_COVERAGE.md). All 2,874 extracted native monster references are included, without level exclusions.

Previously classified references were reused: **1,430 reused, 1,444 newly classified**. The cache is accepted only when all five input hashes and the supported-family set match. Cached rows are copied before classification; all reused rows were checked for exact equality. No services or runtime catalogs were changed.

| Category | References | % of all | % of references with owned spells |
|---|---:|---:|---:|
| All required effect families available; no extracted candidate data gaps | 1,669 | 58.07% | 86.30% |
| Almost: exactly one missing effect family | 219 | 7.62% | 11.32% |
| Multiple missing effect families | 33 | 1.15% | 1.71% |
| Missing candidate dependency data | 13 | 0.45% | 0.67% |
| No native owned spells; not classified as functional | 940 | 32.71% | — |
| Total | 2,874 | 100% | — |

There are **1,934 references with owned spells**. Covered plus almost: **1,888 (97.62% of spell owners)**. Percentages may differ slightly from 100% when individually rounded.

This is static coverage of available shared effect-family building blocks, not certification of working encounters or a zero-effort implementation promise. Native parameters, conditions, NPC context wiring, AI, initialization, triggers and actual combat execution remain unvalidated. Some handlers are conditional on additional runtime authority. The extracted data has not been published to active catalogs. Candidate closure includes all sampled levels and does not exhaust implicit handler dependencies. Effect parameters above the extracted sample domain remain an additional limitation. “Almost” means one missing family, whose implementation difficulty can vary.

Counts include variants, companions, pets, summons and other NPCs rather than distinct wild species. Thirteen dependency gaps are conservative unresolved candidates, not confirmed absent native definitions.

## Reproduce

```sh
python3 server/tools/audit_monster_family_coverage.py --all \
  --reuse docs/reports/monster-combat/LEVEL_100_COVERAGE.json \
  --inventory .runtime/monster-combat-extraction-20261010/inventory.json.gz \
  --registry .runtime/e18-deploy-server/protocol/effect-characteristic-registry.json \
  --setters .runtime/monster-coverage-20261010/set-current.json \
  --output docs/reports/monster-combat/ALL_LEVELS_COVERAGE.json
```

[Per-reference classifications and provenance](ALL_LEVELS_COVERAGE.json). Automatic checks confirmed exact preservation of reused rows, full inventory membership, unique references and category sums. Python compilation and whitespace checks passed.
