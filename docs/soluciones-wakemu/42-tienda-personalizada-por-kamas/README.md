# 42. Custom shop paid with kamas

**Performance and artwork:** [Redis cache, bounded catalog responses and native JPEG icons](../../reports/shop-performance-20261011/README.md) are deployed to shop only. Native expanded-shop graphical acceptance remains pending.

**Current selection:** [Highest-rarity deduplication](../../reports/item-pricing-20261011/deduplication/README.md) leaves **11,765 active articles**. The original publication counts below are historical; all administrator-quality and previously held articles remain disabled.

**Status: 🧪 Expanded catalog published; expanded native client acceptance pending.** Hector confirmed successful native Jalamartillo purchase on 2026-10-10. On 2026-10-11, the reviewed catalog was published with 17,047 active and 1,769 disabled articles, priced at 100–10,000,000 kamas per unit. See [publication evidence](../../reports/item-pricing-20261011/publication.md). This database-only publication required no service restart. The historical pilot below records its original price and deployment.

## Scope and evidence

The [local administration panel](../../reports/admin-panel/README.md) now manages
shop articles, categories, visibility, units per purchase, and kama prices, and
shows confirmed orders. It runs at <http://127.0.0.1:18084> with separate private
operator credentials. Catalog changes take effect without restarting the shop.

Implement a custom server shop using kamas, never real-money payments. The user opened the official shop to provide a UI/protocol reference only; its commercial catalog and payment system are not the requested implementation. Configure products, quantities, availability and kama prices in the database. Purchase must debit kamas and grant items atomically, preserve overflow handling, reject insufficient funds and prevent duplicate purchases on retries.

The 2026-10-10 follow-up explicitly allows Ogrines and kamas, including a shared balance when native kama checkout is unavailable. The installed adapter recognizes OG/OGR rather than a kama payment mode. The pilot therefore displays Ogrines backed by the same authoritative kama wallet, at 1:1; it does not create or sell official Ogrines.

## Deployed pilot (2026-10-10)

- Shopi/HAAPI microservice: localhost `18083`; profiler remains on `18082`.
- Database article `1`, key `gobbhammer`: **Jalamartillo / Gobbhammer**, native item `2027`, quantity `1`, price **1,000 OG = 1,000 kamas**. Home highlight and Wakemu category expose the article.
- Products and prices live in `shop_articles`; completed purchases and pending world notifications live in `shop_orders`.
- Authenticated world login issues a local, generation-bound API key. The client exchanges it for Shopi bearer access and reads the shared wallet through local HAAPI.
- Purchase debits and grants within one PostgreSQL transaction. Cart retries reuse the order identity. Disabled articles, stale prices, expired sessions, combat and insufficient funds are rejected. Full inventory is rejected before debit in this pilot; deferred overflow delivery is not implemented.
- Connected world refreshes inventory and kama balance after commit. Unsent notifications remain durable; reconnect loads authoritative ownership.
- Complete world image `wakemu-world:shop-20261010-r74`; migrations through `104` applied. The complete image matched all 720 packaged source/migration files at the deployment comparison. Later concurrent edits require their own validated deployment.
- Existing world image retained as `wakemu-world:before-shop-20261010`. Private state backup: `.runtime/backups/shop-20261010/state-before.dump`; it excludes immutable native catalog document/record data, which remains covered by the existing native catalog backup. No credentials or private backups are committed.

Validation: 15 shop HTTP/PostgreSQL checks passed, including concurrent retry and rollback; 21 inventory/delivery regression checks passed; 74 selected inventory, replay, combat-wire, ecology coordination and guild checks passed. Shop tests passed again after migration continuity correction. Native Java article/category/promotion/payment parsing, API-key packet decoding and local network guard checks passed. Automated checks are not manual client acceptance.

### First manual attempt and cart correction

The user's first attempt confirmed native opening, shared balance `2,407`, product detail and `1,000` price. Checkout failed with `cartCreation400`; no purchase receipt or debit occurred. The client sends fixed `single_references` in `chosen_references` too. The initial HTTP validator incorrectly rejected every nonempty chosen-reference list.

The corrected adapter accepts the exact configured reference ID, line number and quantity and rejects altered selections. The native probe now serializes the outbound request using the client's actual `cca.b(SingleReference)` path and feeds that JSON back into the adapter. Six HTTP regression tests and the native probe passed. A live authenticated HTTP check passed cart creation, payment-mode retrieval and order creation without executing a payment; the temporary cart and API token were removed. Only `shop` was rebuilt/restarted for this correction; `world` remained running. The subsequent manual purchase succeeded. Product-card thumbnail remains a presentation limitation.

Hector subsequently confirmed successful purchase. The durable receipt records one Jalamartillo, a 1,000-kama debit, resulting balance 1,407 and acknowledged world delivery. Reconnection persistence is covered automatically; a separate manual reconnect result has not been claimed.

## Database-managed categories

Migration `107_shop_categories.sql` is applied to the runtime database and defines `shop_categories`: `id`, `key`, `name`, `description`, `sort_order`, `enabled`. `shop_articles.category` references the category key through a foreign key. Configured departments are Sets, Objetos, Armas, Apariencias, Mascotas, Monturas, Consumibles, Recursos and Merkasaco. The Jalamartillo belongs to Armas. Empty enabled categories are visible, ready for later products; this does not imply those products have been populated.

Validation: seven HTTP checks and the isolated PostgreSQL category test passed, including ordering, filtering, empty categories, disabled categories and purchase rejection. PostgreSQL inventory-full, grant rollback, stale price, concurrent retry, token and insufficient-funds checks also passed in the category snapshot. The complete snapshot suite was interrupted after its time limit; it is not reported as a complete pass. Only the shop service was rebuilt/restarted for categories.

The HTTP service reads enabled categories and articles from the database on each request, filters category catalogs and highlights, and blocks purchase of articles in disabled categories. Category membership, names, ordering and availability do not require a service restart; close and reopen the shop to refresh the native menu.

Operator SQL examples:

```sql
SELECT a.id,a.name,a.item_ref,a.quantity,a.price_kamas,c.name AS category,a.enabled
FROM shop_articles a JOIN shop_categories c ON c.key=a.category
ORDER BY c.sort_order,a.id;

UPDATE shop_articles SET price_kamas=1000,category='weapons'
WHERE key='gobbhammer';

INSERT INTO shop_categories(key,name,sort_order)
VALUES('seasonal','Temporada',100);

UPDATE shop_categories SET sort_order=15 WHERE key='weapons';
```

`shop_articles.quantity` is units delivered per purchase. `enabled` controls availability; there is no finite remaining-stock counter yet. Inventory-full purchases reject before debit, without creating an item or pending gift. Finite stock, bundles and expanded product imports remain separate extensions.

## Manual pilot acceptance

1. Fully close the local client and relaunch from the repository root:

   ```sh
   bash client-tools/local-client.sh
   ```

   A full client relaunch is required to load the updated local Shopi/HAAPI URLs. Select a character and remain outside combat.
2. Leave at least one ordinary inventory slot empty. Note the kama balance `B`. If the account lacks funds, its administrator can run `!kamas 10000` in chat; this adds 10,000 rather than setting a fixed total. Note the resulting balance.
3. Open the native shop button. Find **Jalamartillo** in the home highlights or the **Armas** category. Expected price: **1,000 Ogrines**, with the stated `1 ogrine = 1 kama` equivalence. The shop's starting Ogrine balance should equal the kama balance.
4. Buy one Jalamartillo and confirm. Expected: one item `2027` appears in inventory; kama balance becomes exactly `B - 1,000`; the shop reflects the same shared balance. Allow a few seconds for the world notification.
5. Reconnect and inspect both balances and the item. Expected: the purchase persists, with no second debit or duplicate item.

If the native screen fails, report which step failed and its visible message. No further individual probes are required before this complete basic flow is attempted.

Private evidence: `.runtime/official-dungeon-capture/snapshots/user-complete` and `snapshots/with-backtracking`; capture started on 2026-10-08. Official and local client manifests differ; use the recorded version provenance and verify consumers before applying protocol data. Screenshots and user observations support behavior, not complete wire contracts.

## Acceptance

Prepare one complete manual system test with exact setup commands, actions and expected results after automatic transaction, reconnection and protocol verification. Preserve existing combat and spell behavior.

Dependencies: 10, 22, 23.

## Expanded interface research (2026-10-10)

These linked documents describe research; the deployed pilot and remaining acceptance are recorded above.

- [Opportunities, implementation boundaries and delivery plan](OPPORTUNITIES-20261010.md)
- [Installed-client capabilities and technical evidence](CLIENT-CAPABILITIES-20261010.md)

The installed shop supports a broader storefront than single-item purchases: category navigation, search/pagination, promotional presentation, previews and multi-reference article contents. Currency adaptation, local authentication, recipient selection and atomic world delivery must be verified independently. Do not infer arbitrary currencies, gifting or a general marketplace from bundled SDK methods or the specialized conversion-stone interface.

---

Create a new microservice for the implementation of the shop, use "give direct" and remove kamas, nothing else, for now everythng should cost 1k, but important, we need to configure on database, which items and what price for each one.
