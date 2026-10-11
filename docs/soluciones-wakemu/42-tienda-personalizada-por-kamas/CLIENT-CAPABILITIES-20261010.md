# Native shop client capabilities — 2026-10-10

## Scope and provenance

Read-only inspection of the installed local client, using `unzip`, Python ZIP inspection and `javap -p -c` / `javap -v`. No client, server, database or service configuration was changed. These are static contracts, not a successful local purchase or acceptance result. The official capture and this local client can differ in version; do not transfer obfuscated class names between builds without checking.

Artifacts:

- `client/lib/wakfu-client.jar`, SHA-256 `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`.
- `client/lib/shopi-client-v1-1b533e3e.jar`, SHA-256 `960dc197e67bb014b4a657d9c168048dbec12a4e65254049dd29ccfe0af6505f`.
- `client/config.properties:303–317`: separate Ankama HAAPI, Wakfu HAAPI, Shopi, external payment handling and services URLs. `shopiUrl` is at line 305. The external payment URL is at line 309. This is evidence of a configurable HTTP shop backend; it does not prove that changing one URL implements the complete shop.

Class names below are exact names in the inspected JAR. Binary artifacts have no meaningful source line numbers; method names and DTO fields are the reproducible references.

## Confirmed native UI entry points

`javap -p -classpath client/lib/wakfu-client.jar cNu` exposes:

| Feature | Concrete entry points | Opportunity / limitation |
|---|---|---|
| Category navigation | `selectCategory`, `home`, `goToHighlightCategory` | Hierarchical catalogs and thematic departments. |
| Pagination | `first`, `previous`, `next`, `last` | Large catalogs without one enormous product list. |
| Search | `search`, `search2`, `search3`, `search4`, `resetSearch` | Searchable item catalogs; exact ranking belongs to backend. |
| Featured content | `discoverHighLight`, `selectCarrouselHighlight`, `openLink`, `scrollInHomeArticleList` | Home campaigns, articles, category shortcuts and links. |
| Product detail | `openArticleDescription`, `openArticleDescriptionFromBanner`, `openItemDescription` | Explain packs, contents and conditions. |
| Appearance preview | `openStuffPreviewWindow`, `getPetItemReference` | Native preview route exists for supported content; test item types before promising universal preview. |
| Purchase shortcuts | `quickBuy`, `oneClickFromArticle`, `oneClickFromContainer` | Quick acquisition workflows backed by proper transactions. |
| Conversion-stone section | `goToConversionStone`, `goToConversionStoneTab`, `conversionStoneSell`, `conversionStoneBuy`, refresh/cancel/change methods | A separate exchange-like UI is present; not a generic auction house contract. |

These names demonstrate client entry points, not that every button is visible or enabled in the current server session.

## Confirmed HTTP consumers

`cca.lPg` is initialized to `ShopKey.WAKFU_INGAME`. Client classes `bSo`, `bSp`, `bSx`, `bSE`, `bSy`, `bTe` and `bTG` reference Shopi API methods. Examples confirmed in bytecode:

- `bSo`: `CategoryApi.listCategoriesAsync`, with `WAKFU_INGAME`.
- `bSp`: `CatalogApi.getCatalogPageAsync`, request `categoryId`, `limit`, `page`.
- `bSx`: `PromoteApi.getHomePagePromoteGroupAsync`.
- `bSE`: `ArticleApi.searchArticlesAsync`, request `text`, `limit`.
- `bSy` and `bTG`: `ArticleApi.getArticleByKeyAsync`.
- `bTe`: cart creation/processing using `CartApi`, `Cart` and payment request objects.

SDK paths below were extracted from generated API method bytecode. Prefix every path with `/{language}/shops/{shop_key}`:

| HTTP | Path | Contract |
|---|---|---|
| GET | `/categories` | Categories, pagination, parent category argument. |
| GET | `/categories/{category_id}` | One category. |
| GET | `/categories/{category_id}/breadcrumb` | Category navigation trail. |
| POST | `/catalog-pages:get` | Category, page and limit request. |
| GET | `/articles` | Article listing. |
| GET | `/articles/{article_id}` | One article. |
| GET | `/articles/{article_id}/breadcrumb` | Article navigation trail. |
| POST | `/articles:get-by-key` | Stable article key lookup. |
| POST | `/articles:search` | Search request. |
| GET | `/promoteGroup` | Home promotional sections. |
| GET | `/categories/{category_id}/promoteGroup` | Category promotional sections. |
| POST | `/carts` | Create cart. |
| GET / PUT / DELETE | `/carts/{cart_id}` | Retrieve, update or remove cart. |
| POST | `/carts/{cart_id}/orders` | Create order. |
| GET | `/carts/{cart_id}/payment-modes` | Available payment modes. |
| POST | `/carts/{cart_id}:list-payment-modes` | Payment-mode request variant. |
| POST | `/carts/{cart_id}:estimated-totals` | Estimated totals. |
| POST | `/carts/{cart_id}:add-code` / `:remove-code` | SDK code support; native code-entry UI was not established. |

Not all SDK paths are necessarily requested by the native UI. Implement the actually observed consumer contract first.

## Fields consumed by the Wakfu UI adapter

`cca.a(Article)` reads media, `singleReferences`, promotions, payment modes, id, key, name, description, subtitle, `countdownTo` and metadata. It builds a `bSV` article model. `cca` also converts categories and promotional targets into native display models.

Practical consequences:

- Fixed packs are supported structurally: an article has multiple `SingleReference` entries, each with quantity and reference; game-action definitions also contain multiple actions. The displayed contents still need a matching atomic server fulfillment implementation.
- `GameActionReference` is converted by examining its `GameActionDefinition.actions`. The inspected branch handles `WakfuItemAction.itemId`, parsing it as an integer; unknown action types are logged as unhandled. Do not assume arbitrary script actions automatically render as meaningful products.
- Account-status, virtual-subscription and server references have adapter branches. These are useful evidence for service-style product presentation, but do not supply Wakemu implementations of those services.
- `Price.amount`, `originalAmount` and `currency` are consumed. Original prices and promotional descriptions can be represented.
- `countdownTo` is consumed, so time-limited presentation has a native data route. Actual expiry must be validated by the server.
- `Category` fields include id, key, name, description, parent category id and image URI. Hierarchical themed catalogs are viable.
- Promotional carousel targets include article/category conversion branches; image media is converted from URI. `MediaYoutubeVideo` is converted to a YouTube thumbnail URL. This proves thumbnail handling, not embedded video playback.

### Existing client visibility requirements

`cca.b(Article)` recognizes string metadata key `in_game_requirements`, parses its value through `bSI.h`, and rejects invalid products. `javap -v bSJ` confirms JSON fields `hide`, `containsCompanion`, `hideOnNeo`, `neoOnly`. The validator evaluates feature flags. The category key `companions` also has an availability gate in `bSI.a(bSM)`.

These are presentation filters, not authorization controls. Server-side eligibility must remain authoritative. The inspected parser returns true after a JSON mapping exception, so malformed requirement metadata is not a safe way to enforce purchase restrictions.

## Payment and currency boundary

The broad SDK `Price.currency` string is not proof of arbitrary native currency support. `cca.a(Article)` explicitly branches on virtual payment mode IDs `OG` and `SW`; it also handles free and nonvirtual payment representations. `cca` builds a `FREE` payment request for a free cart mode. Supporting kamas, tokens, event currency or reputation therefore needs an adapter decision and verification of labels, balance, confirmation and debit behavior. Merely returning `currency: "KAMAS"` is unverified.

A free native presentation may be a useful route for free claims, but it is not authorization to bypass backend prices or debit checks. The existing issue still requires configurable kama prices and atomic fulfillment.

## Conversion-stone UI uses another backend

`bTG` references Wakfu HAAPI `OgrineTokenApi.listRequest`, `listBidsRequest`, `getRateRequest`, `sellRequest` and `cancelRequest`, using `WakfuClient.cfs()`, separately from the Shopi client `cft()`. It consumes rate data including `Rate.getAvgLast30d`. The UI controller exposes buy, sell, cancel, refresh and change-offer operations.

Opportunity: a purpose-built exchange board using this surface. Cost: reproduce and verify the separate HAAPI contract, token/offer ownership, escrow, matching and settlement. This is not available for free by implementing the ordinary catalog endpoint, nor does it prove support for arbitrary items, auctions or barter.

## SDK capabilities that remain unconfirmed as native UI features

The shared Shopi SDK includes `ChoosableReference`, `ChoiceItem`, `PromotionCode`, offered-article discounts, rename-character and account-transfer request DTOs, shipping/carriers, real-payment integrations and many other games' models. Presence in this cross-game SDK is insufficient to claim a Wakfu button, workflow or server implementation.

- Select-one-of-many bundles: DTO exists, but no `Article.getChoosableReferences` consumer was established in the inspected adapter. Treat as an extension candidate, not a ready native feature.
- Coupons: cart API contract exists; code-entry UI not confirmed.
- Rename/transfer services: SDK contract exists; native UI and Wakemu fulfillment not established.
- Gifting, wishlists, purchase-history display, loyalty points, recurring subscriptions, player listings, custom forms and auction bidding: no verified native consumer was established in this inspection. They can be backend/product opportunities but may need client changes or another interface.
- Stock status, `maxQuantity`, `purchaseAlone`, notices and flags are DTO fields; do not assume the native adapter enforces or displays every one. Enforce quotas and stock on the server.

## Verification still needed before implementation claims

Use the same client build against a local shop adapter; capture actual HTTP requests and native display/confirmation behavior. Cover home, category, pagination, search, one item, fixed pack, preview, free claim, price labels/balance, errors and reconnection. Validate debit/fulfillment atomically and reject replay independently of UI. Keep the separate exchange as its own scope. No paid official purchase or production request is necessary to investigate these local contracts.
