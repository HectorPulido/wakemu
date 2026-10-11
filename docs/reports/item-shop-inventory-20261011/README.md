# Native items, database and integrated shop inventory

**Use the [curated inventory](curated/README.md) for the current selection.** The full exports below are the original audit baseline and include objects subsequently excluded, including fragments and test records.

Audit date: 2026-10-11. Scope: this installed **Wakfu/Wakemu** client and its active PostgreSQL native catalog. No Dofus/Starloco server data is included. No shop products, player data or services were changed.

## Results

The active catalog contains 20,230 stack records, including sentinel reference `0` (`Ninguno`). The inventory preserves **all 20,229 positive references**, including internal/test/legacy objects. Catalog presence is not evidence of official availability, correct gameplay implementation or suitability for sale. There are 76 references without a native Spanish item name; these remain visible with blank names.

| Requested group | References | Download |
| --- | ---: | --- |
| Weapons and equipment, including tools, bags and set containers | 11,196 | [weapons-equipment.csv](weapons-equipment.csv) |
| Dofus-named items and accessories, including rings, necklaces and pet amulets | 2,229 | [dofus-accessories.csv](dofus-accessories.csv) |
| Actual pets and mounts | 179 | [pets-mounts.csv](pets-mounts.csv) |
| Cosmetics, titles, auras, emotes, appearances and related items | 2,270 | [cosmetics.csv](cosmetics.csv) |
| Haven Bag furniture, gems, displays, workshops, skins and related definitions | 1,586 | [haven-bag.csv](haven-bag.csv) |
| Healing registry plus bread, meals and drinks | 226 | [healing.csv](healing.csv) |
| Smithmagic, legacy runes, powders, hammers, transmutations, shards and sublimations | 901 | [smithmagic.csv](smithmagic.csv) |

Groups overlap intentionally; do not add their totals. 16,340 distinct references belong to at least one group. The remaining 3,889 are retained in [unclassified-items.csv](unclassified-items.csv), mostly other resources, quests and consumables outside the requested structural groups. [all-items.csv](all-items.csv) contains the complete positive-reference catalog. [summary.json](summary.json) records counts, release identity and input hashes. [native-types.json](native-types.json) contains the 199 native types, parent hierarchy, native Spanish labels and all 20,230 item/type/rarity mappings.

## Important distinctions

**Dofus:** [dofus-named-items.csv](dofus-named-items.csv) isolates the 42 positive references with `Dofus` in their Spanish item name. They include actual named objects, fragments, sculptures, cosmetics and titles. This is not a Dofus-game six-slot equipment catalog. Equipment evidence and native type identify what each record actually represents.

**Pets:** 136 native pet definitions and 43 mount definitions are included. Pet colors/appearances and mount harnesses belong to cosmetics. Pet amulets occupy the pet slot but are accessories; they are excluded from the actual-pet count.

**Healing:** [confirmed-healing.csv](confirmed-healing.csv) contains exactly the 62 references in the active native healing-effects registry. `confirmed_healing=True` in the broader food export means registry membership, not graphical or end-to-end gameplay acceptance. The 226-reference group also contains food candidates that may supply buffs or other effects. The registry itself includes two internal/test-type objects. [fish-resources.csv](fish-resources.csv) separately lists all 72 fish resource references; a raw fish is not automatically an edible healing item. Cooked fish are covered by their native meal type.

**Smithmagic:** all descendants of native root type 602 are retained, including obsolete runes and powders. The active sublimation attachment registry contains 388 entries whereas the client native Sublimaciones type contains 467 objects. Inclusion in this inventory does not imply all 467 have working attachment semantics. Likewise, socket templates identify eligible equipment; the 9,163 equipment socket templates are not 9,163 consumable runes.

**Haven Bag:** includes native root 295 descendants, including 121 enclosure definitions and 21 world-decoration plans. Native type names in the CSV distinguish these from ordinary personal-bag furniture; they should not all be advertised as placeable personal-bag furniture. The portable catalog has 1,270 item/template mappings and 1,440 templates, which are different quantities.

Every CSV contains reference, native Spanish name, category membership, evidence, native type/name, native rarity ID, level, equipment slots, maximum stack, use action/criteria and `!item <reference> 1`. Commands grant objects; they do not prove working learning, equipping or consumption. No client or player state was changed to generate the inventory.

## Database and shop

See [shop-review.md](shop-review.md) for schema, authentication, wallet, transaction and delivery details. PostgreSQL holds native definitions separately from owned inventory instances and shop products. Redis caches catalog reads; it is not the wallet or durable purchase authority.

The observed shop has nine enabled departments and **one article: Jalamartillo, reference 2027, quantity one, 1,000 kamas**. Its native OG/ogrine display mirrors the same account kama wallet. Purchasing checks the session, combat state, current price, native stack, empty inventory slot and balance; debit, grant and durable receipt commit together. Retry keys prevent duplicate charges. Pending world notifications survive interruption.

Publishing this inventory is separate work: the shop currently grants a single reference, has no multi-item bundle fulfillment and requires an empty slot. Search/featured responses and full-catalog serialization should be addressed before enabling thousands of products. Domain functionality must be checked before selling cosmetic learning, pet state, furniture or enchantment items as usable.

## Reproduction

Freeze a single active-release SELECT of `native_catalog_documents` to a private snapshot containing `revision` and a `documents` object. Include all `item-%` documents and `mount-models.json`, `haven-bag-furniture-catalog.json`, `native-finisher-items.json`. The audit snapshot is `.runtime/local/item-shop-inventory-20261011/catalog.json`; its hash is in `summary.json`. It contains no player instances or account data.

Export native types from the installed client:

```sh
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -proc:none \
  -cp 'client/lib/*' -d .runtime/local/item-shop-inventory-20261011 \
  tools/ExportItemInventoryTypes.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java \
  -cp 'client/lib/*:.runtime/local/item-shop-inventory-20261011' \
  ExportItemInventoryTypes .runtime/local/item-shop-inventory-20261011/native-types.json
python3 tools/inventory-game-items.py \
  --snapshot .runtime/local/item-shop-inventory-20261011/catalog.json \
  --native-types .runtime/local/item-shop-inventory-20261011/native-types.json
```

The cosmetic-action enrichment reuses `.runtime/local/cosmetic-review/native-cosmetic-actions.json`, previously extracted from the installed client. It is accepted only when its action ID and `bIt` class agree with the frozen published action record. Its input hash is preserved. General type ancestry and current published actions provide the other category memberships.

## Verification and one manual acceptance flow

See [validation.md](validation.md) for independently executed checks and their limits. This review does not claim that every item has been used successfully in-game.

For a complete smoke test of the **currently populated shop**:

1. Launch `bash client-tools/local-client.sh`, log in and select a character outside combat. Keep an empty ordinary inventory slot.
2. If necessary, on an administrator character run `!kamas 10000`. This adds 10,000 kamas. Record the resulting balance `B`.
3. Open the integrated shop. Expect nine departments, with Jalamartillo in Armas at 1,000 displayed OG; the starting OG balance must equal the account's kamas. Other departments have no products.
4. Buy one Jalamartillo. Expect reference 2027 in inventory and both balance displays equal to `B - 1000`.
5. Reconnect. Expect the same item and balance, with no duplicate item or second charge.

The native UI still labels OG as ogrines; this local implementation uses kamas. No purchase was executed as part of this read-only audit. Mass item-use acceptance requires a separately populated shop and qualified item domains.
