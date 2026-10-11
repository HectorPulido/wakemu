# Shop interface: opportunities and implementation boundaries

Research date: 2026-10-10. Research only; no deployment, purchases, database changes or service restart. Issue 42 remains pending. This document expands the design space without changing the requested first delivery: a microservice, database-configured item offers and prices, initially 1,000 kamas, with direct item delivery.

## Evidence and confidence

- Installed client configuration exposes separate `shopiUrl`, HAAPI URLs, external payment URLs and services URL (`client/config.properties:303–317`). The shop is not exclusively a world TCP packet feature. A local HTTP compatibility service is a plausible integration path; configuration alone does not prove authentication or purchase compatibility.
- Native client and SDK investigation is recorded in [CLIENT-CAPABILITIES-20261010.md](CLIENT-CAPABILITIES-20261010.md). Distinguish UI consumers from methods merely present in a bundled SDK.
- Existing official capture records that the shop was opened (`.runtime/official-dungeon-capture/observations-first-room.json`). A shop opening is not evidence of a successful purchase, HTTP schema, delivery receipt or retry contract. Capture provenance differs from the installed client; verify against installed consumers.
- Official support documents products beyond ordinary items: cosmetics, boosters and services; account capacities include character slots, Haven Bag chest slots and aptitude/spell/equipment pages. Official services demonstrate product concepts, not support already implemented in Wakemu.
- Existing server supports an account wallet, owned inventory, cosmetic learning and delivery receipts. No shop implementation was identified in the reviewed source paths.

## Opportunity matrix

The feasibility column describes implementation direction, not completed functionality.

| Opportunity | Player experience | Feasibility and dependency |
| --- | --- | --- |
| Organized item catalog | Equipment, consumables, crafting materials, seeds, bags and other valid native objects grouped by purpose | Strong initial fit; whitelist native references and validate each product's usable behavior |
| Cosmetics boutique | Costumes, titles, auras, finishers and supported appearances | Existing owned-cosmetic and learning foundations; distinguish consumable unlock items from direct account grants |
| Mounts and pets | Obtain supported companions and appearances from a catalog | Validate item initialization, ownership and equipment behavior; an icon in the catalog does not implement the underlying feature |
| Haven Bag furnishing | Decorations, furniture and supported housing content | Reuse item delivery and existing learning/placement systems; check issue 26/41 dependencies |
| Bundles | A starter kit, profession kit, decoration set or seasonal cosmetic set in one offer | Store offer contents as multiple reward rows; all rewards and payment succeed or fail together |
| Visual showroom | Inspect product descriptions and try supported appearances before buying | Native preview/probador exists; supported content types require consumer verification; custom assets need client distribution |
| Featured storefront | Banners, curated categories, highlighted articles and seasonal collections | Native navigation/presentation foundations; verify asset URLs, dimensions, cache invalidation and supported actions |
| Scheduled offers | Weekend collection, event shop, daily rotation and limited availability | Native adapter consumes `countdownTo`; enforce actual dates on server |
| Promotions | Temporary discounts and before/after prices | Native adapter consumes promotions and original prices; server calculates authoritative amount and handles stale offers |
| Limited stock and quotas | Global stock, one purchase per account, daily/weekly allowances | Database stock and quota locks; remaining-stock and quota explanations may need UI adaptation |
| Gifts and compensation | Free event reward, welcome kit, maintenance compensation, tester reward | Custom server policy and claim receipts; free/zero-price checkout and native gift UI need validation |
| Achievement/event redemption | Spend dungeon tokens, profession points or event currency | General cost model can support this; native currency labels, balances and checkout may require client changes |
| Barter | Exchange a configured list of resources for an item or bundle | Atomic item consumption plus reward; native shop is not proven to display multi-resource costs |
| Character services | Name, appearance or class change; supported restat service | Dedicated validated domain operations; cannot assume granting an arbitrary potion implements the service; class changes affect spells/builds/equipment |
| Account capacity services | Character slots, build pages or chest compartments | Requires per-account entitlement storage and native refresh; current character capacity is a runtime policy, not a purchasable entitlement |
| Timed privileges | Temporary convenience benefits or booster-like products | Entitlement duration, expiration and affected systems require implementation; combat/XP/drop bonuses extend scope substantially |
| Collection-aware offers | Hide owned unlocks, prevent duplicate cosmetics, recommend missing pieces | Ownership checks available in backend; confirm native owned/disabled article presentation |
| Different audiences | Starter, advanced, event or administrator catalog | Server-side eligibility by account/progression; never rely only on hidden categories |
| Test environment catalog | Class equipment packs and reproducible test kits | Useful for acceptance testing; expose through explicit test/admin policy, not the public production catalog |
| Exchange interface | Reuse stone listing/purchase/cancel/modify screens for an exchange feature | Native flow exists, but is specialized; not evidence for a general player marketplace or arbitrary barter |
| Account gifts to other players | Buy a reward for another account or character | Recipient selection, abuse rules and delivery ledger are additional work; native gifting has not been certified |
| Purchase history and support | Receipts, recovery and audited compensations | Backend ledger is straightforward; an in-game history/refund screen is not yet established |
| Coupons or codes | Claim an event code or discount | Requires redemption backend and a verified native entry point or added UI; do not infer from generic SDK support |

## What can be configured, and what needs code

After a compatible service exists, categories, localized names/descriptions, images, offer order, native item references, bundle quantities, prices, activation dates and basic eligibility can be database data. That does not mean the current server already accepts these settings.

Currency presentation, arbitrary buttons, new tabs, resource-cost tables, wishlists, subscriptions, battle passes, arbitrary 3D previews, player gifting and new assets must not be promised as configuration-only features. A backend can implement a policy while the installed UI still cannot explain it adequately.

Specifically, the installed article adapter branches on virtual payment IDs `OG` and `SW` and supports `FREE`. A generic SDK currency string does not establish a kama checkout. Fixed multi-reference packs have a native consumer; choose-one-of-many packs do not yet have a verified consumer. Conversion-stone exchange calls a separate HAAPI backend, not the Shopi catalog API.

The most useful early catalog structure is: equipment; consumables; professions; cosmetics; mounts/pets; Haven Bag; bundles; events; and, later, services. Only activate categories whose underlying delivery and use behavior are verified. The shop need not sell every native reference merely because the client can draw it.

## Architecture that preserves the first delivery

1. A Shopi-compatible HTTP microservice serves catalog and supported purchase contracts. Bind locally or to the existing internal network according to the client access path; preserve existing network boundaries.
2. Authenticate against local account/session authority. Do not reuse official authentication tokens or proxy purchases to official commercial services. Resolve the target account and character authoritatively; HTTP catalog access does not by itself select the recipient.
3. Keep shop article IDs distinct from native item references. Model offers, offer reward rows, localized presentation, costs, availability and orders. Initially every enabled offer has a 1,000-kama price stored explicitly in the database.
4. Execute purchase, account-wallet debit, quota/stock consumption, item allocation and receipt creation in one PostgreSQL transaction through shared domain code. A separate microservice must not create a debit-then-remote-grant failure window.
5. Publish inventory and wallet updates after commit. If the world session disconnects, durable state remains authoritative on reconnect. For asynchronous refresh, persist an outbox in the same transaction; retry notifications without repeating delivery.
6. Snapshot the accepted price and rewards in the order; use an idempotency identity tied to the authenticated buyer and request. Repeated confirmation must return the existing result. Reject reuse with changed parameters.

`server/wakfu_server/items/inventory_items.py:50` provides a local grant function, but it opens its own connection and requires an empty destination slot. It is not by itself an atomic shop transaction API, and it does not implement generalized overflow delivery. `maps/test_console.py` uses that API for `!item` and rejects full inventory. Do not implement purchasing by sending chat/admin commands or by separately executing `!kamas` and `!item`.

`storage/combat_drop_delivery.py` illustrates same-transaction receipts, binding, bag placement and temporary inventory. Its domain is combat rewards; extract/reuse an appropriate shared delivery primitive rather than fabricating combat drops for shop purchases or changing combat behavior. Decide explicitly whether shop overflow uses temporary inventory, a pending claim, or rejects purchase before debit, and verify the chosen native client path.

Kamas are account-wide (`account_wallets`), so purchases from two characters must serialize on the same wallet. Validate insufficient funds, signed-integer limits, item quantities, catalog revision, stale sessions, ownership, combat state restrictions and simultaneous stock claims. Displaying an Ogrine price while silently deducting kamas is not an acceptable final UI; verify currency labels/icons and balance refresh separately.

## Suggested delivery sequence

1. Prove the installed client's local shop opening, authentication, catalog, category, article detail and checkout contracts with an offline oracle and a minimal local response fixture.
2. Deliver original issue 42: database offers at 1,000 kamas, atomic direct delivery, wallet refresh, full-inventory policy, retry/reconnect recovery. No combat or spell changes.
3. Expand configuration to curated categories, descriptions, images, supported previews and bundles.
4. Add event rotations, one-time/free rewards and quotas where the native UI can communicate them.
5. Treat services, other currencies/barter, timed privileges and exchange reuse as separately reviewed extensions with explicit domain dependencies.

## Complete acceptance plan after implementation

Provide a deterministic seed command that prints the real article/item IDs and creates an ordinary item, a bundle and a supported cosmetic offer at 1,000 kamas each. No such command exists yet; do not invent one for the user to run.

The prepared system test should use two test accounts and two characters sharing one wallet, and cover: opening/navigation/search/pagination; product information/preview; successful purchase and exact balance; quantity and bundle contents; insufficient funds; full inventory/overflow; repeated confirmation; disconnect immediately after commit; reconnect and receipt recovery; simultaneous purchases; expired/disabled/stale-price offers; ownership and recipient isolation; cosmetic acquisition/use; and ordinary combat/spells after shopping. Give exact setup commands and expected balances once real implementation and fixtures exist. Initial setup can reuse the existing privileged `!kamas 10000` command, subject to configured command permissions.

## External primary references

- [Ankama: Getting and Exchanging Kama Stone](https://support.ankama.com/hc/en-us/articles/360026294214--WAKFU-Getting-and-Exchanging-Kama-Stone): specialized exchange UI, listing, cancellation, suggested rate, linked currency and rewards delivery. This is not direct kama checkout of ordinary catalog articles.
- [Ankama: Ogrest server FAQ](https://support.ankama.com/hc/fr/articles/18654252593425--WAKFU-Serveurs-monocomptes-Ogrest): character/chest/build-page capacities, account/server ownership boundaries and reward restrictions. Read as official product behavior, not local runtime policy.
- [Ankama: obtaining and using Ogrines](https://support.ankama.com/hc/fr/articles/29825538628497-Obtenir-et-utiliser-mes-ogrines): service examples and currency context.

The public store page could not be retrieved through the web tool during this review. Do not claim a complete current commercial catalog audit or infer installed-client compatibility from current website offerings.
