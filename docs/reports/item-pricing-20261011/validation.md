# Price proposal validation

Generated as an offline unit-price proposal for the curated Wakemu inventory. No shop products, balances, catalog records, database rows, or services were changed.

## Final audit

- Curated and priced references: **18,816**, unique and set-equal to `curated/all-items.csv`; category CSV partitions are disjoint and exhaustive.
- Final prices: **100–10,000,000 kamas per one item**, integer values within policy bounds.
- True equipable Dofus: **6** policy-listed references at 10,000,000 kamas; Dofus-named decorative rows are not assigned the premium by name.
- Manual review index: **18,816 / 18,816 references** covered across 847 cohorts and individual exceptions.
- Publication holds: **1,769** rows, with a hold reason recorded in the review index and output row.
- Manual override records: **301**. Compared with automated prices, **902** final rows changed: **293** direct price changes and **609** recursive recipe-cost changes to downstream items.
- Every output row has `quantity=1`. An absent native combat-drop match is described as unverified acquisition evidence, not proof that an item is unobtainable.
- Excluded inventory references remain outside the priced partition.
- Final equipment review matched reference **24103** to equivalent reference **19432** at 5,100,000 kamas after the material-floor recheck.

## Automated validation

Command: `PYTHONPATH=server python3 -m unittest tools.tests.test_price_game_items -v`

**13 tests passed.** Coverage includes synthetic rarity ordering, per-yield recipe costing, cycle handling, price bounds, recursive override propagation, exact curated and category partitions, Dofus premium selection, ADMIN holds, complete review-index coverage, hold-status consistency, direct versus propagated manual changes, excluded references, cautious drop semantics, and source/artifact hash verification.

Generator command: `python3 tools/price-game-items.py`

Final `prices.csv` SHA-256: `ad7d7d30297d5fae083b81dfb0249667280cb630aa56818c93603507240c8d44`.

## SHA-256 input manifest

These values match `summary.json` under `source_sha256`.

| Input | SHA-256 |
|---|---|
| `docs/reports/item-shop-inventory-20261011/curated/all-items.csv` | `98a1dbd47b0e06ec219c9271ad0db9ce465535c31a782c184276db5a1ad636d4` |
| `.runtime/local/item-shop-inventory-20261011/catalog.json` | `54294e13ed583f960c0103bbd05c2df40861eed708bf7aa72fc6fc32bab24970` |
| `.runtime/local/item-shop-inventory-20261011/native-types.json` | `90b8b4ff0ff6040fe09134f7f5acf049f41f387744b1df5bf662416a2af1e945` |
| `.runtime/local/item-pricing-20261011/drops.json` | `abd6b94f1bd7fe1067b776d256223b447d648aeef4a95c6e1423b2648ab80da3` |
| `.runtime/local/item-pricing-20261011/crafts.json` | `8bee3ebc21e3bb7ce51ca0ac94b9a1505147e1210a77ec98359b3869a3243df9` |
| `.runtime/local/item-pricing-20261011/plant-resources.json` | `94af9657e90c2b15d8556f624a88c8527ff73b8db849eefc278927764f95fcdd` |
| `docs/reports/item-pricing-20261011/pricing-policy.json` | `bd50c795e286663b31e9a35a29d5e3995a09987812430c347a5388b6fa46b70c` |
| `docs/reports/item-pricing-20261011/manual-overrides.json` | `eec5487ade8b3dd0511769766faacee9fc58faf8063f9285127836337313bf72` |
| `docs/reports/item-pricing-20261011/manual-review-index.json` | `708784357e034ed82a8ca5f0f4d8e2e5a708d49eda395543ad15a5b260c757e4` |
| `tools/price-game-items.py` | `f05b7b9a85634147025439d94d8fa5683548f27b45debdb7d9c2219306336d55` |
| `tools/merge-item-price-reviews.py` | `ac6f9d1250afa9087e44ef24a0c75815c3dd8a5e5e02fb6415636793b34e5f6c` |
| `.runtime/local/item-pricing-20261011/prices-before-review.csv` | `5087672ad6163e53fd6e583210b3486e24365fe781a39e399a971abb867b45a0` |

## SHA-256 generated artifact manifest

These values match `summary.json` under `artifacts_sha256`.

| Artifact | SHA-256 |
|---|---|
| `category-summary.csv` | `e703f4bf9a1d252b95bccf581844bc6513d67e2af9eeb1497bbee02d73f00f0a` |
| `price-list.csv` | `29c1ec7028e1e5295a85d1122e281d30e3e38e9e2082c2132ad693d4a0ae1e96` |
| `price-review-changes.csv` | `1b0b00992b6a2b6f6586fa9c46816f9f7c2f87e26654e556a92ace69e1337875` |
| `prices-aura.csv` | `2d6e563dc444ab55061511c42d95a108905e7d950c89db54e440eb66f782e24f` |
| `prices-bag.csv` | `483e7cf6736a6d2c1719a028b035e4ad8853c53ed92808f277f183b404b99f89` |
| `prices-bread.csv` | `3b624944aadac2fa88325b6bc6ca3ef9aee52cf4b0ee0027e15c68e1090f526a` |
| `prices-chest_upgrade.csv` | `c557b94fe9caa3f8c6567accd3b8f7a0dd028d6b4f08326c8ca0419f48e2e388` |
| `prices-consumable.csv` | `f5965621687c58ac7c4c6b229b34614030920af77e4e9f2a54cbc500b57f3ea9` |
| `prices-costume.csv` | `c6cc8f5a07545539e8aa9fd11b98038888efc84381c1e061c0ae2309ab561e83` |
| `prices-dofus.csv` | `fe6a0cb26f943a3ea1262123a213a47a89b06f6e1f376accfa32d64e35335e1d` |
| `prices-emote.csv` | `3b6d20fee19787c4d37da071cbc407b58a0220d7fae2cc1e9e30f0fd96fd36c5` |
| `prices-enchantment.csv` | `7a0b614eb7293f87570e5ea619607013930bc54458d3e63d15e43e80fa41c40c` |
| `prices-equipment.csv` | `ed9b10ffc7de0838a9bcdae4bc4ed8e218ee86dd6ebb66f32db61d2b35f834b0` |
| `prices-finisher.csv` | `8712a62706c4a644d9d42299091bf1e2c1354b39b4baf35f1523b1a2be11e0a1` |
| `prices-food.csv` | `54df2ea884c0f7c88c3b7d1f40e611e08ed7a703d9b354f2e1411ac6b8799279` |
| `prices-furniture.csv` | `b7bab2efc7acb7acc92e8b8c7588050eae3de56b720bec7d10cd2fa47253d1b0` |
| `prices-haven_gem.csv` | `e2a262ddebd286b392b562e264f9fa32eeca6aab9658266f5a52323759cf444e` |
| `prices-mount.csv` | `c62f925a922336c70d0e673c9ae3d453971d9c93f484af49ea827307ccf844ac` |
| `prices-other.csv` | `bbc3bd849b9e7ac9ce95eabbd7974c900d788a536c3b000c7cde624accb5fdb2` |
| `prices-pet.csv` | `cb0ba9544e18f08fc5c8e9396112fa98c6ec7b81069640848922da17b1b6c129` |
| `prices-pet_accessory.csv` | `048a53d47c9c344f969685dd22dd32798d8fb4d713dc1146dbba5c57b1c60f2c` |
| `prices-quest_token.csv` | `464d996c3f44a33f20e272c8d409925fda026d5841448169d81c7db379e7fa24` |
| `prices-refined_material.csv` | `c8b27bc484bdf056f012d732869b2c50b24cfad753bcd7c847cfe453d9816226` |
| `prices-resource.csv` | `88b0f5db5dc150453e783ab54cf7d0775a702d0033672dddf90f50ea63a013a0` |
| `prices-seed.csv` | `6e4f156e3d3018db60e674ea6e4abc095461864089d45fa10b869929798fee2d` |
| `prices-skin.csv` | `a0e836a2fba7d7afb1f0afdeccb1e0dcad4949cb5e4e7b583f483e32c74b82fb` |
| `prices-sprint.csv` | `d2f90d3ccdbb55111de7e24624cf8d3cb7f2f9584e6baa190408ea402e95d40d` |
| `prices-station.csv` | `3a14f6c2785204263a706a6c5ff677846039360121ac5fcdf28caf1957f2d85c` |
| `prices-sublimation.csv` | `7c6c425663c62ade510a5d33d77b10faf78468a5fd247e0f029553ca522008ae` |
| `prices-title.csv` | `44f7ab7d2ecd9bb81cb50d3f804a2dd72c30c877e222f570d61bcd73d558376a` |
| `prices-tool.csv` | `e751f147974604807b6fc0942a2c8bbedefe8b84112c4519e2c80524d1d0d52f` |
| `prices-world_building.csv` | `f41bfe17739b8dfca16899e47af271540ac824999ad597dd918f0c860133632b` |
| `prices.csv` | `ad7d7d30297d5fae083b81dfb0249667280cb630aa56818c93603507240c8d44` |
| `publication-holds.csv` | `b75e36adb1a44a0f32f0ec3efc0073727962e7159f79da97993cd4f9398fd0f1` |
| `review-queue.csv` | `4c181b943aa861e03d362c95b6ef2842fb3f4898789ceca546f62ee7c298e68d` |

All source and generated artifact SHA-256 values were verified against the files on disk by the audit tests.
