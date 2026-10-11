# Independent pricing design review

Reviewed on 2026-10-11 against the 18,816-reference curated CSV and its frozen native catalog snapshot. This document recommends game-economy policy; it does not claim observed market prices. No database or service was changed.

## Price units and calibration

All prices must mean kamas per individual delivered item, within 100–10,000,000 inclusive. The user’s `100k` is interpreted as 100 kamas, not 100,000. A stack is quantity × unit price; native `stack_maximum` is a transport limit, never the amount delivered for the displayed unit price.

Recommended initial budgets before manual outlier review:

| Economic role | Unit-price target band | Notes |
| --- | ---: | --- |
| Ordinary bread, restorative food, fish food | 100–5,000 | Lowest repeat-purchase band; price healing strength per unit and actual effect, not a name match alone |
| Other ordinary food/buffs | 100–20,000 | Strong combat buffs may justify the upper end; separate raw fish resources |
| Harvestable resources/seeds | 100–50,000 | Profession level, rare-harvest evidence and yield matter |
| Other resources | 100–250,000 | Verified rare boss materials may exceed this after review |
| Furniture | 500–300,000 | Functional storage/crafting stations may exceed decorative furniture |
| Ordinary tools/bags | 500–250,000 | Capacity and utility matter more than damage-item formulas |
| Common through legendary equipment | 1,000–3,000,000 | Level and quality dominate; only exceptional verified scarcity above this |
| Epic/relic/souvenir equipment | 100,000–7,500,000 | Different native quality ordering; do not simply multiply numeric rarity IDs |
| Pets and mounts | 50,000–2,000,000 | Base obtainable companion versus trained state, travel utility and cosmetic skin |
| Cosmetics, emotes, titles, auras | 10,000–2,000,000 | Level is generally uninformative; achievements and event exclusivity require explicit evidence |
| Enchantment tools/shards/basic runes | 100–250,000 | Consumption and exact supported function dominate |
| Valuable functional sublimations | 100,000–5,000,000 | Reserve strongest premiums for verified utility and source difficulty |
| Real equipable Dofus | 8,000,000–10,000,000 | Explicit user preference: highest category; whitelist by structure |

These are calibration guardrails, not claims that every row in a family is equally useful or functional. A normal food item should not reach equipment prices merely because its native rarity is high or its recipe is absent.

## Native quality order

The installed-client enum evidence is `.runtime/local/fof-enum.javap.txt` (`fof.aKg`, static initializer), independently corroborated for epic/relic by `sniffer/java/ExportNativeSublimationTargets.java`.

| Native ID | Meaning | Suggested multiplier |
| --- | --- | ---: |
| 1 | COMMON | 1.0 |
| 0 | UNUSUAL | 1.25 |
| 2 | RARE | 1.8 |
| 3 | MYTHIC | 3.0 |
| 4 | LEGENDARY | 5.0 |
| 6 | PVP; current label Souvenir | 6.0 |
| 7 | RELIC2; current label Epic | 8.0 |
| 5 | RELIC | 10.0 |
| 10 | ADMIN | Hold for review, no premium inference |

ID 0 is not the lowest rarity, and ID 7 is not above relic ID 5. Category budgets should cap ordinary consumables independently of these multipliers.

Six retained rows have native ADMIN quality even though their names survived the earlier name-based curation: 9679 Sombrero Kano; 29879 Aura centelleante; 30724 Carrera T-pose; 30840 El buen pico; 31470 El Wey ha muerto esta noche; 32913 Carrera T-pose 2. Assign provisional prices if complete coverage requires them, but hold them from shop publication pending functional review.

## Dofus classification

`dofus-accessories` intentionally overlaps accessories and any Dofus-named item. It must not be treated as a premium price class. The structurally equipable Dofus in the retained inventory are native type 646, equipment slot 17, with a Dofus name:

| Reference | Name | Level |
| --- | --- | ---: |
| 20720 | Dofus prismático | 200 |
| 24110 | Dofus prismático | 200 |
| 28417 | Dofus Turquesa | 215 |
| 31361 | Dofus Marfil | 155 |
| 32351 | Dofus Ébano | 245 |
| 33395 | Dofus Púrpura | 170 |

The two prismáticos need effect/action comparison before being treated as interchangeable. The quest objects 28392, 31503, 32407 and 33397 are native type 551 and are not equipable Dofus. Their names and icons can match the functional objects. They need quest-source and purchase-eligibility review, not the premium Dofus band. Sculptures (12182, 12285), the title 11431, encyclopedia 23961, auras and emotes retain their actual furniture/cosmetic/book role. No fragment may re-enter pricing through a recipe or a name-based whitelist.

## Acquisition evidence and uncertainty

Use the easiest verified acquisition route as the base difficulty: an item that is both a common drop and an expensive craft should not receive both premiums. A zero-probability or impossible loot row is not an attainable drop. Expected attempts should use actual probability, roll limits and guaranteed-drop rules, and should be bounded to avoid a tiny catalog rate overwhelming the whole economy. Boss level, encounter duration, dungeon access and player count are separate evidence from the percentage itself.

Absence from extracted drop and recipe tables is not proof of absence in game. Harvesting, quests, achievements, tokens, events, NPC exchange and linked transformations can produce items. Examples of obvious alternate acquisition are wood type 306 (1723 Madera de fresno), crop type 309 (1734 Ñiamzama) and seeds (1750 Semilla de cebada). Apply no verified no-source scarcity claim to these rows. Store `unknown`/`alternative-source` and a confidence field. The user-requested no-drop/no-craft premium can still be an explicit conservative policy surcharge for genuinely unsupported acquisition, but must be labelled policy rather than observed rarity and held for manual checking.

For recipes, use ingredient quantities divided by output yield, profession level, intermediate craft depth, workstation/access restrictions, and the cheapest valid recipe. Guard recursion against cycles. Reusable tools are not consumed ingredients. Missing or excluded ingredients need an explicit uncertainty marker. Do not resurrect deleted fragments as shop listings merely because a recipe references them.

## Economy and functionality checks

- Check craft arbitrage: `sum(input quantity × input shop price) / output yield` against the output price. Buying components and crafting should offer a deliberate modest saving, not an accidental order-of-magnitude exploit. Multiple recipes need the cheapest reachable route.
- Check recycling/enchantment arbitrage using `item-recycling-metadata.json`, shard values and actual target eligibility: shop equipment that recycles into more purchasable value than its price creates a resource faucet even without NPC resale.
- Check NPC resale, exchange chains, container outputs and re-purchase loops before publication. A price catalog alone does not prove these routes are implemented.
- Level zero is valid for pets (12127, 12128, 12129), cosmetics and runes; avoid pricing them as unfinished or applying an equipment level-zero penalty. Companion definition level does not represent a trained pet’s eventual power.
- Runes need supported function and consumption review. 17922 Runa de esquiva and 17923 Runa de placaje are level zero; names do not prove they are equivalent to modern sublimations. 16163 Martillo triturador and 16164 Martillo de forjamago are tools with different economic roles.
- Availability/binding restrictions affect shop eligibility independently of price. Selling a quest replica cheaply may bypass progression even when it has no combat stats.
- Same-name duplicate objects can have different effects, rarity, binding and use actions. Preserve per-reference prices; flag identical evidence with divergent prices for review.

## Manual review acceptance

A human/subagent review should read every exceptional row (Dofus, ADMIN, unknown source, capped prices, quest objects), all category extremes and cross-category collisions. Ordinary homogeneous groups can be reviewed as explicit rule cohorts with representative rows, but must not be described as individual inspection of all 18,816 objects. Record reviewer, references/cohort, observed prices and reason for any override. Until the generated price CSV is reviewed, this document is a design review, not final approval of its actual values.

Sources: `docs/reports/item-shop-inventory-20261011/curated/all-items.csv`, `dofus-named-items.csv`, `README.md`; frozen catalog `.runtime/local/item-shop-inventory-20261011/catalog.json`; native enum dump above. No external market estimates were used.
