# Live shop publication — 2026-10-11

Hector explicitly requested publication of the reviewed prices. This was a database-only change to the existing local Wakemu stack; no services were restarted and no world/combat/spell code was changed.

- Imported 18,816 distinct native references: 17,047 enabled and 1,769 publication-held/disabled.
- Prices and quantities match the frozen `prices.csv` (SHA-256 `ad7d7d30297d5fae083b81dfb0249667280cb630aa56818c93603507240c8d44`), with one item per purchase and prices from 100 to 10,000,000 kamas.
- Native catalog revision checked before and inside the transaction: `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`.
- Preserved article 1 / `gobbhammer`, updating Jalamartillo to 2,600 kamas, and preserved the existing order. Wallets and inventories were not edited.
- Enabled 11 categories; the empty Sets category is disabled. Equipment/accessories, Dofus, appearances, pets, mounts, consumables, resources, Merkasaco and forgemagic are organized separately.
- Private backup and reproducible transaction: `.runtime/backups/shop-prices-20261011/catalog-before.sql`, `publish.py`, `publish.sql`, `publish.log`.
- Initial COPY attempt rolled back before any change because of CSV line terminators; the corrected transaction passed all checks and committed.

A complete post-commit comparison of all 18,816 database references against the reviewed CSV found zero price, quantity or enabled-state mismatches; receipt `.runtime/backups/shop-prices-20261011/full-live-validation.json`.

Live HTTP checks returned 200: health; home promotions (17,047 targets, approximately 15.5 MB, 1.41 seconds locally); first catalog page (20 articles, total 17,047, approximately 18 KB, 0.26 seconds). The large promotion response is an existing adapter scalability limitation; native client rendering of the expanded catalog remains unverified. Existing product thumbnails remain limited.

## Manual acceptance

1. Close and reopen the in-game shop to discard its cached catalog/cart.
2. Check Dofus, Forjamagia, Merkasaco, consumables and equipment categories. Verify six equipable Dofus at 10,000,000 each, Jalamartillo at 2,600 and Albóndiga de tofu at 290 (native OG/OGR display represents kamas 1:1).
3. Buy one affordable food item with inventory space and sufficient kamas. Expect exactly one item and the displayed kama debit; reconnect and confirm persistence.
4. Check that retained/disabled progression objects and old runes are absent from purchasable results. Report any unusually slow home/category rendering; publication itself was verified by database and HTTP, not graphical acceptance.
