# Final manual pricing acceptance

Final `prices.csv` SHA-256: `ad7d7d30297d5fae083b81dfb0249667280cb630aa56818c93603507240c8d44`.

All **18,816** retained references have a price and an assigned independent reviewer. Six reviewers manually assessed **847 type/rarity/acquisition cohorts**, their distributions and representative rows, plus individual exceptions and price deltas. This is a cohort review with individual exception inspection, not a claim that every ordinary row received a separate visual inspection. Automated coverage and bounds checks apply to every row.

| Reviewer scope | References | Cohorts | Final assessment |
| --- | ---: | ---: | --- |
| Basic equipment, bags, tools, pet accessories | 4,973 | 167 | Four tool-price corrections; all 33 changed rows assessed |
| Advanced equipment and equipable Dofus | 5,781 | 284 | 49 relic peer-price corrections; 556 changed rows assessed; six Dofus at 10m |
| Cosmetics and companions | 2,353 | 45 | Prices unchanged; two staff-role title publication holds |
| Bread, food, consumables and materials | 1,928 | 138 | 57 service/XP/bonus corrections; 244 changed rows assessed |
| Furniture, buildings, quest and miscellaneous | 2,987 | 190 | Nine denomination floors; 46 changed rows assessed; eligibility holds |
| Enchantment, sublimations and recycling economy | 794 | 23 | Eight explicit cap-discount decisions; 174 cross-category recycling floors |
| **Total disjoint ownership** | **18,816** | **847** | **No unassigned or overlapping references** |

Decision files and final reviewer attestations are in `manual-reviews/`; `manual-review-index.json` records exhaustive reference ownership and publication-hold reasons. `manual-overrides.json` contains 301 individual decisions, including eight explicit decisions to retain the automated capped price. 293 decisions change a price directly; ingredient-price propagation changes another 609 prices. Total changes relative to the initial automated proposal: **902**.

## Final revision and approval continuity

The first integrated reviewed file had SHA `d8acd33cfd41501b0e7caf02930f9c5c9d0a6cf1b3ac67a2381b44ece35dfba7`. The last advanced-equipment review found that the normal Dora N.I.O. (19432) rose to 5.1m after ingredient recalculation, while its equivalent unresolved-source variant (24103) still had the earlier 5m floor. The latter was corrected to 5.1m.

A complete row-dictionary comparison of the two reviewed files found **exactly one changed row: 24103**. Every other reviewer's scope remained byte-for-byte equal at row-value level. The advanced reviewer signed the current SHA after inspecting this correction. The economy reviewer updated the recycling audit for the same row and signed the current SHA. The parent accepts the other scope attestations through the demonstrated unchanged-scope comparison. Luna reran all 13 checks and the full final manifests after the correction.

## Deliberate policy exceptions

- All six structurally identified equipable Dofus cost 10,000,000 each. Dofus-named furniture, titles, auras, books, emotes and quest replicas do not inherit this premium.
- Four profession tools exceed their earlier 500,000 soft cap to cover their modeled ingredient costs. Global limits are preserved.
- Neopócimas 32701/32702 cost 5,800 instead of 170: each can produce 50 modern powder units priced at 110, with a 5% conversion margin. They exceed the 5,000 bread-family soft cap intentionally.
- Ordinary food remains capped at 15,000 even where a modeled recipe costs more. This is an explicit accessibility subsidy, not a claim that crafting that recipe is cheaper. Cost warnings remain visible.
- Eight expensive sublimations retain the 5m category ceiling despite input values up to about 24.4m. Reviewers explicitly accepted the convenience discount; ingredient-cost warnings and reasons remain visible. No claim of market-equilibrium pricing is made.
- Espada eterna (26593) and other unresolved functionality/progression objects have prices but publication holds. A proposed price is not permission to sell the item.

The final native expected-yield recycling audit covers 13,193 references and finds zero instances where modeled product shop value exceeds source-item price after the approved floors. This is an expected-value conversion check; random yield variance, actual instance eligibility and unrelated resale/exchange systems are not certified by it.

## Final scope and evidence limits

There are **1,769 publication-held items**. They remain priced so the requested coverage is complete; they should not be enabled until their specific hold is resolved. Hold reasons include administrator quality, quest progression, unsupported legacy rune functions, uncertain container contents and system eligibility. No shop products, balances, player inventories, catalog definitions or services were changed.

Pricing confidence remains separate from review status. Manual economic judgment does not manufacture missing acquisition evidence. 10,766 prices depend at least partly on unresolved source/ingredient estimates; they are reviewed design proposals, not observed market prices or proof of exclusivity. See `README.md`, `drop-evidence.md`, `craft-evidence.md` and `validation.md` for reproducibility and technical checks.
