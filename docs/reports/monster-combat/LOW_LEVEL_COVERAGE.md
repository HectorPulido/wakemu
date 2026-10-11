# Low-level monster family coverage

Offline estimate on 2026-10-10, reusing the extracted inventory and current shared class/NPC runtime registrations. This measures available effect-family building blocks, not proven functional monsters. No services or database catalogs were changed.

## Counts

The strict cohort requires `1 <= min_level <= max_level < 25`. Counts are native monster references, including event variants, companions, pets, summons and other NPCs; they are not distinct wild species or currently spawned encounters.

| Strict cohort | References | % of all 471 | % of 204 with owned spells |
|---|---:|---:|---:|
| All effect families available and extracted dependencies present | 193 | 40.98% | 94.61% |
| Almost: exactly one effect family missing, dependencies present | 7 | 1.49% | 3.43% |
| Multiple effect families missing | 4 | 0.85% | 1.96% |
| No owned spells in native data; not classified as functional | 267 | 56.69% | — |
| Total | 471 | 100% | — |

The broader cohort `1 <= min_level < 25` includes references that scale to higher levels: 533 total, 249 with owned spells, 227 covered (42.59% of all; 91.16% of spell owners), 17 almost (3.19%; 6.83%), five with multiple missing families, and 284 without owned spells. It includes companions scaling from level 1 to 245, so the strict cohort is the preferred low-level estimate.

All eight ordinary Miaumiau, Tofu and Jalató references reviewed in the extraction report are in the covered category.

## Seven strict-cohort near matches

| Reference | Name | Levels | Missing family |
|---:|---|---|---:|
| 704 | Gorditofu | 14–18 | 327 |
| 1483 | Bulbo de belíade | 5 | 839 |
| 4092 | Tofu dominante | 18–23 | 327 |
| 4114 | Guadaña-dora | 12 | 994 |
| 4472 | Bulbo evanescente | 5 | 839 |
| 4689 | Bebé perforatroz | 15 | 328 |
| 5815 | Neoespíritu merodeador | 12 | 994 |

These seven share four missing families. Implementing one family may unlock several references, but family count does not measure implementation difficulty.

## Method and boundaries

The audit reads handler registrations directly from `combat_effect_runtime.py`, the dispatcher group branches, damage/healing/displacement constants and native characteristic registries. The characteristic registry's client-JAR checksum matches the extraction bundle. The 12 set-current characteristic families are exported with the existing `ProbeNativeSetCurrentCharacteristic.java` tool.

Each monster must own at least one spell, have actor/casting/root metadata, have no missing candidate dependency definitions, and use only available families throughout the extracted transitive spell/state closure to count as covered. The closure retains all sampled levels rather than pruning to levels below 25; this can conservatively include irrelevant branches.

Available family handlers may still reject an unsupported parameter variant, predicate or missing NPC authority/context. This audit does not test AI choice, cast targeting, trigger lifecycles, initialization, implicit handler-side dependencies, fight-property behavior, or actual execution. The extracted data also remains separate from active database catalogs. Therefore **193 is a candidate integration pool, not 193 certified working encounters**. Neither category implies literally zero integration or validation effort.

The complete per-reference results and input hashes are in [LOW_LEVEL_COVERAGE.json](LOW_LEVEL_COVERAGE.json). Reproduce after exporting the setter registry:

```sh
python3 server/tools/audit_monster_family_coverage.py \
  --inventory .runtime/monster-combat-extraction-20261010/inventory.json.gz \
  --registry .runtime/e18-deploy-server/protocol/effect-characteristic-registry.json \
  --setters .runtime/monster-coverage-20261010/set-current.json \
  --output docs/reports/monster-combat/LOW_LEVEL_COVERAGE.json
```
