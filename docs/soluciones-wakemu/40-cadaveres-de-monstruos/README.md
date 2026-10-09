# 40. Monster corpses after combat

**Status: ⏳ Pendiente.** User-requested original issue; no implementation or acceptance claimed.

## Scope and evidence

Preserve defeated monsters visibly on the exploration map after combat. The user observed three defeated Gobballs remaining in the first official dungeon room and explicitly confirmed this also applies to monsters outside dungeons. Room changes must not be treated as corpse destruction. Actor removal packets prove client visibility removal only, not persisted lifecycle termination. Re-entry visibility and lifecycle require verification. Establish native actor death/persistence state, lifetime and cleanup on map reload or encounter reset from captured packets; do not infer a duration. Preserve combat settlement and prevent corpse harvesting or interaction from duplicating rewards.

Private evidence: `.runtime/official-dungeon-capture/snapshots/user-complete` and `snapshots/with-backtracking`; capture started on 2026-10-08. Official and local client manifests differ; use the recorded version provenance and verify consumers before applying protocol data. Screenshots and user observations support behavior, not complete wire contracts.

## Acceptance

Prepare one complete manual system test with exact setup commands, actions and expected results after automatic transaction, reconnection and protocol verification. Preserve existing combat and spell behavior.

Dependencies: 29, 14, 16.


---

This is not only for dungeons, the corpses are available on the overworld too
