# Haven Ranch possession and administrator entitlement audit

Status: server entitlement and trusted administrator permission correction implemented and source-qualified; not deployed. Luna independently passed26 affected Ranch cases (22 pure/actual-dispatcher and4 isolated PostgreSQL methods) and5 separate administrator-rights cases. The original80-case portal baseline is historical; these overlapping extension counts must not be added into a claimed complete total. No client change or runtime database/service operation was performed.

## Exact native authority

Biome1's original visibility and access predicate is `GetItemQuantity(32864) >= 1 or HasAdminDataAccessRight()`.

`HasAdminDataAccessRight()` is parsed as original `eLY`. Its `a` method requires an `eDw`, obtains `eDv`, and calls `eDv.a(eDF.oTc)`. The original enum reports **ACCESS_ADMIN_DATA, ordinal115**, which reads permission word3, mask`1 << 19`. This is **different from ADMIN_CHAT, ordinal110**, word3 mask`1 << 14`.

The earlier server `admin_chat_rights.project_account_information` projected only ordinal110. That source gap is now corrected: it projects both ordinal110 and115 only from strict boolean trusted `accounts.is_admin`, clears both for ordinary accounts, and preserves unrelated permission words/bits and native trailing fields. Luna independently reviewed the correction and all5 focused tests passed; evidence is `.runtime/local/verification-ranch-entitlement-20261011/admin-rights.log`. The correction is source-qualified, not deployed; Ranch admission still requires separate fresh server authority. The fresh `Store.character` result has `account_is_admin` from the actual joined account row, and the existing ACCOUNT_INFORMATION wire call now passes it to the corrected projection. A captured permission115 must not be used as server entitlement authority.

Original `eKE` implements `GetItemQuantity` by summing the selected actor's bag containers (`fnq/fnp/Rj`), character quest inventory (`fnZ`), equipment inventory (`fpj/fpd`) and, where applicable, explicit character inventory (`fne/fmz`). It then adds the selected actor's account quest quantities via `flX.aj(account_id, reference)`. Each requested reference is narrowed to int32 and accumulated with native int32 semantics. It does not count another hero's inventory, Haven Bag chests, another account's items or arbitrary visible world objects.

For the server's supported inventory model, `Store.character` loads the selected character's `inventory_items` from owned rows and the supported account-quest projection through `exploration_secrets`. That account projection currently owns only11 explicit exploration refs;32864 is absent. The existing `owned_item_quantity` and `exploration_secrets.account_quantity` helpers already implement the relevant supported quantity semantics and reject malformed snapshots. Possessing this item is a predicate; the original criterion does **not consume it**.

## Corrected dispatcher freshness authority

Both opcode12870 portal admission and12380 biome changes now require a mandatory `validate_entitlement` callback in addition to their existing lease/source/session checks. The actual dispatcher calls `require_owned_entitlement`, which obtains the selected `_lease`, checks durable combat exclusion, loads `Store.character` in the same transaction and evaluates the fresh trusted administrator role or actual owned quantity32864. It rejects a stale in-memory item or administrator flag after independent removal/revocation. Missing entitlement callbacks do not receive a no-op fallback. No new private scene is published until admission succeeds.

`Store.character(account_id, character_id, db)` is the appropriate fresh authority: the account join gives actual `is_admin`, and owned item loading gives current selected-character quantities. Its saved XYZ is deliberately the exterior during private scenes; an entitlement check must not overwrite private Ranch coordinates or compare them against that exterior position.

## Implemented correction

1. Both12870 entry and12380 biome switching require current owned possession or the trusted account administrator role. Missing/malformed authority, foreign ownership, changed selected actors and expired leases reject.
2. Original bag-owner restrictions, source/action, native terrain and occupation checks remain. Entitlement does not grant a guest Ranch ownership or enable the five developer placeholders.
3. Return13982 and ordinary exit remain possible after entitlement loss. The actor can leave safely without periodic inventory mutation or invented consumption.
4. Native ACCESS_ADMIN_DATA115 and ADMIN_CHAT110 are independently understood rights, now both projected only from trusted `accounts.is_admin`; ordinary accounts have both cleared. The existing wire hook uses the actual SQL-joined role. Server admission never trusts captured/client permission bytes.

No global inventory grants, fake client privileges or ordinary guest Ranch entitlement were introduced. The private live XYZ is retained independently of the persisted exterior during the fresh ownership check.

## Complete-system manual preparation and regression scope

For the existing authorized development console, outside combat with one free ordinary inventory slot, use `/l !item 32864 1`. `test_console.execute` already accepts the native reference/quantity form and grants through the owned inventory transaction; the dispatcher refreshes the current private session's item snapshot and sends the normal insertion packet. Expected item: native Bioma Esmeralda32864. The original menu gate should then permit “entrar en el merkalugar”. This is a real item grant for acceptance, not a criterion override.

After coordinated deployment, follow the complete Ranch acceptance journey with this preparation. Verify possession is retained after entry/return, no consumption or kamas charge occurs, ordinary nonowners remain denied, and placeholder choices still reject. A freshly logged-in trusted administrator should have the native administrator-data permission without a biome item; ordinary accounts should require the real item. Actual rendered menu behavior remains a manual acceptance requirement.

## Evidence

Primary original definition: [HAVEN-RANCH-NATIVE-SOURCE-INVENTORY-20261011.json](HAVEN-RANCH-NATIVE-SOURCE-INVENTORY-20261011.json). Existing route/authority scope: [HAVEN-RANCH-PORTAL-20261011.md](HAVEN-RANCH-PORTAL-20261011.md).

Private bounded original Java/bytecode receipts are in `.runtime/local/ranch-biome-source-20261011/`: `eLY.javap`, `eDv.javap`, `InspectRanchAdminRight.java` and the original criterion-class parser probe. The numeric inventory producer is also preserved in `.runtime/local/native-date-item-criteria.txt` (`eKE`). The original enum probe ran with `-Xmx128m`; no terrain or GUI operation was used.

Qualification: Luna terminal session34359 exited0;26/26 Ranch cases passed in7.714s against fresh isolated migrations1–143, followed serially by5/5 administrator-rights cases. Evidence `.runtime/local/verification-ranch-entitlement-20261011/evidence.json` pins helper/test hashes and the actual dispatcher helper/call-site ASTs. The gate verifies real selected ownership, actual SQL inventory/role changes, stale snapshot rejection, both admission branches and return after loss. It does not prove deployed image identity or graphical acceptance.
