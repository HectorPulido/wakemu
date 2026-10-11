# Database and integrated shop review

Date: 2026-10-11. Scope: read-only source inspection, PostgreSQL SELECTs in an explicit READ ONLY transaction, and public local-shop GET requests. No catalog, wallet, inventory, services or server implementation was changed.

## Observed running state

PostgreSQL 17 runs as the Compose `postgres` service, database `wakemu_runtime`, user `wakemu`, published only on `127.0.0.1:15432`. There are 168 public tables. The shop is healthy at `http://127.0.0.1:18083/health`; its public article endpoint agrees with SQL.

Active native catalog revision: `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`, activated `2026-10-11 05:40:23.413808+00`. Its `item-stack-rules.json` / `items` collection contains **20,230 records**. This is the native item catalog, not the shop assortment and not a claim that every item has working gameplay effects.

The shop has **one enabled article**, not a populated game-wide catalog:

| ID | Key | Name | Item reference | Quantity | Price in kamas | Category |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | gobbhammer | Jalamartillo | 2027 | 1 | 1,000 | weapons |

All nine departments are enabled: `sets` (10), `items` (20), `weapons` (30), `appearances` (40), `pets` (50), `mounts` (60), `consumables` (70), `resources` (80), `haven-bag` (90); parentheses contain sort order. Only `weapons` currently has an article. One historical order exists and none awaits notification. No account identifiers or private order details were exported.

## Persistence model

`server/migrations/001_accounts_characters.sql` defines account ownership, characters, expiring generation-bound sessions and token digests. `002_inventory.sql` defines owned item instances and containers, a shared UID sequence, unique inventory positions and account/character foreign keys. `account_wallets` is the account-wide kama authority; the shop does not maintain a separate ogrine wallet.

`082_native_catalogs.sql` separates immutable native releases, original document bytes, indexed JSONB records and one active revision. Catalog definitions describe an item reference; `inventory_items` represents each owned instance using its distinct UID, owner, quantity, container and slot. Additional domain tables hold elements, mounts and other item state. An item's existence in the catalog does not establish that its consumption, equipment, learning or combat effect is implemented.

`102_shop.sql`, `103_shop_order_constraints.sql` and `107_shop_categories.sql` add:

- `shop_categories`: configurable departments with independent visibility and order.
- `shop_articles`: one item reference and fixed quantity per article, positive kama price, unique key, category foreign key and visibility flag. There is no native-item foreign key; application validation supplies that check.
- `shop_orders`: durable purchase receipts including account, selected character, request key, article, granted UID/reference/quantity, charged price, resulting balance and notification status. `(account_id, request_key)` is unique.

## Client and purchase flow

`client-tools/runtime/prepare-local-client.py` points native Shopi and HAAPI requests to the local HTTP shop. `server/shop-service/service.py` uses the same PostgreSQL Store as the world. `shop_http.py` translates native category, article, cart, order, payment and ogrine-balance contracts into the shop domain.

1. Browsing reads enabled articles joined to enabled departments. Balance and purchases require a valid API token joined to the same live session generation. Game tokens are rejected.
2. The adapter creates an in-memory, token-bound cart for exactly one fixed article. An order must precede payment; currency, amount and selected references are checked. The cart freezes the displayed price.
3. `shop_domain.py` locks the account, authenticates again, replays an existing durable receipt for a matching request key, locks the selected character, rejects active/placement combat, and reads the current enabled article/category with share locks.
4. It checks the server-loaded native stack rule and fixed quantity, finds an empty usable inventory position, conditionally debits the shared wallet, grants a native inventory instance and inserts the receipt in one transaction. Any failure rolls back debit, grant and receipt.
5. `shop_refresh.py` reads pending receipts in batches of up to 100. The world periodically checks outside combat, reloads committed inventory and balance, sends insertion/synchronization/equipment/wallet packets, then acknowledges the sent receipts. Interrupted delivery remains retryable. Packet transmission is not a client-render acknowledgement.

The native interface labels the currency `OGR` and payment mode `OG`, but **1 displayed ogrine equals 1 kama from the same account wallet**. This implementation does not integrate a real-money payment provider.

## Administration and bulk-inclusion implications

`admin_domain.py` supports listing, creating and updating categories/articles with audit records. Article writes validate reference and maximum stack against the active SQL native catalog. The admin item browser searches that catalog; finding an item there does not add it to the shop.

The six requested inventory groups need a classification/mapping layer before shop inclusion: current departments do not directly model accessories, Dofus-like relic terms, titles/auras, healing-only consumables or smithmagic subdivisions. Departments are data, so adding those does not intrinsically require changing the purchase protocol.

Important current limits:

- One article grants one reference at one fixed quantity. No multi-reference sets, selectable variants or multi-article baskets are implemented, despite the existing `sets` department.
- Titles, emotes, auras and cosmetics can only be sold through this path when an appropriate supported item grants the intended learning/effect. There is no direct title/aura/entitlement action in shop fulfillment. Cataloguing these definitions separately is necessary.
- Each purchase requires an empty inventory slot and creates a new stack; it does not merge into an existing partial stack. Mount grants require quantity one.
- Native support validates stack identity/quantity, not all gameplay effects. Pet, mount, healing, cosmetic, furniture and enchantment usability must be qualified against their own domain implementation before being advertised as functional.
- Article descriptions and names are stored once, without per-language localization. Article images are empty; categories share a one-pixel placeholder icon.
- `catalog-pages:get` paginates up to 100 entries, but loads and serializes the full enabled catalog first. Search returns all name matches without pagination; the featured-group response contains all scoped articles. A 20,230-item shop should address this before bulk publication.
- The page response advertises ascending virtual-price sort, while domain SQL actually orders by department then article ID. There is no implemented client sort/filter engine beyond department and name substring search.
- Carts expire after one hour and are lost on shop restart. Receipts remain durable, but the adapter cannot reopen a lost cart to retry its payment. Durable receipt deduplication prevents double debit for a surviving retry key.
- Admin validates against the active SQL catalog; purchase stack rules are loaded into process memory. Catalog activation must keep shop and world runtime catalogs aligned. This review did not assert equivalence of every deployed module to the concurrently changing checkout.
- No stock decrement, promotion engine, refund operation or multi-item shipment is present in the reviewed purchase path.

## Verification and acceptance

Observed checks: explicit read-only SQL succeeded; health returned `{"status":"ok"}`; `GET /en/shops/WAKFU_INGAME/articles` returned exactly the SQL article above. These checks did not purchase an item.

Existing automated coverage comprises seven HTTP tests and eleven isolated PostgreSQL shop tests. They cover native article shape, department visibility, valid and tampered chosen references, session-bound carts, ordering/payment requirements, stale sessions, wrong tokens, price changes, insufficient funds, full inventory, grant/receipt rollback, concurrent idempotent retries and retry-until-acknowledged delivery. `server/shop-service/verify-native-contract.sh` also exercises installed Java native serializers/deserializers. Test execution for this review is coordinated by the parent worker; source inspection alone is not a fresh test pass.

Offline command: `PYTHONPATH=server:server/tests python3 -m unittest test_shop_http`. PostgreSQL tests additionally require `WAKFU_RUN_SHOP_POSTGRES_TESTS=1`, `WAKFU_POSTGRES_TEST_URL` pointing to an isolated non-runtime database, and any needed password-file configuration. The harness refuses databases named `wakemu` or `wakemu_runtime`; never point this suite at the live database.

Current-shop manual acceptance: log in, select a character outside combat with at least 1,000 kamas and one empty inventory slot, open the integrated shop, inspect Armas, and buy Jalamartillo once. Expect reference 2027 to appear in inventory, the kama/OG display to decrease by exactly 1,000, and the item/balance to persist after reconnecting. Other departments currently display no articles. No command for changing the user's balance is necessary for this read-only review; the operator can use the established admin wallet controls if preparing a separate test account.
