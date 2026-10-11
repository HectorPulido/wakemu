# Functional shop readiness review

**Historical candidate audit:** the user subsequently approved removing the 104 legacy powders/runes, 68 unmapped furniture sources and 350 set containers. Those 522 distinct references are now excluded. The counts below describe the pre-removal inventory. Haven World/enclosure items were not excluded by type; nine overlap the approved unmapped-furniture group. See the current README and summary for authoritative counts.

Read-only analysis of the curated 19,338-item inventory and native catalog snapshot revision `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`. No database, server, or service changes. These are review candidates, not additional exclusions or proof that the native items are incomplete.

| Candidate group | Count | Reason to review before selling |
|---|---:|---|
| Legacy powders and runes, native types 682/683 | 104 | Separate from the current enchantment shard catalog; verify their actual transformation/consumption route. |
| Haven World / enclosure items, types 652/853 | 142 | 21 Haven World items and 121 enclosure-building items; these belong to systems other than ordinary Haven Bag furniture. |
| Furniture-learning sources missing portable mapping | 68 | A native `bIx` use action exists, but no current furniture mapping has that item as `source_item_ref`. |
| Set containers, type 604 | 350 | All use `bIl`; they are packaged sets, not individual wearable equipment. Verify unpacking before selling. |

The candidate CSV contains 664 rows and 655 distinct references (nine items occur in multiple candidate groups). Predicates are applied independently to all-items.csv, not only category CSVs; category classification may not capture all subtypes. Existing curation remains authoritative and unchanged.

## Evidence and limits

- `server/wakfu_server/items/haven_bag_furniture_knowledge.py` requires action class `bIx`, no native use criteria, and at least one `_source_refs()` mapping; it explicitly rejects a source with no native template mapping. The 68-item predicate compares each retained `bIx` reference to all `source_item_ref` values in snapshot `haven-bag-furniture-catalog.json`. Examples: 14316 Vitrina de Krosmaster Arena, 14317 Mesa de Krosmaster Arena, 14423 Biblioteca básica, 14737/14738 Maniquí masculino/femenino. These may require another system or catalog expansion; this does not prove missing artwork. There are also 1,262 retained `bIx` sources with a mapping.
- Types 652 and 853 identify Haven World and enclosure buildings in the native type catalog. Some have `bIx` mappings, so a type alone does not prove that every item is unusable. Examples include 17069 Plano de decoración de la casita de Amakna and 17073 Puerta clásica. Keep their system classification separate from corruption checks.
- Types 682 and 683 contain 52 powders and 52 runes. Current `item-shard-effects.json` describes the enchantment bonuses, while `socket_enchantment.py` validates socket bonus installations against native shard metadata. Do not assume legacy rune installation is implemented merely because recycling exists. Conversely, `recycling.py` explicitly supports both `SHARD` and `POWDER`: the word powder alone is not a removal rule. Modern recycling powder 27093 must not be excluded by a generic name search.
- The retained 350 type-604 objects all use action class `bIl`. No `bIl` implementation or set unpacking authority was found in the reviewed server domain. `inventory_actions.use_request` only returns metadata, and does not implement arbitrary effects. Classify these as containers pending functional confirmation rather than defective equipment. Example: 12903 Set justiciero. Do not delete the individual armor pieces.

## Sublimations: preserve

All **464** retained type-812 sublimation scrolls have an installed pattern definition: 385 appear in snapshot `item-sublimations.json`, and 79 additional EPIC/RELIC references appear in `server/migrations/124_native_special_sublimation_eligibility.sql`. Comparing only to the JSON would falsely flag those 79. `sublimation_eligibility.pattern()` reads enabled PostgreSQL patterns and verifies the native client checksum and kind. The implementation supports BASIC, EPIC and RELIC. This review checked snapshot/migration coverage; it did not requery live enabled rows or test every item manually.

## Suggested next curation rule

Keep validity and shop readiness separate. Quarantine the above candidates from a first shop release until their complete use path is confirmed; preserve their native definitions. Never deduplicate by display name: level, rarity, effects and native reference can intentionally differ. A broader final readiness audit should check mount models, cosmetic learning authorities, furniture templates and item use predicates before promising that every retained item works end to end.
