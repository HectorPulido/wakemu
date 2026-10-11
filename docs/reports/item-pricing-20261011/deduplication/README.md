# Highest-rarity shop selection — 2026-10-11

Hector requested removal of duplicate shop variants, keeping the highest rarity, and explicitly reiterated that administrator items must not be sold.

The effective shop selection is [catalog.csv](catalog.csv), derived from the frozen reviewed prices without changing unit prices. It supersedes the original 17,047-active publication: **11,765 active articles, 5,282 duplicate variants disabled, and 1,769 previously held references still disabled**. Native item references, recipes, inventories, orders and wallets are not deleted or edited.

## Selection rule

- Compare exact Spanish display name **and native item type** among publication-eligible references. Equal names with different functions/types remain separate; the earlier audit identified 165 same-name groups spanning different types.
- Keep the highest rarity using this explicit shop policy: RELIC > EPIC > PVP_SOUVENIR > LEGENDARY > MYTHIC > RARE > COMMON > UNUSUAL. This is not numeric native rarity order; souvenir is a special quality placed here by policy.
- Ties use higher item level, then higher native reference ID. Reference ID is only a deterministic tie-break, not evidence of stronger effects or functional equivalence. This intentionally simplifies variants with different effects, as requested.
- Never promote held items. Independently exclude native ADMIN quality10, internal/test type lineages727/732/837, and administrative/test markers in Spanish, English and French names. All six retained ADMIN-quality references remain disabled. Unrelated words such as the title “El alpha, beta, gamma”, the name “Eri Staff” or “Gwan Wabbit GM” are not alone proof of administrative status; existing functional holds still apply.
- Keep Dofus prismático24110 and disable20720. Five equipable Dofus now remain for sale, all at10,000,000 kamas.

## Operation and validation

Generate the plan with `python3 tools/deduplicate-shop-items.py`; publish with `--apply`. Publication backs up articles/categories, checks native revision and unchanged reviewed prices/quantities, takes a table write lock and updates visibility in one transaction. It does not re-enable articles. Private backup and receipt directory: `.runtime/backups/shop-deduplication-20261011/`. No service restart is required.

The earlier `prices.csv` and review manifests remain frozen as pricing evidence. Future shop imports must use this deduplicated visibility plan; replaying the earlier initial import alone would restore variants and is no longer the desired selection.

## Verified result

The transaction disabled exactly5,282 duplicate articles. Independent exhaustive group recalculation matched the plan, all prices stayed unchanged, and database visibility matched11,765 active/7,051 disabled. Six ADMIN-quality references and all1,769 original holds are disabled (the six ADMIN references are included in those holds). No prohibited es/en/fr admin/test names or internal type lineages were found among active references. HTTP pagination reports11,765, and the Dofus category returns exactly five entries with one prismático. The previous single purchase receipt remains intact. Evidence: `.runtime/backups/shop-deduplication-20261011/validation.json`, `publish.log`, `page-response.json`, `dofus-response.json`. The validator initially tried a nonexistent Dofus-specific route; the correct category-based native shop API was subsequently checked successfully.

## Manual acceptance

Close and reopen the in-game shop. In Dofus, expect five entries and one Dofus prismático at10,000,000. Search for a multi-quality item and expect only its highest-quality same-type variant. Existing owned lower-quality items must remain in inventories. ADMIN-quality items must be absent from shop search and direct purchase. A normal affordable purchase should still grant one item and debit the displayed kama price (native OG/OGR uses the same wallet1:1).
