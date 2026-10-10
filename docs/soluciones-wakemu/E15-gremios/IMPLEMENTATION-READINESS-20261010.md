# E15 implementation readiness — 2026-10-10

## Assessment

The installed client contracts provide a useful starting point, but the current server has no authoritative guild domain or guild schema. Implementing E15 requires persistence, session-bound operations, native synchronization and service-specific rules. Fixing chat or sending creation notification 1000 alone cannot deliver guilds.

This is an offline source review. No server code, database or running service was changed. Existing native probes remain fixture evidence, not end-to-end acceptance.

## Current integration points

| Area | Current source | Required change |
| --- | --- | --- |
| Transactions | `server/wakfu_server/storage/postgres.py`, `Database.connection` | Reuse the existing transaction boundary for guild state, wallet debit and inventory consumption. |
| Session authority | `server/wakfu_server/storage/store.py`, `lock_character` | Bind every mutation to account, session generation and acting character; handle hero switching explicitly. |
| Persistence | `server/migrations/`, account wallets and inventory tables | Add guild, rank, membership, invitation and bonus tables, policy settings and an operation/event ledger. Allocate the migration number at implementation time because other work is concurrent. |
| Native requests | `server/local_game_server.py` | Add a dedicated guild dispatcher and domain service; do not put guild rules directly into the main dispatch loop. |
| Chat decoding | `server/protocol_codec.py`, `decode_body` | Separate 13744 from text-only requests and decode i64 guild identity before u16 UTF-8 text. |
| Chat delivery | `server/wakfu_server/maps/chat_channels.py`, `Channels` | Add authoritative membership routing and verify the native guild response. Current accepted requests are 13074, 13224, 13188 and 13831. |
| Local model | `server/wakfu_server/wire.py`, `minimal_entity` and `adapt` | Serialize a complete guild model into local state and update enclosing lengths. The current format22 path assumes a fixed 46-byte empty snapshot. |
| Remote identity | `server/wakfu_server/wire.py`, actor serialization | Replace empty guild identity and hydrate remote guild information from the same authoritative snapshot. |
| Character lifecycle | `Store.delete_character`, disconnect/reconnect and hero switch | Define leader deletion, member removal and presence rules; ensure later actor refreshes cannot erase a guild model. |

The earlier statement that the local-state carrier is entirely unknown is outdated: opcode 15548 with format22 is handled by `wire.adapt` and used by the native hero-switch completion path. A nonempty guild payload and initial-login delivery still need native validation. Preserve the existing hero fade-completion behavior.

## Contracts already supported by evidence

- Creation request 13757: i64 blazon and three i32-length UTF-8 strings. UI references creation item 16942 and 10,000 kamas; authoritative debit rules still need implementation.
- Creation notification 1000: signed-byte UTF-8 byte length. This notification does not hydrate membership.
- Local section 31: u16 protobuf length, protobuf and float32 moderation factor. Section 31 is not a network opcode.
- Incremental update 15367: guild identity and typed deltas. A full snapshot must precede deltas.
- Rank requests 15194, 14088, 14815 and 15429; 27 permissions with native hierarchy probes. Position zero still requires the permission bit.
- Remote identity and protobuf fields documented in `MODELO-Y-PERSISTENCIA.md`.

## Evidence still needed before the dependent features can ship

1. **Identity and bootstrap:** establish `ownerId`, date units, all required protobuf defaults, initial-login carrier and nonempty format22 roundtrip. Verify guild loading after hero switching as well as reconnecting.
2. **Creation validation:** finish name normalization, uniqueness and dictionary rules; valid emblem catalogs; native errors and exact creation-item consumption. Never substitute example-based regex rules for the native validator.
3. **Membership lifecycle:** identify invitation, acceptance/rejection, cancellation/expiry, leaving, expulsion, leadership transfer and dissolution requests/responses. Determine which operations affect characters versus accounts and how owned heroes participate.
4. **Rank authority:** establish initial permissions, rank assignment restrictions, leadership invariants and legal rank ordering. Consumer behavior alone does not establish official tie policy.
5. **Chat:** identify native response/error packets and prove membership-based delivery across maps, including concurrent expulsion and stale sessions.
6. **Progression and services:** establish point earning/spending and weekly limits, bonuses and their actual effects, chest storage/withdrawals, treasury and Haven World contracts. Permission labels do not prove service behavior. These remain part of full E15 scope.

Independent persistence and codec work can proceed while missing lifecycle contracts are investigated. Do not invent missing opcodes, permission defaults, bonus effects or official rules.

## Proposed implementation sequence

1. Implement strict native codecs and reusable guild domain/storage modules. Add schema constraints for one permitted membership per identity, same-guild rank references, normalized-name uniqueness and durable invitations.
2. Deliver atomic creation and complete snapshot restoration: validate session and requirements, lock wallet/inventory, create initial ranks/member, debit once, commit, then publish notification and state. The request has no documented client operation ID: define server-side retry semantics rather than assuming an ID is present.
3. Implement the complete membership/rank lifecycle with locked capacity and permission checks. Prevent leaderless guilds, cross-guild rank assignments and races for the last available place.
4. Publish ordered post-commit deltas and chat using current recipient leases. Serialize membership changes with chat authorization so expulsion cannot authorize later sends from stale membership. Reconnect from a fresh snapshot rather than replaying obsolete events.
5. Implement progression, bonuses, chest/treasury and Haven World under the same authority. Keep economic ledgers and transaction boundaries shared with inventory/wallet services. Introduce combat bonus effects only through verified existing stat/effect paths with regression coverage.

An event ledger/outbox is a proposed recovery mechanism, not an existing guild implementation. Persist ordering internally; do not add unsupported revision bytes to native packets. Character deletion is currently logical, so foreign-key cascades cannot clean up membership: explicitly remove ordinary members and apply the verified leadership policy. Wallet balances belong to accounts, not characters. Follow the existing character-before-wallet locking convention in `server/wakfu_server/items/player_exchanges.py` and define compatible guild/inventory lock ordering to avoid deadlocks across deletion, creation and membership operations.

## Verification and complete manual acceptance

Automated coverage must include malformed/trailing/invalid UTF-8 payloads, 64-bit IDs, native snapshot/delta roundtrips, duplicate creation, rollback after partial failure, concurrent name/capacity conflicts, invitation replay, permission escalation, cross-guild access, stale leases, character deletion and durable restart recovery. Use PostgreSQL integration tests for transaction claims; mocks cannot prove atomicity.

The current decoder failure was reproduced offline with `PYTHONPATH=server python3` and `struct.pack('>qH', guild_id, len(text)) + text` passed to `decode_body('out', 13744, body)`: guild 456 gives `17 undecoded bytes`; guild 281474976710663 gives `16 undecoded bytes`, with text `Prueba ñ`.

Once implemented, prepare two member accounts and a third nonmember, with the exact verified provisioning commands supplied by the implementation. Do not assume an unverified item-grant command exists. Run one complete acceptance session:

1. Create a guild with the required item and kamas. Expect one debit, stable identity, initial ranks and visible local/remote emblem; repeat the request and verify no second debit.
2. Invite the second account, reject once, invite again and accept. Expect consistent rosters on both clients and correct errors for expired or reused invitations.
3. Exercise rank creation, renaming, movement, assignment and restricted operations. Expect identical ordering and permissions on both clients; prohibited removal and escalation fail without state changes.
4. Send Unicode guild chat from different maps. Expect both members to receive it and the nonmember to receive nothing. Expel a member and verify subsequent sends are denied.
5. Rejoin, transfer leadership, leave and reconnect; also switch an owned hero. Expect correct membership and no stale leader or presence state.
6. Exercise implemented point/bonus, chest/treasury and Haven World operations, including unauthorized access. Expect exact persistent balances and verified effects without changing unrelated combat/spell behavior.
7. After a complete checkout build and automated validation, restart the single shared world in coordination with ongoing work. Expect guild identity, ranks, membership, balances and services to survive; disconnected members must not restore as online.
8. Dissolve according to verified rules and reconnect all clients. Expect no residual membership, access or active guild effects.

These are future acceptance steps, not tests claimed to have passed. Implementation must add exact UI actions, provisioning commands and service-specific expected values when their contracts are established.
