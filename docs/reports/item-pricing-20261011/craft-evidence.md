# Native craft evidence for item pricing

The read-only PostgreSQL export is pinned to native catalog revision `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`, document `craft-recipes.json`, SHA-256 `7d9acb8f733d0a93a137c3a55f6d73cbbabd9497198539a0f71125af4996ae1e` (6,473,768 bytes). The complete private snapshot and generated index are under `.runtime/local/item-pricing-20261011/`.

Run `python3 tools/export-item-craft-evidence.py` to reproduce `crafts.json` from the snapshot and current curated inventory. No database or services are modified.

## Coverage

- 5,449 recipes and 34,049 ingredient records, with zero native export errors.
- 5,178 distinct output item IDs; 5,144 remain in the curated sales inventory.
- 4,878 curated output IDs have at least one productive recipe supported by the current recipe authorization policy.
- 271 recipes have criteria or flags unsupported by the current runtime and must not establish an ordinary cheap procurement route.
- All recipes belong to at least one native station definition. Map instance counts are preserved; a missing world station does not imply no portable haven-bag station.
- 4,894 distinct ingredient IDs are retained even when excluded from sales. Exclusion from sales does not make an ingredient unobtainable.
- There are no direct self-input recipes. The ordinary dependency graph contains cycle `28362 → 29567 → 28362`; recursive costing must guard cycles and consider other acquisition routes.

## Costing contract

`by_item[reference].recipes` preserves profession ID, profession level, recipe ID, batch duration, ingredients and their quantities, batch output quantity (`yield_quantity`), station memberships, mapped station counts, criteria flags, and every raw native recipe field. `usable_for_cost` excludes unsupported criteria/flags and direct self input. `executable` denotes only supported recipe policy: actual execution still requires player profession, accessible station, ingredients and ordinary runtime authorization. These flags are not promises that an arbitrary player can craft immediately.

For each usable alternative, compute ingredient opportunity cost times quantities, add labor/access overhead, and divide by output yield. Prefer the cheapest reliable route, while recording more difficult alternatives. Avoid using the shop sell price as an ingredient acquisition floor: internal ingredient procurement costs and curated sales prices have different purposes.

`extra_raw` is the native ingredient `cvm()` field. Values 0–9 are preserved. Nonzero values are ubiquitous and cannot be treated as evidence of an unresolved ingredient selector. Only explicit item IDs/quantities are used; no substitutes or dynamic rules are invented. Recipe expressions, secret flags, and raw fields remain auditable. There is no verified separate kama fee in this export, so no direct currency charge is fabricated from unnamed raw numbers.

Validation reconciled 5,449 recipes and products, 34,049 ingredients and the source hash. The generator emits one recipe entry for every native product and retains output yield (some outputs contain multiple units), preventing per-batch costs from being incorrectly assigned per item.
