# Final food and materials delta signoff

Reviewed artifact: `prices.csv`, SHA-256 `d8acd33cfd41501b0e7caf02930f9c5c9d0a6cf1b3ac67a2381b44ece35dfba7`.

Compared the final 1,928-reference food/materials scope against `.runtime/local/item-pricing-20261011/prices-before-review.csv`. There are 244 changed prices: {'resource': 171, 'food': 10, 'consumable': 58, 'refined_material': 3, 'bread': 2}. This supplements the initial 138-cohort review; the review focused on final changed distributions, all category-cap food rows, and individual recycling/extreme examples rather than rereading every unchanged object.

## Final decisions

- Accept the 57 manual service/XP/stat-bonus proposals and their publication holds. Their explicit utility progressions remain intact after regeneration.
- Accept recycling-driven resource increases. Examples: level-231 mythic resources 31762/31768/31780/31786 and conditional 32342 rise from 3,200 to 15,200; 29363/29369/29375/29381/29387 rise from 2,900 to 10,700. These prices establish a coherent floor against their retained expected powder output, rather than inventing harder drop probabilities. The earlier report's 3,100–3,200 late-game examples are superseded for these changed IDs.
- Accept bread-classified Neopócima de regeneración 32701 and definitive 32702 at 5,800 each, above the 5,000 ordinary bread ceiling. Their 50-unit powder output at 110 kamas produces 5,500 expected output value; 5% overhead rounds to 5,800. This explicit recycling floor exception prevents a contradictory economic loop. It does not assert that regeneration effects execute correctly, nor redefine ordinary healing bread prices.
- Accept the 15,000 prepared-food ceiling even where native recursive craft costs exceed it. This is a deliberate cheap-consumable shop policy. Most conspicuous: Huevos revueltos 22575 has 73,300 ingredient opportunity cost plus 1,577 labor per unit, Castañas 13108 has 47,200 plus 1,577, and Tarta de moras 22587 has 33,800 plus 1,637. Buying these meals can therefore be substantially cheaper than crafting from individually valued ingredients. Retain the warning flags. Raising meals above their category ceiling would conflict with the user's affordable-food preference; these are sales subsidies, not missing cost propagation. They do not create reverse arbitrage without a verified decomposition or resale route; this review does not certify an unexamined sell-back system.
- Accept propagated recipe updates: Cawota wey 17530 rises 17,000→18,000; changed refined orbs 31803/22488/27885 and meals 18574/18576/19154/19159 correctly reflect increased input cost. The 18,000 Cawota is a general utility consumable, not an ordinary daily healing bread.

Verdict: final proposed prices accepted for this scope with the existing publication holds and evidence limits. No additional overrides or holds requested. No database, services, combat or pricing pipeline changes performed by this reviewer.
