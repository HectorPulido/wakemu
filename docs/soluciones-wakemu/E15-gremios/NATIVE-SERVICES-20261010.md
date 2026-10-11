# Native guild service contracts (2026-10-10)

## Evidence and limits

Read-only `javap -p -c` inspection of installed `client/lib/wakfu-client.jar`, followed by an offline Java helper loading only `eHu` bonus definitions. No client GUI, network session, database, container, migration or service was started. Runtime inspection artifacts are private under `.runtime/e15-*`; the derived catalog is [native-bonus-catalog-20261010.json](native-bonus-catalog-20261010.json).

## Bonus purchase, progression and catalog

`cBS.d()` is **15613**. Its body is exactly one big-endian **i32 bonus ID**; it contains no guild ID, price, duration or actor ID. `dgl` sends this request for the chosen UI bonus. `dgt` resolves `eHy.Qg(currentLevel + 1)` and sends the same request for guild level advancement. Therefore the authenticated session must determine guild and authority; all prices and prerequisites must come from the server catalog.

The native `eHu` enum contains **78** definitions with noncontiguous IDs from 1 to 86. `fgS` exposes definition ID, learning duration, activation duration, point cost, effect and scope (`MEMBER_BONUS`, `GUILD_BONUS`, `CRITERION_BONUS`). The extracted JSON preserves these fields. Native nonfinite duration is represented as **-1** in the artifact; `TT.bjC()` alone returns zero for that sentinel, so it must be accompanied by `TT.aYZ()` when extracting. Do not interpret every zero as immediate expiration.

Verified service definitions:

| IDs | Effect |
| --- | --- |
| 11, 33, 50, 69 | Unlock guild storage compartments GUILD_1 through GUILD_4 |
| 25 | Set points earned factor to 1.1 |
| 42 | Increase weekly points limit by 1500 |
| 51 | Increase parallel learning by 1 |
| 74–83 | Set guild level to 1–10 respectively |
| 84 | Unlock Haven World; cost 100000 points, nonfinite learning/activation duration |
| 85, 86 | Increase member capacity by 50 each |

`fgF.isFull()` uses 200 + bonus member capacity. `fhT.gbw()` reads feature configuration `eEL.pcJ`; its declared default is **7500** (`feature.guild.points.maxPerWeek`). Bonus speed configuration `eEL.pcI` defaults to **1.0** (`feature.guild.bonus.speed.factor`). These are client defaults, not proof that a remote server cannot override them. `bwQ` calculates learning-speed input using the guild factor, local guild factor and configured speed factor; permanent activation and learning must be handled separately.

`fhU` compares learning completion against purchase date plus adjusted learning duration. Activation date is separate. Therefore merely purchasing a definition must not immediately apply every effect. The snapshot already has distinct `buyDate` and `activationDate` fields. Exact earning events, per-fight award formulas, client prerequisite evaluator semantics, and every MEMBER_EFFECT's combat payload remain unverified. Preserve combat/spell behavior: effect IDs in the catalog are references, not invented stat changes.

## Shared chest and treasury requests

Guild storage uses the shared compartment system (`bQA.GUILD`, `bQC`); these opcodes also serve other storage kinds. They must be bound to an authenticated, authorized open storage session rather than interpreted as guild access by opcode alone.

| Native class / opcode | Exact body |
| --- | --- |
| `cpv` / 12844 | i32 compartment ID |
| `cpw` / 12004 | i32 compartment ID |
| `cpu` / 14616 | i32 source compartment ID, i8 source slot, i32 destination compartment ID, i8 destination slot |
| `cpx` / 12531 | i32 compartment ID, i8 operation ordinal, operation-specific bytes |

`bQC.emI` sends 12844; `bQC.emJ` sends 12004. Their exact server state transitions and response carriers still require tracing. Do not label these as proven open/close contracts solely from their names.

`fma` operation ordinals for 12531 are **0 ADD_ITEM, 1 REMOVE_ITEM, 2 MOVE_ITEM, 3 ADD_MONEY, 4 REMOVE_MONEY, 5 GAME_ADD_ITEM**. Verified operation payloads:

- `fmb` (ADD_ITEM, ordinal 0): 15 bytes, i64 source item UID + i32 item reference + i16 quantity + i8 destination storage slot.
- `fmh` (MOVE_ITEM, ordinal 2): 9 bytes, i64 item ID + i8 storage slot.
- `fmj` (REMOVE_ITEM, ordinal 1): 23 bytes, i64 source item UID + i32 item reference + i16 quantity + i64 destination inventory container UID + i8 destination inventory slot.
- `fmd` (ADD_MONEY, ordinal 3) and `fml` (REMOVE_MONEY, ordinal 4): i64 amount.

Client permission checks are advisory. The server must enforce membership, compartment rights, withdrawal permissions, wallet ownership, positive quantities/amounts, inventory compatibility and locking in one transaction. Reject server-only GAME_ADD_ITEM from clients. The exact shared storage response/snapshot contracts were not established in this pass.

## Implementable now and remaining evidence

Implement strict 15613 parsing, the native bonus catalog, transactional point accounting, durable purchase/learning/activation state, configuration-backed weekly reset and cap checks, and derived noncombat guild effects. Unit tests should use explicit clocks at learning, activation, expiration and week boundaries; concurrent purchase and duplicate requests require transactional tests.

Implement storage and treasury domain transactions with an explicit storage access context and ledger, but do not fabricate native responses. Native GUI storage integration needs verified compartment bootstrap/update/error responses. Haven World unlock metadata is proven; ownership allocation, auctions, world topology, construction and entry transport are independent contracts and remain unverified. A permission name or bonus ID does not establish these rules.

## Shared storage response evidence (2026-10-10 follow-up)

`bBX` opens `blL` occupation **23** locally for `QT.START_BROWSING` action **12** and closes with action **13**. `fil.GUILD_1` through `GUILD_4` use IDs **0..3**, each with **40 slots**. These are distinct from the account chest protobuf compartment system.

- **14424 / cDo:** i32 enabled-map count, repeated (i32 compartment ID, bool byte), i64 treasury, remaining bytes `kh` history protobuf.
- **14787 / cDn:** raw `kt` protobuf, repeated `kd` compartment field 1 and required `kh` history field 2. `kd` fields are required int32 ID (1), required bool enabled (2), repeated `kK` positioned items (3), optional int64 metadata (4). `kK` contains required `kX` item (1) and required int32 slot (2). The optional compartment metadata is omitted and the installed loader defaults it to -1.
- **15817 / cDp:** i64 treasury, i32 history byte length, `kh` protobuf.

`fij.g(kd)` clears and repopulates that compartment. Therefore complete snapshots can safely replace affected compartment contents after a committed transfer. The wire implementation sends empty valid history protobufs; durable server audit is independent and history UI population remains a separate addition.

The earlier request field labels were corrected by tracing `dbM`, `bQC`, `fmb` and `fmj`: **the i32 is the item reference, and the i16 is quantity**, not an inventory position. Withdrawal source slot is derived from the authoritative source item UID; it is not sent by the client. The withdrawal i64 destination identity is the owned inventory container UID, and its trailing byte is the destination inventory slot.

An offline headless Java oracle parsed Python-generated carriers through installed `cDo`, `cDn`, and `cDp`; verified four 40-slot compartments, item UID 99 at slot 3, required fields, and exact protobuf reserialization. Optional item element/shard serializers were stubbed empty for this minimal fixture to avoid runtime database catalog loading. No database, services, containers, GUI or network sessions were started.
