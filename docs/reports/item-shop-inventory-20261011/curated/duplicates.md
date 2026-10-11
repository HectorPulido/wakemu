# Same-name item review

Review scope: 18,816 retained items after the authorized legacy rune/powder, unmapped furniture and set-container exclusions. No duplicate items were removed by this review. Grouping uses the exact Spanish display name; different names and near spellings are outside this audit.

## Findings

| Classification | Name groups | Items | Interpretation |
| --- | ---: | ---: | --- |
| Structural variants | 3,232 | 8,892 | At least one exported structural field differs, even after effect identity IDs are removed. |
| Effect identity only | 29 | 126 | Exported effect payloads match after removing identity IDs; native effect references differ. Candidates for further verification, not proven interchangeable. |
| Exported record equivalent | 42 | 122 | Compared exported records match. Coverage gaps prevent claiming complete native equivalence. |
| Total | 3,303 | 9,140 | Items sharing a name. |

Across these groups, 2,428 have different levels, 2,872 different rarities and 165 different native item types. These counts overlap. Other differing sections include equipment effects (3,021 groups), exchange metadata (205), action rules (341), equipment conditions (81), stack rules (65) and furniture mapping (27).

## Examples and practical consequences

- **Laminadora**, IDs `12, 8887, 8888, 8889, 8890`: all share level 60, rarity 0, type 223 and icon 2230012. ID 12 has five effects; the other four have six, including resistance values of 1, 2, 3 and 4 respectively. Name, level, rarity and icon are insufficient to deduplicate equipment.
- **Amuleto de Gramilú**, IDs `9347, 9525, 9526, 9527`: same level 35, rarity 0, type 120 and exported semantic effect payload; effect identity IDs differ. This is a stronger deduplication candidate, but native effect references must be preserved until their other uses are checked.
- **Abeto de Nawidad**, IDs `10633, 28355`: same name and level, but native types 546 and 566, graphics, action rules and furniture mapping differ. A display name can cover different object representations or uses.
- **100 kamas**, IDs `14950, 15304, 16990`: exported use-action rules differ despite matching level, rarity and native type. Keeping one by name could change whether or how it can be used.
- **Alas de dragojabatillo**, IDs `16717, 28500`: exported records match, but both have no equipment-effect record. Their native type is 581 and level 0; this cannot establish that the underlying pet-accessory association or behavior is equivalent.

## Conservative recommendation

Keep structural variants. Review the 71 candidate groups (248 items) first before any further removal. The 42 exported-equivalent groups comprise 111 type-581 items, seven type-808 items, two type-764 items and two type-603 items; none has an equipment-effect record in this snapshot. Missing records are evidence limitations, not proof that items have no effects. Rarity 0 alone is not evidence of an invalid item.

No purchase delivery, inventory ownership, quest, recipe, pet-accessory association, hidden native field, equipped model or animation equivalence was asserted. Icon IDs are compared; actual image pixel equivalence is not checked. Array order is preserved conservatively. The semantic comparison removes the `id` key only inside equipment/healing effect entries for candidate detection only; it does not authorize merging records. Neither class licenses deleting references already used in inventories or other game data.

## Artifacts and reproduction

- [Group summary and differing sections](duplicates-groups.csv)
- [Per-item compared values](duplicates-items.csv)
- [Machine-readable counts](duplicates-summary.json)

Run from the repository root:

```sh
python3 tools/audit-item-duplicates.py
```

The script reads the retained CSV and frozen `.runtime/local/item-shop-inventory-20261011/` catalog, native type and graphics fields already present in the curated CSV. It compares every item-addressable catalog section, including effects, equipment rules, conditions, binding/exchange metadata, actions, sockets, recycling, stack rules, sublimations, finisher and furniture records where exported. Mount-model records keyed by reference are also compared; unexported native associations remain outside scope. It writes only these duplicate review artifacts.
