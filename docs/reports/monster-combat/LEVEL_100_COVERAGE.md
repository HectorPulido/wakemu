# Monster family coverage through level 100

Offline estimate on 2026-10-10, using the same available shared effect-family criteria as [the low-level audit](LOW_LEVEL_COVERAGE.md). Level 100 is included. No services or runtime catalogs were changed.

| Entire native level range within 1–100 | References | % of all | % of references with owned spells |
|---|---:|---:|---:|
| All effect families available and candidate dependencies present | 780 | 58.47% | 90.70% |
| Almost: exactly one missing effect family | 68 | 5.10% | 7.91% |
| Multiple missing effect families | 12 | 0.90% | 1.40% |
| No native owned spells; not counted as functional | 474 | 35.53% | — |
| Total | 1,334 | 100% | — |

There are 860 references with owned spells. Covered plus almost: 848, or 98.60% of those references and 63.57% of all references. Individually rounded percentages may not sum to exactly 100%.

If references merely starting within 1–100 are included, even when they scale higher, there are 1,430 references: 845 covered (59.09%), 79 almost (5.52%), 13 with multiple missing families and 493 without owned spells.

These are monster/NPC references, including variants, companions, summons and pets, not distinct wild species. Available handlers do not certify successful execution: native parameters, conditions, NPC context wiring, AI, initialization and trigger lifecycles remain untested. Dependency closure spans all sampled levels and may include branches irrelevant below level 100. Extracted data is still separate from active catalogs. “Almost” measures one missing family, not the difficulty of implementing it.

## Reproduce

```sh
python3 server/tools/audit_monster_family_coverage.py --max-level 100 \
  --inventory .runtime/monster-combat-extraction-20261010/inventory.json.gz \
  --registry .runtime/e18-deploy-server/protocol/effect-characteristic-registry.json \
  --setters .runtime/monster-coverage-20261010/set-current.json \
  --output docs/reports/monster-combat/LEVEL_100_COVERAGE.json
```

The [JSON result](LEVEL_100_COVERAGE.json) includes every reference, missing families, and input checksums. Automatic checks confirmed count totals, unique references, level bounds and unchanged classifications for the default level range.
