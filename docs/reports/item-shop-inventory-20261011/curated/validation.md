# Curated inventory validation

Review date: 2026-10-11. This verifies the filtered outputs against `all-items.csv`, the native type hierarchy, Spanish/English/French item names, the frozen native graphics export at `.runtime/local/item-shop-inventory-20261011/item-graphics.json`, and the catalog snapshot used for portable furniture mappings. It does not certify that retained items work in gameplay.

## Results

The input has 20,229 unique positive references. Curated `all-items.csv` and `excluded-items.csv` form a complete, disjoint partition: 18,816 retained and 1,413 excluded, with no missing, extra, or duplicate references. Every retained row has an empty rejection-reason field, and every excluded row has at least one reason. The requested added filters account for 104 legacy powder/rune objects (native types 682/683), 68 portable furniture action objects (`bIx`) without a source mapping, and 353 set containers (native type 604). These selections are absent from the retained inventory. Three of the 353 raw set containers were already excluded by earlier rules, so the newly authorized pass removed 350 sets and 522 additional unique references in total.

All 18,816 retained rows have a Spanish name and a verified existing native icon with a valid TGA header. No retained reference has “fragment” in its Spanish, English, or French name. Every retained category CSV is duplicate-free and a subset of the retained IDs. The generated CSV hashes match `summary.json`; that summary also records the source, locale, catalog snapshot, and graphics evidence hashes.

| Curated output | Rows |
| --- | ---: |
| All retained items | 18,816 |
| Weapons and equipment | 10,525 |
| Dofus accessories | 2,155 |
| Pets and mounts | 179 |
| Cosmetics | 2,199 |
| Haven bag | 1,506 |
| Healing | 224 |
| Smithmagic | 794 |
| Confirmed healing | 60 |
| Dofus-named items | 36 |
| Fish resources | 72 |
| Unclassified items | 3,404 |

Category rows overlap and must not be summed to infer unique item counts. The reason totals below also overlap:

| Exclusion reason | Rows |
| --- | ---: |
| Internal test/WIP type ancestry | 154 |
| Missing native item icon | 134 |
| Obsolete name | 342 |
| Nonpositive equipment level | 49 |
| Test/beta/debug name | 26 |
| Missing Spanish name | 76 |
| Fragment name/container | 191 |
| Staff role name | 16 |
| Native fragment type | 104 |
| Set container | 353 |
| Missing portable furniture source mapping | 68 |
| Legacy powder or rune | 104 |

The native Merkamundo and enclosure branches (types 652 and 853) contain 142 source rows; 133 remain curated. All 133 appear in Haven Bag and none appears in weapons/equipment. Modern powder reference 27093 (`Polvo` / `Powder`) and current shard currency 27083 (`Esquirlas`) remain. Of 467 source rows with native type 812, 464 sublimation scrolls remain; the three excluded rows are lunar fragment items. The two EPIC/RELIC sublimation pouch references 26334 and 31740 also remain.

## Hashes

SHA-256 values below are recorded by `summary.json`:

| Evidence | SHA-256 |
| --- | --- |
| Source `all-items.csv` | `3593a9e9e9975d2c232d4a2dcab7b7aed870c90a68cc0e8c5a0f8380c25bcd07` |
| Source `native-types.json` | `ab3fb867f0aa62dfac8502948566078035fb648286f310ac8e2feceacbc4176a` |
| Graphics evidence JSON | `307a7521358a37dadbbafb97f3ad5e497f8ed88af05a8745c2333d198cced46d` |
| Haven furniture catalog snapshot | `54294e13ed583f960c0103bbd05c2df40861eed708bf7aa72fc6fc32bab24970` |
| Installed GUI archive | `1e49268704d1e787590e666efc30381aca40486efaefd9f490c800dddcc44752` |
| Spanish locale archive | `7a1e3247388f5e771e31f2ea1e4db7a2c7dc48d4108b71dae04789e7966ce7c8` |
| English locale archive | `a9a077c6805fbfc9caa28d1b398b1c1ec95e3df035f7f3853ace9d82e2d11830` |
| French locale archive | `12cab5e8b0959cf4cbafa0b675a77da4305a3a45777454239c1cee53f0ba3530` |

Output CSV SHA-256 values are listed individually in `summary.json` under `artifacts_sha256`.

## Predicate review

The filter checks localized names in all three locales. It rejects names containing “fragment” and native fragment types 601, 687, and 810; staff-role names; explicit test, debug, WIP, placeholder, beta, obsolete, and deprecated markers; and descendants of internal test/WIP roots 727, 732, and 837. Empty Spanish names are rejected. The level rule follows native type ancestry and removes nonpositive-level equipment beneath the configured weapon/armor/bag roots. Missing icons, invalid TGA headers, legacy type IDs 682/683, set-container type 604, and unmapped portable furniture `bIx` sources are also rejected.

The icon audit checks asset presence and TGA headers. It establishes a usable inventory icon path, not an equipped model, animation, appearance preview, or server implementation. Localized-name matching, native type ancestry, and the current furniture source catalog remain curation inputs and heuristics.

## Limits

These checks validate the declared predicates, the partition, and output integrity. They do not establish item usability, shop readiness, or gameplay completion. Exclusion decisions are reviewable and reversible through the source inventory and reason-coded exclusion ledger; no catalog or player data was changed.
