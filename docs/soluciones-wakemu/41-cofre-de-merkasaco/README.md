# 41. Haven Bag chest

**Status: ⏳ Pendiente.** User-requested original issue; no implementation or acceptance claimed.

## Scope and evidence

Implement the personal Haven Bag chest using owned persistent storage. The user opened a chest during the official capture. Its exact identity, capacity, account/character scope, supported items and transfer protocol still require verification; do not assume the observed chest is a Haven Bag chest without checking. Validate deposits, withdrawals, partial stacks, full inventory, reconnect, ownership and replay protection.

Private evidence: `.runtime/official-dungeon-capture/snapshots/user-complete` and `snapshots/with-backtracking`; capture started on 2026-10-08. Official and local client manifests differ; use the recorded version provenance and verify consumers before applying protocol data. Screenshots and user observations support behavior, not complete wire contracts.

## Acceptance

Prepare one complete manual system test with exact setup commands, actions and expected results after automatic transaction, reconnection and protocol verification. Preserve existing combat and spell behavior.

Dependencies: 11, 22, 23, 26.
