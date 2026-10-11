# Offline economy backend

`server/wakfu_server/characters/guild_economy.py` provides transactional APIs only. No native packet dispatcher, service startup, migration execution or combat effects are introduced by this module.

## Implemented authority

- `transfer_kamas`: current selected session and guild permission checks; account-wallet/guild-treasury atomic debit and credit; signed 64-bit balance limits; durable operation receipts reject conflicting retries; durable guild events record both resulting balances.
- `accrue_points`: trusted server events choose a configured source, never a client reward amount. Rewards obey a guild-wide UTC Monday weekly cap; durable `(guild_id,event_key)` receipts prevent duplicate accrual. Current guild membership is checked. All contributions share the guild row lock with membership changes.
- `bonus_operation`: configured catalog cost, prerequisite learning completion and learning duration; points debit, purchase state and event commit together. Repeated purchase is rejected; an identical operation-key retry returns its receipt. Learning state stores absolute milliseconds and survives process replacement. Activation supports explicitly configured permanent noncombat effects: sequential guild level, member capacity, weekly capacity and compartment unlocks. Effects and activation state commit together.
- `snapshot`: private economy state for the current selected member.

Policies are local deployment choices and do not claim official rates or limits. The migration inserts `economy` with every capability disabled. Enabling a capability requires `guild_policy.enabled=true` plus its capability flag. `permission_bits` maps action names to native bit indexes explicitly; no leader bypass exists. Actions are `treasury_deposit`, `treasury_withdraw`, `bonus_learn` and `bonus_activate`. Progression additionally requires positive integer `point_sources` rewards and `weekly_point_cap`. Bonus learning requires `bonus_catalog` keyed by decimal bonus ID with `cost`, `learning_duration_ms` and optional integer `prerequisites`. Point balances use authoritative guild columns and int32 wire bounds; service state stores the UTC week marker, treasury and bonus records.

## Explicitly unavailable integrations

`transfer_chest_item` now delegates to the guild chest custody engine. See the subsequent [guild chest implementation](GUILD-CHEST-IMPLEMENTATION-20261010.md) for migration 106, native access, item metadata, treasury routing and tests. No migration or deployment was performed.

Temporary and combat bonus activation raises `NotImplementedError`. Noncombat activation requires explicit catalog `effect` with `kind` (`unlock_level`, `member_capacity`, `weekly_capacity`, `unlock_compartment`), positive integer `value`, and `duration_ms=-1`. Only purchased, fully learned bonuses can activate; repeated activation fails. No member stat or combat effects are supplied. The extracted native catalog is evidence, not an automatically enabled gameplay policy. A verified effect implementation must preserve the current transaction and combat/stat paths.

Haven World ownership, acquisition and operations are outside these APIs. No unknown request opcode is fabricated.

## Verification battery required before enabling

Use an isolated PostgreSQL test database, never the running world database. Run treasury deposit/withdraw and verify conservation, unauthorized/stale sessions, insufficient funds, overflow, retry conflict and rollback after injected event failure. Run parallel withdrawals against the same treasury and account wallet, and concurrent expulsion against transfer. Exercise point events twice, conflict reuse, cap exhaustion, Monday rollover, two concurrent contributors, expelled/deleted contributors and durable receipts after reconnect. Exercise prerequisite learning boundaries, insufficient points, concurrent duplicate purchase and rollback. Verify unsupported activation and unauthorized chest calls leave all balances, items, state and events unchanged.

No migrations or PostgreSQL integration checks were run as part of this implementation. Python compilation is syntax validation only. Eight offline boundary tests passed with `PYTHONPATH=server:server/tests .runtime/e18-venv/bin/python -m unittest server.tests.test_guild_economy`. Six PostgreSQL integration tests are prepared in `server/tests/test_guild_economy_postgres.py`; they require explicit `WAKFU_RUN_GUILD_POSTGRES_TESTS=1` before opening the isolated schema and were not executed. They cover treasury conservation/retry/rollback/overflow/concurrent withdrawals, weekly point cap and rollover, and bonus learning/activation.
