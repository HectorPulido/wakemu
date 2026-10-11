# Curated game item inventory

This is the recommended inventory after Hector's requested screening on 2026-10-11. It replaces the original unfiltered export for selection purposes. No native catalog definitions, owned player items or shop products were deleted or changed.

**18,816 positive item references retained; 1,413 excluded.** Of the retained items, 15,412 are in at least one requested group and 3,404 are outside those groups. Groups overlap.

| Group | Original | Retained |
| --- | ---: | ---: |
| Weapons/equipment, tools, bags and set containers | 11,196 | 10,525 |
| Dofus-named items and accessories | 2,229 | 2,155 |
| Pets and mounts | 179 | 179 |
| Cosmetics, titles, auras, skins and emotes | 2,270 | 2,199 |
| Haven Bag and related definitions | 1,586 | 1,506 |
| Food/healing candidates | 226 | 224 |
| Smithmagic/enchantment items | 901 | 794 |
| Dofus-named subset | 42 | 36 |
| Confirmed native healing registry subset | 62 | 60 |

## Files

- [Weapons and equipment](weapons-equipment.csv)
- [Dofus and accessories](dofus-accessories.csv), and [Dofus-named items only](dofus-named-items.csv)
- [Pets and mounts](pets-mounts.csv)
- [Cosmetics](cosmetics.csv)
- [Haven Bag](haven-bag.csv)
- [Healing/food candidates](healing.csv), [confirmed healing subset](confirmed-healing.csv), and [fish resources](fish-resources.csv)
- [Smithmagic](smithmagic.csv)
- [All retained items](all-items.csv), [other retained items](unclassified-items.csv)
- [Excluded objects with explicit reasons](excluded-items.csv), [counts and hashes](summary.json), [independent validation](validation.md)

## Screening rules

All fragments and fragment containers are excluded across every group, using Spanish, English and French names containing `fragment` and native fragment types 601, 687 and 810. This includes all six Dofus fragments. The enchantment currency Esquirlas is retained: it is a supported enchantment item, not a collectible equipment/Dofus fragment.

Other exclusions: names identifying administrator/moderator roles (eight additional objects excluded during the second review); missing Spanish names; explicit test/debug/WIP/placeholder name markers; native internal/test/WIP type families 727, 732 and 837; explicit obsolete/deprecated names, including generic `Objeto antiguo` and `Recurso antiguo`; legacy powder/rune types 682/683, set containers of type 604, `bIx` furniture sources absent from the native portable source mapping, nonpositive levels for weapon/armor/bag types; missing or invalid native inventory icons. Reasons overlap; their counts should not be added to get the number of exclusions.

Level zero alone does not establish an unfinished object. Level-zero items remain, including normal pets, skins, emotes, titles and enchantment shards. The stricter weapon/armor/bag rule excludes 49 level-zero definitions; this is a conservative selection policy, not proof that all 49 are unfinished. It also excludes leveling items such as Makabra equipment. The excluded export makes that tradeoff reversible. Words such as `antiguo` inside a specific legitimate item name, or `dummy` for a mannequin/training dummy, do not independently cause rejection. `L'Alpha, Beta, Gamma` is not treated as a beta build merely for its name.

Only two healing-registry objects were removed; both belong to internal/test native types. All 60 ordinary registry entries remain. The distinction between food candidates and documented healing effects is preserved.

## Graphics evidence and limits

Every retained object has its native inventory icon in the installed `client/contents/gui.jar`, with a valid TGA header and positive dimensions. The native lookup is `aLO.bwX -> bGT/bJq.Wt -> fpC.bwX -> aTv.zD(itemsIconsPath)`. `client/config.properties:166` identifies `icons/items/64/%d.tga`. All 20,230 source records were checked; 135 had missing icons, including sentinel reference zero, yielding 134 positive-reference missing-icon exclusions.

An inventory icon does not certify an equipped model, animation, appearance preview or server gameplay implementation. This is a statically screened selection, not a claim that every retained item is complete or works in-game. The original full export is preserved in the parent directory as audit evidence and is not the recommended selection.

## Reproduction

Compile and run `tools/ExportItemInventoryTypes.java` as described in the parent README. Its updated export includes native `gfx_id`. Generate icon evidence and filter:

```sh
python3 tools/audit-item-icons.py \
  --native-types .runtime/local/item-shop-inventory-20261011/native-types.json \
  --output .runtime/local/item-shop-inventory-20261011/item-graphics.json
```

Then run:

```sh
python3 tools/filter-game-item-inventory.py \
  --graphics .runtime/local/item-shop-inventory-20261011/item-graphics.json
```

The filter reads the frozen parent CSV/type snapshot and the installed three locale archives. Output contains each retained ID once and a separate reason-coded exclusion ledger. Source, locale, resource archive and output hashes are recorded in `summary.json`.

## Additional screening review

The user approved removing 104 legacy powder/rune references (types 682/683), 68 furniture-learning sources without portable mappings and 350 set containers (type 604): 522 additional unique exclusions. The user referred to the 68 furniture sources as “60”; the action follows the previously enumerated group. Haven World/enclosure objects remain unless independently excluded by the approved furniture-mapping rule. See [functional-review.md](functional-review.md) for the original candidate evidence. Same-name objects are not automatically deduplicated because item level, rarity, effects, binding and learning targets can differ. Quest `Prueba` objects translate to `Clue`/`Indice`, and equipment named `Vacío` translates to `Hollow`/`Creux`; these names are not test/placeholder evidence.

## Duplicate-name audit

[Duplicate review](duplicates.md) compares 3,303 shared-name groups containing 9,140 retained items. 3,232 groups have structural differences; 29 differ only in exported effect identity IDs and 42 match the compared records with coverage limitations. No duplicates were removed.
