# Shop catalog performance and native icons

Follow-up category correction applied2026-10-11: Dofub'huritu29456 moved from equipment to Dofus, preserving its7,300,000-kama price and active status. The live category API now returns six Dofus articles. Earlier five-entry counts below describe the initial deployment. No restart was needed; the revision trigger invalidated the cache. Future catalog imports must preserve this [category correction](../item-pricing-20261011/dofubhuritu-category-correction.sql).

Published to the local Wakemu shop on2026-10-11. Only `shop` was recreated; World, AI, admin, ecology and Redis container IDs remained unchanged. Active catalog remains11,765 articles;7,051 disabled references include all publication holds, duplicate variants and six ADMIN-quality objects.

## Behavior

The old adapter constructed every article object for every request and returned the entire catalog in home promotions. Home now contains at most24 representative products; page/search responses serialize only their requested slice, capped at100. Counts still report the full matching catalog. Item details and category membership remain available. Purchases, tokens, carts and wallet balances are never cached: fulfillment continues to validate current visibility and price in its PostgreSQL transaction.

`PublicCatalogCache` stores only public article/category rows in Redis (TTL300seconds), with a decoded local snapshot. Every request checks the PostgreSQL catalog revision. Statement triggers on both article/category tables advance that revision on committed edits, including operator changes and SQL imports. A repeatable-read database snapshot binds rows and categories to one revision. Redis outage/corruption falls back to PostgreSQL; local locking bounds concurrent fills. Startup warms the catalog so the first user does not pay the full cold load.

Native `gui.jar` icons were extracted by graphic ID and converted to optimized JPEG quality82, up to128px. JPEG uses an opaque darkRGB(32,32,32) matte as requested after the original PNG export. All18,816 images decode correctly and cover every active reference. The complete JPEG collection is26,139,505bytes versus100,429,550bytes for PNG,73.97% smaller. Only requested icons are downloaded. Transparent PNG originals remain private backups/legacy-compatible assets. Runtime requires no image conversion dependency.

Article `MediaImage`, game-action-reference images and category images use local `/item-icons/<reference>.jpg` URLs, matching the installed Shopi DTO/parser. Static responses use image/jpeg, ETag/304 and a24-hour public cache. Strict numeric paths and symlink checks prevent arbitrary file serving.

## Observed server results

Five local requests per endpoint after deployment:

| Endpoint | Previous bytes | Current bytes | Current median |
| --- | ---: | ---: | ---: |
| Categories |2,199|2,269|9.5ms|
| Home promotions |10,722,475|27,173|11.1ms|
| First20-item page |—|22,496|7.8ms|
| Search “Dofus prismático” |—|2,308|7.5ms|

Search also matches the separately named aura; exactly one equipable Dofus prismático is returned among matches, reference24110. Its JPEG is1,269bytes and returns304 with its ETag. Server request timings do not establish native GUI rendering time or graphical acceptance.

## Validation and deployment

35 distinct tests passed without skips: HTTP9, cache9, assets2, PostgreSQL purchase11, revision/bootstrap4. PostgreSQL tests ran in isolated schemas, both with all migrations and with the live001–123 baseline plus130DDL. Test-only no-op migration fillers124–129 satisfy the harness's contiguous ledger constraint; they were never applied to runtime. The bootstrap replay test proves normal later migration preserves the revision and invalidation triggers.

The live migration ledger was at123 while other owners'124–129 changes were pending. Only the idempotent130DDL was bootstrapped, under the standard migration advisory lock, **without inserting130 into schema_migrations**. This preserves the contiguous ledger. A later complete migrator applies and records124–130 normally, safely reapplying130. No unrelated pending migration or native catalog activation was performed.

Systems acknowledged the isolated shop scope; deployment used the atomic lock and a complete immutable private shop build context. Healthy image: `wakemu-shop:performance-icons-20261011`, SHA256 `353fe5a06896d36c5e446655bc5c467f2088375e8ef4e978b56dd56c9a24558f`. Seven critical packaged source hashes matched the captured manifest. No World/class/Systems deployment is implied. Lock/window released at18:19:16UTC.

Evidence: `.runtime/local/shop-performance-20261011/` contains test logs, image audits, before/after HTTP metrics, build log, complete context hashes and bootstrap receipt. Private catalog/order backup and previous container identities: `.runtime/backups/shop-performance-20261011/`. Rollback image: `wakemu-shop:before-performance-20261011`; revert only the shop image with a temporary Compose override, preserving the same single shop service. New revision objects are backward-compatible with the old adapter and need not be removed for rollback.

## Manual acceptance

1. Close the in-game shop and reopen it. Expect a short home selection with real item icons; compare perceived first-open delay with the previous full-catalog home.
2. Open Dofus: expect five products, one prismático, each priced10,000,000. Check representative equipment, pet, mount, food and Merkasaco categories for matching original game artwork. The JPEG matte is intentionally dark and opaque.
3. Search “Pan del abuelito Ditocas” (reference17863,130kamas), with inventory space and sufficient wallet funds. Buy one: expect one item and a130-kama debit. Reconnect and confirm persistence. Native OG/OGR display uses the kama wallet1:1.
4. Reopen the shop again. Icons should be reused from browser cache; ADMIN and duplicate variants must remain absent. Operator catalog changes must appear on the next request without restarting services.

## Dofus Ocre audit

The installed native item catalog has no equipable item named Dofus Ocre. Related objects are fragment23997, sculpture29657 and emote31580 (“Blandir un dofus Ocre”). Translations also mention Ocre in quests/effects/lore; those are not evidence of an equipable item template. The fragment remains excluded by the user's earlier rule.
