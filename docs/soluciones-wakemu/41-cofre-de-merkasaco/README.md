# 41. Haven Bag account chest

**Status: manually accepted by Hector on 2026-10-09.** Hector reports: “Cofre funciona perfecto.” Deployment was performed separately; this agent did not restart services. The automated verification below remains the recorded source evidence.

## Verified identity and protocol

The installed map-9 catalog identifies object 13261 as `AccountChest`, at (0, -4, 0). The official `chest-haven-world` capture opens that exact object using action 12, parameter 0. Its login bootstrap contains account-owned compartment protobufs; this is an account chest, not a character chest or an unverified loot container.

Current-client contracts were checked in `cqe`, `cqi`, `cxt`, `ciH`, `bmK`, `bmM`, and protobuf descriptors `lY`, `lj`, `lm`:

| Direction | Opcode | Verified purpose |
|---|---|---|
| Out | 12870 | Interactive target + action 12 + parameter 0 |
| In | 12401 / 12344 / 12088 | Occupation 7, chest interactive state, occupation type 31 |
| Out | 12038 | Deposit groups: compartment string + item UID, position, quantity |
| Out | 12551 | Withdrawal: actor, compartment, item reference, position, quantity, destination bag and position |
| In | 318 | Complete owned compartment list; existing slot arrays and UID index are replaced and the open UI refreshed |
| In | 13929 / 13716 / 12852 | Official incremental content changes and inventory acknowledgements |

The implementation uses the verified complete 318 snapshot, authoritative BAGS, and the rich inventory registry after transfers. It does not fabricate an incomplete rich-item incremental acknowledgement. Hector confirmed that the chest works correctly in the installed client on 2026-10-09.

Private evidence: `.runtime/official-dungeon-capture/snapshots/chest-haven-world/decoded/frames.jsonl`; native offline inspection files `.runtime/chest-*.javap`. No captured account identity, compartment ID, or contents are seeded into the implementation.

## Implementation

- `haven_chest.py`: lease-checked, account-owned storage; complete-batch planning before any ownership mutation; transactional inventory custody and receipts.
- `haven_chest_wire.py`: strict native decoders and complete current-client protobuf serialization.
- Migration `088_account_haven_chest.sql`: one account-owned compartment, JSON-backed durable complete items, revision and transaction receipts. The local DEV policy grants **one 100-slot compartment**. The capture shows 100-slot compartments; this policy does not claim to reproduce commercial default unlocks or all four captured tabs.
- All account characters use the same chest. Visitors and other accounts cannot open it. The dispatcher validates installed object identity, owner bag, proximity, native action, combat state and active opening token. Movement, leaving the bag or combat invalidates access.
- Deposits and withdrawals handle whole/partial stacks, compatible merges, occupied positions, full inventories, stale/foreign sources, and equipped objects in **any** build. Failed batches roll back completely.
- Item metadata preserved: elemental selections, exact shard state (including unknown protobuf fields), pet/mount state, binding state and recycling state. Split identities use the existing global inventory UID allocator; full transfers retain their UID. Character-bound items are rejected from account storage.
- Identical native requests carry no nonce. A private opening token, committed revision and **three-second retry window** suppress immediate duplicate submissions. After the window, an identical request is a fresh intentional transfer; quantity conservation remains transactional. Two deliberate identical clicks inside that window may produce only one transfer. This is an explicit protocol limitation.

No chest upgrades, additional compartment purchase, tab reordering/customization or cross-character bound-item conversion are implemented.

## Automated verification

`test_haven_chest.py` covers native captured requests, malformed framing, batch conservation and rollback, rich metadata, partial split UIDs, compatible/incompatible merges, full destinations, account sharing, and opening guards. `test_haven_chest_store.py` exercises real transactions in isolated PostgreSQL schemas: reconnect, account sharing, shards/elements, pet metadata, injected transaction failure, bounded duplicate requests, foreign destinations and equipment in other builds.

The final chest gate passed **24 tests, zero skips or failures** (17 unit/wire and seven PostgreSQL tests), including the complete bootstrap serialization test. The installed native `cxt/lY/lj` decoder also accepted a generated 100-slot bootstrap containing a rich shard item at slot 54. The combined dungeon/corpse/chest gate passed 54 tests. Tests require the repository test environment and an explicit non-runtime PostgreSQL test database:

```sh
PYTHONPATH=server:server/tests python3 -m unittest test_haven_chest test_haven_chest_store
java --class-path 'client/lib/wakfu-client.jar:client/lib/protobuf-java-3.21.6.jar:client/lib/log4j-1.2.17.jar' sniffer/java/VerifyAccountChestBootstrap.java .runtime/local/account-chest-bootstrap.hex
```

## Complete manual acceptance after deployment

Combined system acceptance: [corpses and chest](../../reports/CORPSES-CHEST-ACCEPTANCE-20261009.md).

Use two characters A and B from the same account, plus visitor C from another account. Do not equip a dragoturkey while verifying item characteristics, because issue 39 has an independent open refresh defect.

1. On A, prepare space in the inventory and execute `!item 2504 9` and `!item 2869 1`. Identify the equipment if required; record its elements/engastes before storing it.
2. Enter A's Haven Bag, approach the account chest at (0, -4), and open it. Expected: one available 100-slot tab and no other account's contents.
3. Deposit **four** of the nine items 2504. Expected immediately: five in inventory, four in chest. Do not repeat identical partial clicks within three seconds.
4. Withdraw **two**. Expected immediately: seven in inventory, two in chest, with no additional stack or duplicate object. Close and reopen the chest: quantities remain unchanged.
5. Deposit equipment 2869, close the chest, leave and reconnect. Expected: equipment remains in the chest with the same elements/engastes and no duplicate in inventory.
6. Switch to B on the same account, enter B's bag and withdraw the equipment and remaining two resources. Expected: exactly one equipment object retaining its metadata, and exactly nine resources across A/B/the chest in total.
7. Have C enter as a visitor and attempt to open the chest. Expected: no account contents or transfers become available. C's own bag has a separate chest.
8. With a plain resource in the chest, fill the destination inventory with other items so no compatible stack has space, then attempt withdrawal. Expected: unchanged chest quantity and no dropped/lost item. Free a cell and retry after three seconds: withdrawal succeeds once.
9. Equip the equipment in a build and attempt to deposit it. Expected: rejected without moving/deleting it. Remove it from every build and retry: succeeds.
10. Reconnect once more with A and B. Expected: the same shared final contents, conserved quantities, and no reappearance of withdrawn items.

Report the first failing step and whether the inventory/chest corrects itself on closing/reopening or reconnecting. The native UI reconciliation remains unaccepted until this complete test passes.
