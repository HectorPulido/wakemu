# Guild implementation — offline delivery, 2026-10-10

## Deployment state

Source and migration only. Migration `101_guild_authority.sql` has **not** been applied. No world image was built, no container was started/restarted and no running database was changed. Both `guild_policy.enabled` and `native_sync_enabled` default to false. This is not a declaration that full E15 is playable or ready to enable.

## Implemented code

| Layer | Implementation |
| --- | --- |
| Native protocol | `characters/guild_wire.py`: strict requests, complete required protobuf fields, local format22 and remote format12 actor updates, invitation notice, creation ACK, verified member/rank delta payloads and delta envelope. Shared storage parsing is separate from guild authority. |
| Domain | `characters/guild_service.py`: atomic creation/cost, durable retry receipts, snapshots, rank creation/edit/removal/reordering, permission scope, membership invitation/acceptance/rejection, departure/expulsion, leader transfer, dissolution, description/message and paid identity changes. |
| Persistence | Migration 101: guild/rank/member aggregates, same-guild rank FK, unique membership, deferred unique positions, session-bound invitations, receipts, ordered events, economic state and trusted progression receipts. Logical deletion of a member is blocked until departure/dissolution. |
| Synchronization | `characters/guild_dispatch.py` and `guild_outbox.py`: session-bound routing, full post-commit snapshots, captured recipient leases, failed-publication recovery and guild chat 743. Outbox recovery publishes current authority, not obsolete historical deltas. It runs on guild requests and refresh/reconnect; no new daemon was introduced. |
| Character integration | `guild_character.py`, `storage/store.py`, `wire.py`, `maps/world.py`: snapshot hydration, remote identity, detached world projections and presence timestamps. Generic character loads use one MVCC statement for guild state, avoiding cross-guild locks while loading owned hero rosters. |
| Hero/company integration | COMPANY records carry the selected character's guild; optional hero codec arguments preserve the existing zero-guild default. Hero switching retains its native format22 completion path. Social updates carry no fighter/stat sections. Haven Bag owner identity also uses the projected guild ID. |
| Economy backend | `characters/guild_economy.py`: account-wallet/treasury conservation, trusted idempotent point events, configured weekly caps, bonus purchase/learning and permanent noncombat effects for level, capacity and storage compartment unlocks. |

The server dispatcher handles creation, management snapshot, rank requests, invitations/replies, removal, rank/leader assignment, dissolution, description/message, identity changes, bonus purchase/activation and chat. Native inventory/currency synchronization follows the three identity operations that consume items. All mutation responses are published after commit.

Native parsing evidence is recorded in [NATIVE-LIFECYCLE-20261010.md](NATIVE-LIFECYCLE-20261010.md), [NATIVE-SERVICES-20261010.md](NATIVE-SERVICES-20261010.md) and [NATIVE-SNAPSHOT-ORACLE-20261010.md](NATIVE-SNAPSHOT-ORACLE-20261010.md). The offline Java oracle accepts a nonempty model with ranks/members and both actor carriers. It does not prove live UI installation.

## Explicit remaining work

- **Shared chest inventory:** subsequently implemented in [the guild chest delivery](GUILD-CHEST-IMPLEMENTATION-20261010.md), with migration 106, native routing, metadata-safe custody, treasury and watcher publication. PostgreSQL/live validation remains pending.
- **Haven World (deferred by user):** unlock metadata exists in the extracted catalog; acquisition, ownership, entry, topology and construction are not implemented. No invented transport was added.
- **Combat and temporary bonuses:** no combat/spell effect path was modified. Only explicitly configured permanent noncombat effects can activate. Expiration and member-stat integration remain unavailable.
- **Gameplay earning hooks:** the trusted point API exists, but official per-fight/quest formulas have not been established and no reward callback calls it automatically.
- **Member-specific metadata:** requests 15064/14239 are decoded but not applied. They are not guild rename packets.
- **Native policy gaps:** `ownerId`, final name dictionary/normalization, emblem validity, initial rights and native point-week/counter semantics are not fully established. Deployment requires explicit local policy; a configurable choice is not evidence of official behavior. The chat sender identifier follows the existing account-based channel payload; independent native semantic proof remains pending.
- **Live verification:** login ordering, hero switching with a nonempty guild, visible nameplates, two-client UI behavior and restart durability have not been tested. PostgreSQL integration tests have been prepared but not run.

Names remain globally reserved after dissolution in this schema. Creation receipts return a fresh snapshot only while the original guild remains active and the requester is still a member. Native retry keys are server-generated from session/opcode/body because these requests contain no operation token. This deduplicates identical economic requests within a session; it does not add a protocol field.

## Configuration before any future enablement

Complete and review `guild_policy` before enabling native synchronization: explicit name pattern/normalization (`NFKC_CASEFOLD` is a local option), allowed packed emblems, owner identity interpretation, initial masks, action-to-permission-bit mappings, metadata limits, moderation factor and the three native point fields (`weekly_points_limit`, `earned_points_limit`, `last_earning_point_week`). The codec requires signed 64-bit identities/masks and native byte/UTF-16 bounds. Rank count is 15 by default; member capacity starts at 200 plus configured activated capacity bonuses.

Identity changes require separate enabled policy, `authority='leader'`, a verified consumable item and explicit kamas cost. Economy capabilities, permission bits, source rewards, weekly cap and bonus definitions are independently disabled/configured. The extracted catalog of 78 bonuses is evidence, not an automatically installed reward/effect policy. Test fixtures intentionally use synthetic local policies and do not establish official permissions or name rules.

## Test batteries

Offline execution (no database or running world required):

```sh
PYTHONPATH=server .runtime/e18-venv/bin/python -m unittest \
  server.tests.test_guild_wire \
  server.tests.test_guild_dispatch \
  server.tests.test_guild_projection \
  server.tests.test_guild_economy \
  server.tests.test_guild_dissolution_holdings \
  server.tests.test_guild_outbox \
  server.tests.test_protocol_codec \
  server.tests.test_world_location_batch -v
```

Latest offline verification: **57 tests passed**. No service was started and no migration was applied. The two PostgreSQL modules contain 16 prepared integration cases; these have not been executed.

Use the project's dependency environment if that local interpreter path is unavailable. These tests exercise malformed UTF-8/lengths/trailing bytes, 64-bit identities, required protobuf fields, native snapshots, stale leases, permission boundaries, dispatcher routing, chat recipients/rate/byte limits, publication failure, outbox retry ordering, economic boundaries and preservation of actor combat fields.

The following command is **prepared, not executed**, and creates/applies migrations in isolated test schemas. It requires the guild opt-in flag, an explicit dedicated test database DSN, and project dependencies. Never point it at the running world database:

```sh
WAKFU_RUN_GUILD_POSTGRES_TESTS=1 \
WAKFU_POSTGRES_TEST_URL="$GUILD_ISOLATED_TEST_DSN" \
PYTHONPATH=server:server/tests .runtime/e18-venv/bin/python -m unittest \
  test_guild_service_postgres test_guild_economy_postgres -v
```

Prepared integration cases include creation/retry, wallet/item rollback, stale generation, invitation replay/session replacement, concurrent acceptance for the last place, rank capacity/cross-guild access, identity changes, concurrent treasury withdrawal, balance overflow, trusted-event replay, weekly rollover and bonus learning/activation. The fixture creates minimal test characters directly and avoids runtime native-catalog reads.

Broader catalog-backed tests cannot be asserted offline: `test_world` imports the database-backed protocol catalog. The separate hero-switch dispatcher test also has an existing/concurrent packet expectation mismatch involving its statistics packet. Neither was changed to hide that limitation.

## One future manual acceptance session

Do not execute this session until configuration, isolated PostgreSQL tests and a complete current-checkout build are approved for deployment. There is no manual probe requested now.

1. Use two member test accounts and a third nonmember on the same deployed test world. The founder needs admin/local-console item grant permission. In local chat, run `!item 16942 1` and `!kamas 20000`; verify the item and balance are visible. Use a fresh native-valid name such as `Audit Guild Alpha` and a configured valid emblem. Open the creation interface through the guild creation item and create once. Expect one item and 10,000 kamas consumed, the guild panel populated and the remote emblem/name visible. A repeated native creation request must not cause a second charge.
2. Invite the second player by character name. Reject once; invite again and accept. Expect the native prompt to show founder/guild names, one membership entry per character and correct presence. A third account must have no private roster or chat access.
3. Create/edit/reorder/assign ranks. Expect identical ordering and rights on both clients. Bottom/master rank removal and permission escalation must fail. Give the second player leadership through the master rank and verify the former leader loses that rank atomically.
4. Move members to different maps. Send `Prueba ñ` in guild chat. Expect both members to receive it and the nonmember to receive nothing. Expel the former leader; expect its panel/identity cleared and later guild sends denied.
5. Reinvite, reconnect both accounts and switch an owned hero. Expect membership to remain character-correct, the company identity to match the selected main and the existing fade completion to finish. Verify ordinary movement, combat and spells still behave as before.
6. If identity-change policy is enabled, grant `!item 25101 1` for rename and `!item 25100 1` for emblem changes. Apply a configured-valid value; expect exactly one consumption/cost and consistent local/remote identity. Economic backend tests must already cover conservation and retry behavior; chest/Haven World UI and combat bonuses are still excluded until their adapters are implemented.
7. In a later authorized deployment window, restart only the shared world after a complete build. Expect guild identity, membership, ranks, receipts and economic state to survive; disconnected members must not appear online. This restart has not been performed.
8. Empty treasury holdings through the verified backend and dissolve as leader. Reconnect all characters. Expect no membership, guild chat access or remaining projected identity. Historical receipts and guild identity remain retained for audit.
