# 42. Custom shop paid with kamas

**Status: ⏳ Pendiente.** User-requested original issue; no implementation or acceptance claimed.

## Scope and evidence

Implement a custom server shop using kamas, never real-money payments. The user opened the official shop to provide a UI/protocol reference only; its commercial catalog and payment system are not the requested implementation. Configure products, quantities, availability and kama prices in the database. Purchase must debit kamas and grant items atomically, preserve overflow handling, reject insufficient funds and prevent duplicate purchases on retries.

Private evidence: `.runtime/official-dungeon-capture/snapshots/user-complete` and `snapshots/with-backtracking`; capture started on 2026-10-08. Official and local client manifests differ; use the recorded version provenance and verify consumers before applying protocol data. Screenshots and user observations support behavior, not complete wire contracts.

## Acceptance

Prepare one complete manual system test with exact setup commands, actions and expected results after automatic transaction, reconnection and protocol verification. Preserve existing combat and spell behavior.

Dependencies: 10, 22, 23.

---

Create a new microservice for the implementation of the shop, use "give direct" and remove kamas, nothing else, for now everythng should cost 1k, but important, we need to configure on database, which items and what price for each one.
