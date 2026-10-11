# Manual food and materials price review

## Scope and method

Reviewed 1,928 item references in 138 distinct economic group / native type / rarity / acquisition cohorts. This is a manual review of cohort distributions and individually inspected extremes, not a claim to have read every item individually. The complete reference scope is in `food-materials-decisions.json`.

Read pricing-policy.json, native drop and craft evidence contracts, all cohort counts/ranges, lowest three and highest eight entries in each group, all consumable names, and the 60 confirmed healing items. Reference prices are kamas per single item. No DB, service or pricing pipeline was modified.

## Decisions

- Keep cheap recurring supplies: seeds 100–210, ordinary harvest resources generally 100–820, healing bread 130–5,000 and food 190–15,000. Higher food prices are for prepared meals and utility, not raw fish healing. Missing harvest quantity remains a confidence limit, not a scarcity multiplier.
- Accept material progression and recipe overhead: common refined materials mostly 660–8,700, upper breeding materials 93,000–99,000, and master seals 99,000–310,000. The seals are exceptional progression inputs rather than ordinary daily crafting stock.
- Retain native drop quantities and conditional/boss acquisition premiums. Late-game rare/mythic resources around 3,100–3,200 are appropriate inexpensive ingredients; 30,000 necromic stone is an evidenced crafted exception. No external loot probability was invented.
- High-yield bread recipes yield four units: per-unit costing already divides the whole recipe and labor by four. 5,000 bread and 15,000 meal ceilings are deliberate affordability subsidies, not missing yield corrections. A shop ingredient sum greater than a finished product is not itself an exploit when cheaper harvest/drop procurement exists.
- Correct 57 service/XP/explicit-stat boosters that were almost flat 1,600–3,500 despite radically different utility. XP names scale from 380,000 to 35,000,000; proposals now scale 50,000–2,000,000. Class changes scale 250,000 / 600,000 / 1,000,000 by stated level range; reset 250,000. Explicit +10 to +100 boosters scale 20,000–200,000 per stat, double for both stats.
- All 57 corrections stay on publication hold pending effect execution, duration and consumption verification. Prices are manual commercial proposals derived from stated utility, not fabricated acquisition evidence. Unknown eternity XP gets provisional 2,500,000 and hold.

## Healing potency cross-check

All 60 retained healing references were cross-checked by name/price against curated confirmed-healing.csv. As a secondary sanity check, `.runtime/e18-deploy-server/protocol/item-healing-rules.json` provides native flat healing magnitudes, but it is a prior deployment snapshot rather than an authoritative current build. Its progression is coherent: Pan de Farle heals 50 at 540; Pan de centeno 250 at 880; Pan infernal 1,100 at 2,800; Pansalva 1,875 at 5,000. Starter/event rolls heal 8–70 at 130–140 and should stay accessible. Recipe flavor changes justify some nonmonotonic prices; a strict price per HP would incorrectly erase craft costs. No claim that the snapshot proves current executable healing behavior.

## Cohort inventory

| Group | Type | Rarity | Acquisition | Count | Price range before manual overrides |
|---|---|---|---|---:|---:|
| bread | 745 | COMMON | craft | 35 | 290–3,100 |
| bread | 745 | COMMON | drop | 1 | 140–140 |
| bread | 745 | COMMON | unresolved_source_policy | 1 | 130–130 |
| bread | 745 | MYTHIC | craft | 16 | 1,100–5,000 |
| bread | 745 | UNUSUAL | unresolved_source_policy | 10 | 130–170 |
| consumable | 594 | COMMON | drop | 2 | 990–1,300 |
| consumable | 594 | COMMON | unresolved_source_policy | 1 | 1,600–1,600 |
| consumable | 594 | RARE | unresolved_source_policy | 1 | 2,100–2,100 |
| consumable | 594 | UNUSUAL | unresolved_source_policy | 4 | 1,800–1,800 |
| consumable | 630 | COMMON | drop | 1 | 950–950 |
| consumable | 630 | COMMON | unresolved_source_policy | 3 | 1,600–1,600 |
| consumable | 630 | UNUSUAL | unresolved_source_policy | 9 | 1,800–1,800 |
| consumable | 631 | COMMON | drop | 1 | 530–530 |
| consumable | 631 | MYTHIC | unresolved_source_policy | 1 | 2,700–2,700 |
| consumable | 631 | RARE | unresolved_source_policy | 3 | 2,100–2,100 |
| consumable | 631 | UNUSUAL | unresolved_source_policy | 5 | 1,800–1,800 |
| consumable | 696 | COMMON | drop | 9 | 530–900 |
| consumable | 696 | COMMON | harvest_catalog | 1 | 530–530 |
| consumable | 696 | COMMON | unresolved_source_policy | 4 | 1,600–1,600 |
| consumable | 696 | RARE | harvest_catalog | 1 | 710–710 |
| consumable | 696 | RARE | unresolved_source_policy | 13 | 2,100–2,100 |
| consumable | 696 | UNUSUAL | unresolved_source_policy | 13 | 1,800–1,800 |
| consumable | 738 | COMMON | drop | 3 | 730–1,000 |
| consumable | 738 | COMMON | unresolved_source_policy | 2 | 1,600–1,600 |
| consumable | 738 | RARE | craft | 1 | 5,600–5,600 |
| consumable | 738 | RARE | drop | 2 | 1,400–1,700 |
| consumable | 738 | RARE | unresolved_source_policy | 18 | 2,100–2,100 |
| consumable | 738 | UNUSUAL | unresolved_source_policy | 16 | 1,800–1,800 |
| consumable | 746 | COMMON | drop | 4 | 530–850 |
| consumable | 746 | COMMON | unresolved_source_policy | 4 | 1,600–1,600 |
| consumable | 746 | MYTHIC | unresolved_source_policy | 1 | 13,000–13,000 |
| consumable | 746 | RARE | craft | 1 | 17,000–17,000 |
| consumable | 746 | RARE | drop | 2 | 1,400–1,400 |
| consumable | 746 | RARE | unresolved_source_policy | 7 | 2,100–2,100 |
| consumable | 746 | UNUSUAL | unresolved_source_policy | 40 | 1,800–4,300 |
| consumable | 752 | COMMON | unresolved_source_policy | 2 | 1,600–1,600 |
| consumable | 752 | LEGENDARY | unresolved_source_policy | 5 | 3,500–3,500 |
| consumable | 752 | MYTHIC | unresolved_source_policy | 3 | 2,700–9,600 |
| consumable | 752 | RARE | unresolved_source_policy | 1 | 2,100–2,100 |
| consumable | 752 | UNUSUAL | unresolved_source_policy | 8 | 1,800–1,800 |
| consumable | 815 | MYTHIC | unresolved_source_policy | 1 | 2,700–2,700 |
| consumable | 815 | UNUSUAL | unresolved_source_policy | 7 | 1,800–1,800 |
| consumable | 838 | COMMON | unresolved_source_policy | 30 | 1,600–1,600 |
| food | 747 | COMMON | craft | 40 | 290–15,000 |
| food | 747 | COMMON | drop | 1 | 800–800 |
| food | 747 | COMMON | unresolved_source_policy | 20 | 190–840 |
| food | 747 | MYTHIC | craft | 1 | 12,000–12,000 |
| food | 747 | MYTHIC | drop | 1 | 1,900–1,900 |
| food | 747 | RARE | craft | 52 | 1,900–15,000 |
| food | 747 | RARE | drop | 3 | 300–1,900 |
| food | 747 | UNUSUAL | unresolved_source_policy | 38 | 200–910 |
| food | 751 | COMMON | craft | 2 | 2,500–2,700 |
| food | 751 | RARE | drop | 2 | 220–230 |
| food | 751 | RARE | unresolved_source_policy | 1 | 220–220 |
| refined_material | 327 | COMMON | craft | 16 | 1,300–8,500 |
| refined_material | 327 | COMMON | drop | 1 | 280–280 |
| refined_material | 393 | COMMON | craft | 18 | 660–8,500 |
| refined_material | 393 | COMMON | drop | 1 | 280–280 |
| refined_material | 463 | COMMON | craft | 16 | 1,300–8,500 |
| refined_material | 463 | COMMON | drop | 1 | 280–280 |
| refined_material | 463 | RARE | craft | 1 | 750–750 |
| refined_material | 463 | UNUSUAL | unresolved_source_policy | 1 | 360–360 |
| refined_material | 514 | COMMON | craft | 18 | 1,300–8,700 |
| refined_material | 514 | COMMON | drop | 1 | 280–280 |
| refined_material | 514 | MYTHIC | conditional_drop | 5 | 780–2,500 |
| refined_material | 514 | MYTHIC | craft | 1 | 2,500–2,500 |
| refined_material | 514 | MYTHIC | harvest_catalog | 3 | 280–700 |
| refined_material | 514 | RARE | craft | 1 | 80,000–80,000 |
| refined_material | 514 | UNUSUAL | unresolved_source_policy | 1 | 360–360 |
| refined_material | 567 | COMMON | craft | 16 | 1,300–8,700 |
| refined_material | 567 | COMMON | drop | 1 | 280–280 |
| refined_material | 568 | COMMON | craft | 16 | 1,300–15,000 |
| refined_material | 568 | COMMON | drop | 1 | 280–280 |
| refined_material | 569 | COMMON | craft | 16 | 1,300–8,700 |
| refined_material | 570 | COMMON | craft | 16 | 1,300–8,400 |
| refined_material | 570 | LEGENDARY | craft | 1 | 99,000–99,000 |
| refined_material | 571 | COMMON | craft | 16 | 1,300–8,400 |
| refined_material | 571 | LEGENDARY | craft | 1 | 310,000–310,000 |
| refined_material | 574 | COMMON | craft | 16 | 980–13,000 |
| refined_material | 574 | LEGENDARY | craft | 1 | 200,000–200,000 |
| refined_material | 575 | COMMON | craft | 16 | 1,300–8,700 |
| refined_material | 575 | LEGENDARY | craft | 1 | 200,000–200,000 |
| refined_material | 576 | COMMON | craft | 16 | 1,300–8,700 |
| refined_material | 576 | LEGENDARY | craft | 1 | 220,000–220,000 |
| refined_material | 577 | COMMON | craft | 16 | 1,300–8,400 |
| refined_material | 578 | COMMON | craft | 16 | 1,300–8,400 |
| refined_material | 578 | LEGENDARY | craft | 16 | 1,200–15,000 |
| refined_material | 739 | COMMON | drop | 16 | 110–1,200 |
| refined_material | 851 | COMMON | craft | 14 | 2,300–99,000 |
| refined_material | 852 | LEGENDARY | craft | 1 | 5,800–5,800 |
| refined_material | 852 | LEGENDARY | harvest_catalog | 1 | 450–450 |
| resource | 281 | COMMON | harvest_catalog | 32 | 100–580 |
| resource | 281 | RARE | harvest_catalog | 32 | 100–820 |
| resource | 282 | COMMON | drop | 1 | 330–330 |
| resource | 282 | COMMON | harvest_catalog | 1 | 100–100 |
| resource | 282 | COMMON | unresolved_source_policy | 151 | 100–1,100 |
| resource | 282 | MYTHIC | unresolved_source_policy | 1 | 160–160 |
| resource | 282 | UNUSUAL | unresolved_source_policy | 4 | 270–610 |
| resource | 306 | COMMON | harvest_catalog | 73 | 100–560 |
| resource | 306 | COMMON | unresolved_source_policy | 1 | 170–170 |
| resource | 306 | RARE | harvest_catalog | 32 | 100–790 |
| resource | 306 | UNUSUAL | drop | 1 | 140–140 |
| resource | 306 | UNUSUAL | harvest_catalog | 1 | 100–100 |
| resource | 306 | UNUSUAL | unresolved_source_policy | 1 | 100–100 |
| resource | 308 | COMMON | harvest_catalog | 33 | 100–580 |
| resource | 308 | COMMON | unresolved_source_policy | 4 | 400–420 |
| resource | 308 | RARE | harvest_catalog | 33 | 100–820 |
| resource | 308 | UNUSUAL | unresolved_source_policy | 2 | 100–100 |
| resource | 309 | COMMON | harvest_catalog | 35 | 100–560 |
| resource | 309 | RARE | harvest_catalog | 32 | 100–790 |
| resource | 313 | COMMON | harvest_catalog | 66 | 100–560 |
| resource | 313 | RARE | harvest_catalog | 32 | 100–790 |
| resource | 313 | UNUSUAL | drop | 1 | 1,000–1,000 |
| resource | 313 | UNUSUAL | harvest_catalog | 1 | 100–100 |
| resource | 313 | UNUSUAL | unresolved_source_policy | 1 | 100–100 |
| resource | 419 | COMMON | unresolved_source_policy | 27 | 140–1,100 |
| resource | 419 | UNUSUAL | unresolved_source_policy | 1 | 270–270 |
| resource | 531 | COMMON | drop | 131 | 100–1,400 |
| resource | 531 | COMMON | unresolved_source_policy | 12 | 190–990 |
| resource | 531 | MYTHIC | conditional_drop | 44 | 400–3,200 |
| resource | 531 | MYTHIC | craft | 1 | 30,000–30,000 |
| resource | 531 | MYTHIC | drop | 94 | 160–3,200 |
| resource | 531 | MYTHIC | unresolved_source_policy | 2 | 350–2,100 |
| resource | 531 | RARE | conditional_drop | 1 | 1,600–1,600 |
| resource | 531 | RARE | drop | 104 | 100–3,100 |
| resource | 531 | RARE | harvest_catalog | 2 | 130–210 |
| resource | 531 | RARE | unresolved_source_policy | 6 | 260–1,400 |
| resource | 531 | UNUSUAL | conditional_drop | 12 | 150–1,600 |
| resource | 531 | UNUSUAL | unresolved_source_policy | 8 | 270–270 |
| resource | 809 | COMMON | unresolved_source_policy | 1 | 100–100 |
| resource | 809 | MYTHIC | harvest_catalog | 7 | 100–100 |
| resource | 809 | MYTHIC | unresolved_source_policy | 4 | 160–160 |
| resource | 809 | RARE | harvest_catalog | 34 | 100–100 |
| resource | 809 | RARE | unresolved_source_policy | 1 | 120–120 |
| seed | 309 | COMMON | drop | 1 | 100–100 |
| seed | 309 | COMMON | harvest_catalog | 30 | 100–170 |
| seed | 419 | COMMON | unresolved_source_policy | 77 | 100–210 |
| seed | 419 | UNUSUAL | unresolved_source_policy | 3 | 100–140 |

## Limitations

Native harvesting evidence establishes a route, not yield, spawn density or time to gather. Quest/event delivery, booster duration and every runtime consumable handler are not established by the price catalog. No reliable sell-back table was reviewed, so reverse shop arbitrage is not certified. Review approves proposals and documented holds, not deployment.
