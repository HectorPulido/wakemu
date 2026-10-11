# Reviewed Wakemu item prices

**Current selection:** [Highest-rarity deduplication](deduplication/README.md) leaves **11,765 active articles**. The original publication counts below are historical; all administrator-quality and previously held articles remain disabled.

All **18,816 retained objects** have a proposed price between **100 and 10,000,000 kamas per individual item**. The user's confirmed unit is kamas; `100k` means 100 kamas. The six equipable Dofus cost 10,000,000 each. The previous curation, excluded fragments and distinct item references are preserved.

**Start with [price-list.csv](price-list.csv)** for the readable catalog. [prices.csv](prices.csv) contains the complete calculation and provenance fields. Published to the live local shop on 2026-10-11 at the user’s request: **17,047 active articles and 1,769 disabled publication-held articles**. See [publication evidence](publication.md).

## Deliverables

- [Readable item prices](price-list.csv): ID, Spanish name, economic role, level, quality, price, source, confidence, reviewer and publication holds.
- [Full price calculations](prices.csv): drop route, recipe, output yield, ingredient costs, utility factors, manual decisions and flags.
- [Category summary](category-summary.csv) and one `prices-<economic_group>.csv` per economic role.
- [Publication-held objects](publication-holds.csv): 1,769 priced references requiring specific functional/progression review.
- [Manual changes](price-review-changes.csv), [manual decisions](manual-overrides.json), [full reviewer ownership](manual-review-index.json).
- [Final manual acceptance](final-review.md), [automated validation](validation.md), [counts and SHA-256 manifests](summary.json).

## Representative final prices

| Item | Reference | Unit kamas |
| --- | ---: | ---: |
| Esquirlas | 27083 | 110 |
| Albóndiga de tofu | 3864 | 290 |
| Jalamartillo | 2027 | 2,600 |
| Miaumiau angora | 12127 | 350,000 |
| Dragopavo | 18682 | 870,000 |
| Dora N.I.O. reviewed variant | 24103 | 5,100,000 |
| Dofus prismático | 20720 | 10,000,000 |
| Dofus Turquesa | 28417 | 10,000,000 |

The deployed Jalamartillo article now costs 2,600 kamas; its original article ID/key and purchase history were preserved. Native shop OG/ogrine presentation still represents the same account kama wallet. Quantity is one; a full stack costs quantity × unit price, not this displayed unit price.

## Economic model

The editable [pricing-policy.json](pricing-policy.json) defines the versioned assumptions and soft category budgets. Additional criteria beyond level/rarity are permanent versus consumed utility, actual output quantity, profession effort, intermediate ingredients, conditional access, boss difficulty and recycling replacement value.

For each economic role:

```text
utility = role_base × (1 + effective_level / role_scale)^role_exponent
          × quality_multiplier^role_quality_exponent
```

Healing-registry objects receive a bounded strength factor based on their native healing effect. Companion and cosmetic level 0/1 uses a documented role utility default; that default is an economic assumption, not a fabricated character-level requirement. Quality ordering follows native identities: COMMON=1, UNUSUAL=0, RARE=2, MYTHIC=3, LEGENDARY=4, PVP/SOUVENIR=6, EPIC=7, RELIC=5. ADMIN=10 triggers a publication hold instead of a prestige multiplier.

For a supported drop route, the difficulty factor uses native expected items per encounter, with exponent 0.22, a bounded base factor, monster minimum level, boss modifier and conditional-access modifier. The least expensive supported modeled drop route is used. Prospection/rate bonuses, actual spawn availability and team encounter time are not inferred. A route is catalog evidence, not a guarantee that a player can reach it now.

If no supported drop is found, a supported productive recipe can set the price:

```text
input_cost_per_item = sum(ingredient_quantity × final_ingredient_unit_price)
                      / recipe_output_quantity
labor_per_item = (profession_level × 12 + ingredient_slots × 25
                 + raw_recipe_seconds × 2) / output_quantity
craft_price = 1.15 × max(utility, input_cost_per_item + labor_per_item)
```

The lowest modeled supported recipe is used. Intermediate crafting is recursive; ingredient manual overrides propagate into dependent prices. Cyclic recipes are skipped explicitly, preserving alternative acyclic recipes. Excluded ingredients may be internally costed to evaluate a recipe, but never reappear as sale listings. Their absence from the curated shop is flagged.

Verified criterion-free harvest references are an alternate acquisition route; when both harvesting and crafting are available without a supported drop, the cheaper modeled route is used. Harvest yields and rare-harvest probabilities are not quantified by this extraction. Remaining objects receive an explicit role-specific unresolved-source premium: equipment usually 6×, permanent cosmetics/companions 4×, most services/consumables 3×, bread/food 1.5×. Resources and quest objects receive smaller premiums because alternate acquisition is likely. These are **policy premiums**, not evidence that an object cannot be obtained in the game.

Prices round upward to readable steps: 10 below 1,000; 100 below 10,000; 1,000 below 100,000; 10,000 below 1m; 100,000 above that. The global floor and ceiling apply after rounding. Economic-role ceilings are soft; specifically documented manual exceptions may exceed them while respecting the global maximum.

## Manual review and final corrections

Six independent reviewer scopes cover all 18,816 references without overlap: **847 type/rarity/acquisition cohorts**, representative rows, extrema and individual exceptions. This is not a claim of separately eyeballing every ordinary item. The exception queue and changed prices received explicit manual judgment; all rows also pass automated checks.

The final catalog includes **301 individual decisions**: four profession-tool corrections, 49 relic peer-price corrections, 57 service/XP/bonus valuations, nine kama-denomination floors, eight retained sublimation cap discounts and 174 recycling procurement floors. Of these, 293 change a price directly; another 609 prices change through final ingredient-cost propagation. The final Dora N.I.O. peer floor was rechecked at 5.1m after propagation.

The expected-yield recycling check prevents a cheap source item from undermining the listed powder/shard price. It uses native product/yield metadata and the actual supported recycling projection, rather than treating recycling as a cash buyback. After 174 floors, zero expected product-value undercuts remain among 13,193 audited recyclable references. Random output and per-instance restrictions remain distinct from expected-value pricing.

Some category caps deliberately subsidize direct purchases relative to expensive recipes, especially ordinary food and eight sublimations. See [final-review.md](final-review.md) for the exact tradeoffs, including two neopócimas at 5,800 and four tools above their former soft cap. Equal display names are never merged: differing effects, binding, conditions, quality and acquisition routes remain separate references.

## Coverage and uncertainty

| Pricing source | References |
| --- | ---: |
| Supported unconditional drop route | 3,808 |
| Supported conditional drop route | 2,113 |
| Supported productive crafting route used | 2,472 |
| Harvest catalog route used | 522 |
| Unresolved-source policy | 9,895 |
| Explicit equipable-Dofus premium | 6 |
| **Total** | **18,816** |

The evidence includes 16,138 native drop rows and 5,449 recipes. Full recipe extraction contains 4,878 curated outputs with a productive supported recipe; fewer use the crafting price because documented drops take precedence or a harvest route is cheaper. Recipes with unsupported criteria/secret flags do not silently become obtainable routes.

Confidence is independent of manual price approval: 3,808 high, 4,236 medium, 10,766 low, six explicit Dofus-policy prices. Low confidence includes unknown ingredient acquisition, not just the final item's own source. Missing drops/recipes do not prove exclusivity: quests, achievements, events, exchanges and unexported gathering sources remain possible.

Six ADMIN-quality objects and other progression, container, old-rune and special-system cases are priced but held from publication. Ordinary food is distinguished from experience grants, stat boosts and class-change/reset services; those receive specific manual prices and holds pending functional verification. The 60 accepted healing-registry objects remain present. All 464 current sublimations remain present, including the 79 epic/relic definitions supplied by migration 124.

## Reproduction and validation

Sources are pinned to native release `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`. [Drop evidence](drop-evidence.md) and [craft evidence](craft-evidence.md) explain source hashes, probability units, supported criteria and limitations. The private runtime evidence directory contains catalog snapshots only for this analysis; no player/account data is included in the price outputs.

From the repository root, with the frozen evidence already available:

```sh
python3 tools/merge-item-price-reviews.py
python3 tools/price-game-items.py
PYTHONPATH=server python3 -m unittest tools.tests.test_price_game_items -v
```

The original automated proposal is preserved at `.runtime/local/item-pricing-20261011/prices-before-review.csv` for deterministic delta reporting. Drop/craft exporters and their exact invocation are documented in the evidence reports. The main generator consumes their JSON outputs, the immutable native snapshot and the curated reference list; it performs no service or database mutation.

**13 checks pass**, including exact ID coverage, per-unit bounds, six premium Dofus, ADMIN holds, native quality ordering, output-yield division, recursive manual override propagation, cycle handling, review ownership, price deltas and source/artifact hashes. Final price SHA-256: `ad7d7d30297d5fae083b81dfb0249667280cb630aa56818c93603507240c8d44`.

## One complete manual review flow

1. Open `price-list.csv` in a spreadsheet application, import UTF-8 with comma delimiter, and enable filters. Expected: 18,816 unique references; every quantity is one.
2. Filter `economic_group=dofus`: exactly six rows, each priced 10,000,000. Search Dofus sculptures/auras: they use their real furniture/cosmetic roles and lower prices; no fragment is present.
3. Filter `bread` and `food`: ordinary bread spans 130–5,000, with two explicit neopócima recycling exceptions at 5,800; meals/drinks span 190–15,000. Compare the 60 accepted curatives to `confirmed-healing.csv` in the curated inventory.
4. Inspect Jalamartillo 2027 (2,600), Miaumiau angora 12127 (350,000), Dragopavo 18682 (870,000) and Dora N.I.O. 19432/24103 (5.1m each). Use the full calculation CSV to trace drop, recipe or unresolved-source policy.
5. Filter nonempty `publication_hold`: 1,769 rows. Confirm ADMIN, quest replicas and unresolved special-service/container cases remain held despite having prices. Open `publication-holds.csv` for detailed reasons.
6. Read the final manual acceptance and review changed prices. No in-game purchase test can verify these new prices yet because the live shop has not been updated; publication is a separate step.
