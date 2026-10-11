# Wakemu administration panel

The English administration panel runs at <http://127.0.0.1:18084> as the separate
Compose service `admin`. Credentials are private in
`.runtime/local/admin/admin-credentials.json`. The Dofus portal was inspected
as a read-only reference; its database and credentials are not reused.

## Features

- Dashboard: accounts, characters, connected sessions, active fights and service health.
- Accounts: search, creation, password reset, administrator role and kama balance.
  Account editing requires the player to be offline and uses the login account lock.
- Characters: location, inventory, direct item delivery and teleportation.
- Maps: native English names, administrative overrides/notes, occupancy, native
  bounds, resources, monster groups, transports and validated walkable destinations.
  Missing native names explicitly display `Map #ID`.
- Shop: articles, categories, native item search, prices, quantities and visibility.
  Stock remains unlimited. Catalog changes are read without restarting the shop.
- Profiler: optional read-only recorder status and timing reports. When the
  recorder is unavailable, the panel can read the world's latest metrics file
  and displays its age and source. Recorder availability is reported separately.
- Settings: all PostgreSQL settings, search/category filters, typed scalar editors
  and an advanced JSON editor. Optimistic revisions reject stale overwrites;
  validation rejects malformed or unsupported configurations before saving.
- Service controls: restart world, ecology, shop, AI or profiler with durable
  operation receipts and actual health checks.
- Administrative audit. Sales history and revenue are absent from the interface.

## Authoritative actions and persistence

Direct delivery submits `!item <reference> <quantity>` and teleportation submits
`!tp <map> <x> <y> <z>` through the existing live console. World executes them on
the owning character session thread. Characters must be connected. Inventory
capacity, native stack limits, combat state and native destination geometry are
checked by the existing game implementation. The panel reports the actual
pending/completed/failed receipt; an accepted queue entry is not reported as a
completed delivery. Retries reuse the original request identifier and pending
receipts are polled without submitting another action.

Inventory and account/catalog metadata are authoritative in PostgreSQL and do
not have mutable Redis copies. Movement uses the existing Redis position
journal. The panel reads only records matching the active session generation,
owner and PostgreSQL baseline. Teleportation flushes pending movement, commits
its database transition, clears the old journal using CAS and attaches the new
position baseline. The panel never writes a competing Redis position itself.
If Redis is unavailable, it shows the persisted PostgreSQL position.

Presence uses game session leases. Normal disconnect removes the lease; after
an abrupt crash it can remain visible for up to 300 seconds. Actions additionally
check the world's live session registry, so a stale lease cannot deliver an item.

The browser uses HttpOnly/SameSite sessions and CSRF protection. World delegation
requires a dedicated game administrator API credential, stored privately in
`.runtime/local/admin/world-api-token`. Its account is `admin-panel-service`;
no player's administrator role is reused. The credential expires after one year
and must be renewed through the existing Store token mechanism if revoked or
expired. Neither credentials nor token values belong in commits or screenshots.

## Build and schema

```sh
docker compose build admin
docker compose up -d --no-deps --no-build admin
docker compose ps admin
```

Changing world command endpoints requires a complete validated world image and
restarting the single shared `world`. Preserve concurrent combat/spell changes.
The matching ecology service must run when world uses external ecology mode.

Historical migrations 104 and 106 were restored to their exact applied checksums.
Their subsequent schema changes are additive migrations
`110_ecology_delivery_recovery.sql` and `111_guild_chest_native_capacity.sql`.
The normal strict migrator applied both successfully; no stored checksums were
rewritten. Backup: `.runtime/backups/admin-actions-20261010/state-before.dump`
(immutable native catalog data excluded).

## Complete manual acceptance flow

1. Connect a game character outside combat and its Haven Bag. Open
   <http://127.0.0.1:18084>, sign in and open **Characters**. Search its name and
   click **Manage character**. Its online state, map name, instance and coordinates
   should match the game. Move, then refresh to check the latest position.
2. In direct item delivery, select item reference `2027` (Jalamartillo), quantity
   `1`, and submit. Wait for the completed receipt. Exactly one item should appear
   in game and the refreshed panel inventory; the kama balance should not change.
   If inventory is full, the action should fail without adding the item.
3. Use **Maps**, search `Sufokia` (map `235`) and open its detail. It should contain
   a name, geometry information and validated destinations. Select the connected
   character and **Use destination**. Confirm the teleport in the character form.
   Wait for completion: the game and panel should show the selected coordinates.
4. Disconnect and reconnect. The delivered item and final position should persist.
   An offline character's delivery/teleport controls should be disabled.
5. Open **Profiler**. Timing rows should appear when a report exists. A missing
   recorder should display **Unavailable**, with the fallback report's source and
   age where available. Absence of profiler data must not break other pages.
6. Check **Accounts**, **Articles**, **Categories** and **Audit**. Existing catalog
   editing should still work. There should be no purchases/revenue section.
   Check the panel at a narrow mobile width and then log out.

## Automated verification

Regression suites cover HTTP authentication/CSRF/routes, isolated PostgreSQL
administration, command delegation and revocation, live console idempotency,
Redis position ownership and teleport transitions. Tests use UUID-isolated
schemas in `wakemu_migration_test`, never runtime tables.

```sh
PYTHONPATH=/app:/app/tests \
WAKFU_RUN_ADMIN_POSTGRES_TESTS=1 \
WAKFU_POSTGRES_TEST_URL='host=postgres dbname=wakemu_migration_test user=wakemu' \
python -m unittest test_admin_http test_admin_domain_postgres \
  test_api_authorization test_live_console test_position_redis -v
```

Run inside Compose with the configured database password file. Private browser
screenshots and smoke scripts are under `.runtime/admin-ui/` and
`.runtime/admin-ui-qa/`. Verification results and deployed images are recorded
in [DEPLOYMENT-HANDOFF.md](DEPLOYMENT-HANDOFF.md). The panel and world are healthy. The final authenticated HTTP/native TLS
action check passed on 2026-10-10, including full inventory rejection and
reconnection persistence.

## Settings and lifecycle controls

Settings writes use a PostgreSQL transaction including the audit event. The
existing ecology dirty trigger publishes invalidation durably. Settings have no
mutable Redis replica; consumers use the existing database/Redis architecture,
without creating a second competing settings cache. Most settings apply to new
actions or cycles. `dungeon_runtime_routes` requires a world restart, identified
in the editor. Already running fights and dungeon instances are not rewritten.

Dungeon configuration documents remain immutable: editing publishes a validated
new version and updates its active configuration/context policies together.
The active-version editor can select an already installed configuration. Schema
versions and identifiers are protected; the panel does not enable unfinished
server features by accepting arbitrary JSON keys.

The internal `admin-control` service alone has the Docker socket. It has no
published host port, requires a private bearer token and only accepts the five
fixed service names. The web container does not receive Docker access. Restart
requests are serialized and deduplicated by request ID; interrupted operations
are reported rather than silently replayed. After a long build, **Check status**
reads the original operation without starting another restart.

Before stopping world, the controller builds the complete current checkout and
its attached services, compiles the image, compares deployed source hashes and
runs live-console/API regression tests against the isolated test database. It
aborts if source or the active catalog changes during preparation. It then
recreates world and waits for health before recreating attached AI, ecology and
profiler. The profiler must be recreated to attach to the new world PID namespace.
A failed preparation leaves the existing server running; a failure after
activation is reported explicitly and requires investigation.

Run Compose commands from the repository root: the controller uses the matching
absolute host project path for Docker bind mounts. Its private token lives in
`.runtime/local/secrets/admin-control-token`, and operation receipts/diagnostics
live under `.runtime/local/admin-control/`.

### Settings acceptance flow

1. Open **Settings**, choose **Combat**, and edit
   `combat_placement_duration_ms`. Record its original value, save a small change,
   reopen the editor and verify persistence. Restore the original value. New
   combat placements use the saved duration; existing fights are preserved.
2. Open a JSON policy and verify its structure is readable. Invalid JSON or an
   invalid policy must fail without changing the persisted configuration.
3. Under service controls, choose **Restart world**, confirm the disconnect
   notice, and follow the operation phases. If preparation takes over a minute,
   use **Check status**. Completion requires healthy world and attached services.
4. Reconnect the game character, verify inventory/location persistence and open
   **Profiler** to verify the recorder attaches to the recreated world.

The Settings regression gate includes real PostgreSQL transaction/conflict
checks, HTTP authentication/CSRF/body limits, and broker allowlist, deduplication,
recovery and deployment source-change checks. Real browser verification edits
and restores a setting and checks all 262 records plus mobile layout.

### Combat reward multipliers

Settings includes `combat_xp_multiplier`, `combat_kamas_multiplier` and
`combat_drop_multiplier` under **Combat**. Enter the direct multiplier:
`1` means normal, `2` means double, `0` disables that reward. Values support
0–9999999.9999 with up to four decimal places. These are editor aliases backed by the
existing `combat_reward_policy_versions` / `combat_drop_policy_versions` and
active selectors, not duplicate rows in `settings` or Redis.

Each save locks the active selector, checks the editor revision, inserts a new
policy version preserving sibling rates and switches the selector with the
audit event in one transaction. Existing policy versions and awarded receipts
are preserved. The next new reward calculation reads the active policy directly
from PostgreSQL; no world restart is needed. The drop multiplier changes drop
probability, subject to the existing probability cap; it does not multiply item
stack quantities or character XP.

Acceptance: filter Settings by `combat_`, open each multiplier and verify its
current value. Save the desired multiplier, reopen to verify it, and win a new
PvE fight. Previously awarded rewards must remain unchanged. Restore the original
multiplier after a temporary balance test.

Multiplier range migration 115 widens combat XP/kama/drop basis-point columns
from integer to bigint without rewriting policy versions. Their consumers and
editor share the same maximum of 99,999,999,999 basis points. The smallest
nonzero multiplier remains 0.0001. Native drop probability still caps at 100%.
Combat settlement caps new rewards at packet limits (signed64 XP, signed32 kamas)
and remaining signed64 progression/wallet storage, recording native limit flags
in its receipt. A large multiplier cannot wrap a reward or overflow the wallet.
Existing golden math and recorded receipts remain unchanged. Profession XP is
configured separately and is not changed by this combat policy migration.

### Persistent administrator sessions

Administrator sessions now live in PostgreSQL (`admin_panel_sessions`, migration
116), surviving F5, browser navigation and administration container restarts.
The cookie and database session expire after eight hours. PostgreSQL is the
session authority; no mutable Redis session cache is introduced. Only a SHA-256
hash of the opaque browser token is stored. CSRF remains required for mutations.
Logout deletes the database session immediately; a credential fingerprint rejects
sessions issued for another username/password configuration. Expired sessions
are cleaned during login, and the existing 100-session limit is preserved.

One new login is required after upgrading from the old in-memory implementation.
Acceptance: sign in, press F5 repeatedly, restart only the administration service
with `docker compose restart admin`, and press F5 again. The panel must restore
the session without asking for credentials. Sign out, press F5 and verify that
login is required. The game server does not need a restart for this change.

### Server display name

`server_name` in Settings controls the realm label shown by the game client's
world selector. It defaults to the previous name, `Rubilax`. Names support 1–80
characters and at most 255 UTF-8 bytes, without control characters or surrounding
whitespace. The dispatcher reads PostgreSQL on every server-list request and
replaces both the default name and any localized name overrides for realm 10.
Endpoints, realm identity, type and other native metadata remain unchanged.
There is no mutable Redis name replica and no restart is needed after a name edit.

Acceptance: edit `server_name` in Settings and save. Disconnect the game account
and sign in again to request a fresh world list. The new name should appear on
the server card and selected-world title, and the existing character should
connect normally. Restore the prior name after a temporary test.
