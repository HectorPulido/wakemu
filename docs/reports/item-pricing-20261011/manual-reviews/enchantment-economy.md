# Final manual review: enchantment and economy

The reviewer inspected every type/rarity/acquisition cohort, the source policy, native craft evidence, live server recycling implementation, and all eight capped sublimation craft conflicts. This is a pricing review, not in-game verification of each effect. No server or database mutation was performed.

## Scope decisions

- Preserve 464 sublimations (type 812). There is no verified effect-demand ranking that supports assigning individual premium tiers.
- Preserve publication holds on 253 legacy type 626 runes; pricing does not authorize their sale.
- Modern esquirlas 27083 and powder 27093 stay at 110 kamas each. Their verified drop routes avoid the unknown-source scarcity premium. Modern powder is not a removed legacy powder.
- Remaining enchantment tools, transmutations, and modern type 811 stat options retain their evidence-based provisional prices. Missing acquisition evidence is not proof they cannot drop or craft. No additional functionality holds are invented.

## All reviewed cohorts

| Group | Native type | Rarity | Acquisition | Count | Price range (kamas) |
|---|---:|---:|---|---:|---:|
| enchantment | 626 | 0 | unresolved_source_policy | 22 | 18,000–130,000 |
| enchantment | 626 | 1 | unresolved_source_policy | 66 | 16,000–19,000 |
| enchantment | 626 | 4 | unresolved_source_policy | 165 | 51,000–300,000 |
| enchantment | 628 | 0 | unresolved_source_policy | 1 | 18,000–18,000 |
| enchantment | 628 | 1 | unresolved_source_policy | 6 | 16,000–16,000 |
| enchantment | 628 | 2 | unresolved_source_policy | 1 | 22,000–22,000 |
| enchantment | 628 | 3 | unresolved_source_policy | 3 | 220,000–220,000 |
| enchantment | 628 | 4 | unresolved_source_policy | 17 | 41,000–41,000 |
| enchantment | 709 | 0 | conditional_drop | 1 | 6,700–6,700 |
| enchantment | 709 | 0 | unresolved_source_policy | 28 | 18,000–18,000 |
| enchantment | 811 | 1 | unresolved_source_policy | 17 | 16,000–19,000 |
| enchantment | 811 | 3 | unresolved_source_policy | 1 | 30,000–30,000 |
| enchantment | 811 | 4 | drop | 2 | 110–110 |
| sublimation | 812 | 0 | unresolved_source_policy | 3 | 850,000–850,000 |
| sublimation | 812 | 2 | conditional_drop | 84 | 750,000–930,000 |
| sublimation | 812 | 2 | drop | 2 | 690,000–690,000 |
| sublimation | 812 | 2 | unresolved_source_policy | 38 | 1,100,000–1,100,000 |
| sublimation | 812 | 3 | conditional_drop | 110 | 1,000,000–1,700,000 |
| sublimation | 812 | 3 | craft | 79 | 510,000–5,000,000 |
| sublimation | 812 | 3 | drop | 3 | 1,300,000–1,300,000 |
| sublimation | 812 | 3 | unresolved_source_policy | 40 | 1,400,000–1,400,000 |
| sublimation | 812 | 4 | conditional_drop | 76 | 2,100,000–2,500,000 |
| sublimation | 812 | 4 | unresolved_source_policy | 29 | 1,700,000–1,700,000 |

## Individually reviewed craft ceiling conflicts

These eight retain 5,000,000 kamas as an explicit category policy discount. Their modeled input costs are uncertain opportunity costs, not observed market prices. Several exceed the user’s absolute 10,000,000 maximum: no price within that maximum can both cover these modeled inputs and obey the requested ceiling. Keeping a discount is a deliberate choice, never evidence of a cheap recipe. Overrides carry this explanation even where the numerical price is unchanged.

| Ref | Item | Modeled input cost | Decision |
|---|---|---:|---|
| 24131 | Constancia | 6,037,000 | Retain 5,000,000 |
| 24137 | Confianza | 13,826,000 | Retain 5,000,000 |
| 25797 | Fuerza Hercúlea | 24,438,000 | Retain 5,000,000 |
| 25798 | Alternancia II | 16,837,000 | Retain 5,000,000 |
| 25800 | Sangre del Martirio | 24,438,000 | Retain 5,000,000 |
| 25802 | Aura de Llamas | 20,040,000 | Retain 5,000,000 |
| 27187 | Manejo: Daga | 9,640,000 | Retain 5,000,000 |
| 27188 | Manejo: Escudo | 16,837,000 | Retain 5,000,000 |

## Cross-category recycling and crafting audit

Audited 13,193 curated recyclable references against current product shop prices. 174 have expected product shop value above item price; 0 are equipment. All 174 are unbound in the native template. See `recycling-value-audit.csv` for complete rows, exact float32 yields and floor/ceiling quantities.

The largest ratio is regeneration neopotions 32701/32702: 170 kamas purchases one potion that recycles into 50 powder, whose direct shop replacement cost is 5,500 kamas. This undercuts direct powder purchase but does not generate kamas: recycling grants items and no verified buyback price is established.

Recommended economic correction: apply `max(current price, expected native recycling yield × direct product price × 1.05)`, rounded upward to 100 kamas, to these 174 template-unbound references. This preserves the current 110-kama modern powder/shard prices and establishes a procurement-consistency floor for bulk recycling. Expected yield is preferable to individually rounded maximum yield: the native implementation aggregates products across stacks and rounds once; a rare upward rounding event should not establish the deterministic price of every source item. This is a shop design floor, not a claim of observed market value or guaranteed runtime access.

`recycling-floor-suggestions.json` provides the exact 174 proposed overrides for root coordination with category owners; no other owner's prices were mutated. The highest proposed corrected price is 23,100 kamas. All 174 have no native DELETE criterion and are template-unbound; instance state and settings still apply. There are only two category-ceiling conflicts: 32701 and 32702 require 5,800 kamas against a soft bread ceiling of 5,000. Recommend an explicit 5,800-kama exception for both rather than reduce the modern currency price or violate the global 10-million limit. If the bread soft cap is treated as absolute, hold only those two instead. No equipment floor changes are required.

Native template-bound items cannot recycle; instance bindings, installed sockets, equipment in any build, container occupancy, DELETE predicates, and runtime-disabled references can also block conversion. Yield is rounded stochastically after aggregate product sums. The single-item intervals in the CSV are bounds, not guarantees for every member of a stack; the current template unidentified bonus is included. Template-level eligibility does not certify a player-owned item can recycle.

Alternative drops or harvests legitimately make a crafted item cheaper than its recipe ingredients; this is not a recipe-cost error. Category caps also create deliberate food, furniture, tool and equipment discounts, so capped-only craft items must remain visibly flagged. Cyclic recipes and unavailable criteria cannot establish ordinary cheap crafting. Excluded ingredients may still be procured in game, and batch outputs must remain divided by native yield.

Reviewed artifacts: `pricing-policy.json`, `prices.csv`, `craft-evidence.md`, `server/wakfu_server/items/recycling.py`, native recycling and binding metadata snapshots. No external market claims were introduced.
