# Native mixed physical and transport progression

Source-only policy: `native_mixed_victory_policy`. No runtime activation or restart is performed by this implementation.

A mixed topology retains literal physical gate coordinates and literal native transport bindings. Each encounter stage may contain several disconnected terrain components connected through native transports. `doors` records exact source/destination identities, source approaches, arrivals and stage membership; `physical_doors` records walking boundaries. Ordered stage numbers express explicit local progression, not a claim about official room numbering.

## Authorization and durable transitions

- Intra-stage transport is allowed only for this policy and only for an exact uniquely reviewed native source/destination binding. Source approach cells must be literal native cells assigned to the same stage; arrival coordinates must match the reviewed native destination.
- Both ends must be at or below the committed progression frontier. A transport cannot unlock a future stage.
- Advancing transport between adjacent stages still requires the durable previous-stage victory receipt.
- Backward transports retain the existing adjacent-stage authorization.
- All active party members must have current sessions, belong to the same private instance, and be outside combat. The existing transaction atomically updates every member and inserts durable transition outbox rows. Intra-stage travel changes the instance transition revision but does not settle encounters or advance room progress.
- Physical walking retains the exact directed native exploration edges, diagonal validation, closed-gate collision and frontier validation. An intra-stage transport never creates a walking edge between disconnected terrain.

## Publication and visual state

Hydration combines the existing native teleporter availability packets with physical gate state packets. Locked gates remain closed; committed victory clears gate collision and hides the opened native gate sprite. Intra-stage transports become usable when their stage is unlocked. No combat geometry or spell state is changed.

## Acceptance after complete-image deployment

For Milubo, enter with a group and finish four encounters. Verify that the first physical gate blocks before victory, stage-2 internal transport works without granting a victory, the stage-2-to-3 transport blocks until the second victory, stage-3 internal transports preserve progress, the last physical gate blocks until the third victory, and the boss appears only in stage 4. Finish, use the native exterior exit, and re-enter a fresh run. Also test reconnect after an intra-stage transport and reject all travel while any active member is in combat.

This requires a complete checkout image build before activation; an existing image does not acquire these source changes through database configuration alone.

## Focused automated gate

`test_dungeon_mixed_flow.MixedNativeFlowTests` and `test_dungeon_mixed_flow.MixedNativeTransactionTests`: **6/6 passed in 95.314 seconds**, including two PostgreSQL tests against isolated schemas in `wakemu_migration_test`. The fixture uses a synthetic native binding to test atomic party relocation, durable outbox delivery, unchanged room progress, locked-stage rejection and combat rollback. Four unit tests cover reviewed binding/arrival rejection, physical gate state publication, frontier collision, and absent native walking edges. A separate read-only check hydrated the real Milubo V6 candidate at all four frontiers: 12 packets per stage, gate 32205 opens at stage 2 and gate 32212 opens at stage 4. Full actual-candidate lifecycle validation remains a separate gate owned by the independent validation agent.

```sh
PYTHONPATH=server:server/tests \
WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' \
WAKFU_POSTGRES_TEST_URL='host=127.0.0.1 port=15432 dbname=wakemu_migration_test user=wakemu' \
WAKFU_DATABASE_PASSWORD_FILE=.runtime/local/secrets/postgres-password \
.runtime/local/verification-venv/bin/python -m unittest \
  test_dungeon_mixed_flow.MixedNativeFlowTests \
  test_dungeon_mixed_flow.MixedNativeTransactionTests
```

## Explicit optional native branch exclusions

Mixed candidates may declare `disabled_native_sources` records containing exactly `source_id`, a nonempty English `reason`, and `source_sha256` (the canonical hash of the complete literal native source record). These declarations are specific local policy, never claims about official unavailability. Examples requiring explicit separate review include an item-gated secret annex, a foreign exterior destination outside the reviewed return route, and a shortcut that bypasses encounter gates.

Validation rejects unknown/foreign sources, stale hashes, duplicate records, missing reasons, other topology policies, or overlap with any reviewed transport binding, physical gate, or exterior exit. Every source used by a mandatory advance, boss approach, or main exit must remain bound in the reviewed topology; the hybrid reachability and frontier-closure proof remains required independently. The server publishes excluded sources hidden/unusable and rejects forged interaction requests before either internal party travel or exterior departure. A database configuration cannot silently enable this behavior on an old image.

Three additional focused regressions passed: exact optional-source hiding/rejection; mandatory-path overlap, stale-hash, duplicate and empty-reason rejection; and policy/map ownership rejection. Together with the original mixed units this gate passed **7/7**.
