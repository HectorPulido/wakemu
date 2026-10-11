# Guild shared chest implementation — 2026-10-10

The basic guild chest now has durable custody, native request routing and native snapshots. This work reuses the existing account chest planner and metadata persistence engine. It does not change Haven Worlds, combat bonuses or automatic rewards. Migration **106** is prepared, not applied; all guild/chest enable flags remain off. No server, database migration, container or game client was launched.

## Implemented behavior

- Shared compartments belong to a guild, independently of the character/account that deposits an item. Native compartment IDs are **0–3**, with **40 slots** each.
- Deposit, partial/full withdrawal, compatible stack merging, in-compartment reordering and cross-compartment swaps preserve quantities and supported item metadata. Empty destinations and automatic inventory placement use the existing account chest planner.
- Custody preserves item UID on a full move; partial stacks receive an authoritative new UID. Elements, shards, mount/pet state, bindings and recycling state are snapshotted/restored through the existing metadata whitelist. No arbitrary SQL table/column comes from a packet.
- Bound, nonexchangeable, unknown-rule and equipped-in-any-build items cannot be deposited. Unknown stack/binding rules fail before committing.
- Each transaction locks the selected session/character, then the guild, then its compartments. It rechecks current membership, the original opened guild, unlock state and current rank permissions. No leader permission bypass exists.
- Durable operation receipts suppress repeated commits. Expected compartment revisions reject stale actions; replays return current snapshots without applying again. Native requests have no operation token, so the server retains an identical request's original translation/revision for a three-second retry window within an opening. A later identical action receives a new server operation key.
- Guild dissolution fails while any compartment holds items. Leaving or expulsion does not transfer guild property to the departing member.
- Native money requests use the existing treasury record. Chest rights and separately configured treasury rights are checked together with wallet conservation, overflow checks and a durable receipt. Treasury remains independently opt-in.

`haven_chest.persist_inventory` extracts the original account chest persistence block without changing its behavior. Guild custody reloads only inventory/build equipment/wallet fields, preserving live combat and spell state. Container ordering keeps the fixed base bag first.

## Native interface and physical authority

The installed client's **GuildStorageBox** (`bBX`) starts browsing with interaction **12870**, action **12**; action **13** ends browsing. The client starts its guild occupation locally. AccountChest interactions cannot open guild storage.

Every action checks the configured installed object, current public map/instance, distance, elevation and activity. Movement, hero changes, combat, spectator/haven-bag activity and disconnect cleanup invalidate the connection context. Private instances are excluded, so Haven World contexts are untouched.

Shared storage requests **12844, 12004, 14616, 12531** are routed only with this private authorized context. An opcode alone grants no access. Reads return fresh snapshots; this does not assert undocumented official subscription semantics for 12844/12004.

A corrected native field interpretation is important: deposits/withdrawals contain **UID i64, reference i32, quantity i16**. Withdrawal additionally carries the destination inventory container UID and destination slot. Its source slot is resolved by authoritative chest UID, never taken from a client-owned inventory position. Server-only operation 5 is rejected.

Responses **14424** (enabled compartments/treasury), **14787** (contents) and **15817** (treasury) were accepted and reserialized by the installed native parsers in an offline headless Java oracle. The required history protobuf is empty; durable receipts/events exist on the server, but native history UI is not implemented. Contents are published one compartment per packet. Oversized or unencodable contents are rejected before custody commits.

Connected viewers of the same guild receive fresh views after storage mutations and guild/rank changes. Different guilds never receive those contents. Locked or unauthorized compartments have disabled empty snapshots; losing all viewing rights also hides treasury money. Captured session generations prevent delivery to replacement sessions. A per-guild publication lock serializes updates and close/clear operations. Socket/DB publication failures do not undo custody; reopening reads the committed state.

## Configuration for a future deployment

Migration [106_guild_chests.sql](../../../server/migrations/106_guild_chests.sql) adds `guild_chests`, `guild_chest_receipts` and a disabled `guild_policy.chest` section. Apply it only in a later authorized deployment window, together with the full current checkout and preceding migrations.

Before enabling, configure `guild_policy.chest`:

```json
{
  "enabled": false,
  "compartments": {
    "0": {
      "name": "Guild chest 1",
      "capacity": 40,
      "requires_unlock": false,
      "permission_bits": {"view": 11, "deposit": 11, "withdraw": 5, "move": 11}
    }
  },
  "access_points": [
    {"map_id": 527, "object_id": 27021, "action_id": 12, "parameter": 0,
     "compartment_ids": [0], "max_distance": 3, "max_z_distance": 2}
  ]
}
```

This is an explicit local access policy example, not an applied setting or a claim about all official chest rules. The installed enum verifies `REMOVE_CHEST_ITEM` bit 5, `REMOVE_CHEST_MONEY` bit 8 and `MANAGE_GUILD_CHEST_1..4` bits 11–14. Mutations also require `view`; moving between compartments conservatively requires view/move/deposit/withdraw rights on both.

Configure additional compartments with IDs 1–3, capacity 40 and explicit unlock/permission rules. Locked compartments can remain in the native view without revealing their contents. No bonus is activated by this work. A capacity change requires a deliberate migration; changing JSON cannot silently resize stored custody.

The access example uses the installed map catalog's bank object 27021 on map 527 at **(92, -45, 8)**. Validate that object and its browse parameter against the current published catalog before enablement. The same validator supports every configured installed public GuildStorageBox; it has no map-specific gameplay branch. This work does not publish missing map geometry or teleport destinations.

Treasury needs `guild_policy.economy.treasury_enabled` and explicit `treasury_deposit`/`treasury_withdraw` permission bits in addition to chest rights. Guild/native synchronization policy remains separately required. None is enabled by this change.

## Verification and prepared battery

The offline regression battery includes guild domain/protocol routing, chest planning, native codecs, physical access, watcher publication, retries, close/publication concurrency, oversized snapshots and the original account chest planner. PostgreSQL cases are prepared but **not executed**. They cover shared members, persistence, metadata, rollback, revoked rights, full inventories, last-stack races, duplicate operations, expected-guild fencing, treasury conservation, hidden compartments and dissolution protection.

Run the offline battery from the repository root:

```sh
PYTHONPATH=server .runtime/e18-venv/bin/python -m unittest \
  server.tests.test_haven_chest \
  server.tests.test_guild_chest server.tests.test_guild_chest_access \
  server.tests.test_guild_chest_wire server.tests.test_guild_chest_dispatch \
  server.tests.test_guild_chest_limits \
  server.tests.test_guild_wire server.tests.test_guild_dispatch \
  server.tests.test_guild_projection server.tests.test_guild_economy \
  server.tests.test_guild_dissolution_holdings server.tests.test_guild_outbox \
  server.tests.test_protocol_codec -v
```

Latest focused offline result: **104 tests passed**. Python parsing passed for 26 relevant source/test files, and scoped `git diff --check` passed. There are **31 prepared PostgreSQL cases** across guild lifecycle, economy and chest modules; none was executed.

Broader verification is not green. A separate World location-batch check ran six tests: one fails because a failure-path fixture passes a string peer and cleanup calls `peer.shutdown(2)`, raising `AttributeError`. This is outside the chest files; neither that test nor the concurrent World implementation was changed to mask it. A full discovery attempted by the test agent reported 3,233 tests, 421 skips, 1,275 errors and five failures. Most errors require the unavailable live native catalog (`WAKFU_DATABASE_URL`); reported failures involved placement deadlines, social and territory weather. No baseline comparison establishes their origin. The focused passing result must not be read as a passing complete-server suite.

Future isolated PostgreSQL battery, **do not run against the world database**:

```sh
WAKFU_RUN_GUILD_POSTGRES_TESTS=1 \
WAKFU_POSTGRES_TEST_URL="$GUILD_ISOLATED_TEST_DSN" \
PYTHONPATH=server:server/tests .runtime/e18-venv/bin/python -m unittest \
  test_guild_service_postgres test_guild_economy_postgres test_guild_chest_postgres -v
```

The fixture creates an isolated schema and applies migrations there; this command has not been executed. Synthetic stack/exchange rules are isolated from the runtime catalog. Offline mocks and Java parsing do not establish PostgreSQL atomicity or live UI behavior.

## One future manual acceptance session

The expanded handoff guide is [MANUAL-ACCEPTANCE-20261010.md](MANUAL-ACCEPTANCE-20261010.md); remaining implementation and readiness work is tracked in [PENDING-20261010.md](PENDING-20261010.md).

No manual probe is requested now. Run this complete session only after configuration, isolated PostgreSQL validation and an authorized complete-checkout deployment:

1. Use founders/member A and B of one test guild and a member C of another guild. Give A the configured chest rights; give B deposit/view rights initially and later withdrawal rights. On A's authorized local console, run `!item 2504 9`. Verify nine units appear in a free inventory position; leave the item unequipped.
2. Bring A and B to the same configured public guild bank. For the example above, use map 527, bank object 27021 near (92, -45, 8), through normal travel. Do not invent a teleport tile: the server requires published traversable geometry. Open the bank on both clients. Expect identical enabled compartments, empty initial cells and the same treasury balance.
3. Deposit four units into an empty chest cell. Expect five in A's inventory, four in that cell and B's open view to update without reopening. Repeat native delivery of the same request within the retry window using the protocol test harness: expect no second transfer. After the retry window, a deliberate new deposit should work normally.
4. As B without withdrawal rights, attempt withdrawal. Expect denial and unchanged inventories/chest. Grant the configured withdrawal bit through guild rank management, reopen, and withdraw two units. Expect two left in the chest and two in B's inventory, with the total remaining nine.
5. Move the stored pile within a compartment; if a second compartment is explicitly available, move/swap across compartments. Expect both views to agree, quantities unchanged and no duplicate UID. In a separate item fixture with shard/element/pet state, compare all visible properties before deposit and after B withdraws it.
6. Have A and B try to withdraw the last pile simultaneously. Expect one successful owner and one stale/source-unavailable rejection; no duplicate or missing item. Fill B's inventory and retry a withdrawal: expect denial with unchanged custody.
7. Open C's guild bank. Expect C's own guild storage only. Expel B while B's guild chest is open: expect its view cleared and further requests denied. Moving away, entering combat or switching hero must invalidate that opening; return and reopen before another action.
8. If treasury is separately enabled, grant A `!kamas 1000`, record the initial wallet+treasury sum, deposit 100 and withdraw 40. Expect conservation, live updates for both viewers, denied unauthorized withdrawal, and no second debit for an identical immediate retry.
9. Disconnect/reconnect both members and reopen. Expect all committed custody and treasury balances restored. Dissolution while items/money remain must fail. Withdraw/settle all holdings, then dissolve: expect no remaining membership or storage access. Test restart durability only in a later explicitly authorized restart window; no restart occurred here.
