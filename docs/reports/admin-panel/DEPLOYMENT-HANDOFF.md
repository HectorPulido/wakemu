# Configurable server display name — 2026-10-10

Settings now exposes `server_name`, initialized to `Rubilax` by migration 117.
It accepts 1–80 characters, at most 255 UTF-8 bytes, without control characters
or surrounding whitespace. The dispatcher reads PostgreSQL for every server-list
request and replaces realm 10's default and localized labels. There is no Redis
replica for this setting, so no separate cache update is needed. Saving subsequent
names requires no restart; reconnect the game account to refresh its server list.

Full current world source and attached AI/ecology were built and validated by
lifecycle operation `fd31d21f181941388861dec7761d894b` before activation.
World image: `sha256:80de6b29130ac40489446c95f6d8cc77180ff24654fe8b10d843e6cf33cb3ad9`.
Admin image: `sha256:6d36c4fb84afe74664bfea861e12c0130e40e0cf4207825b53bf4658a386b02f`.
Migration 117 applied at startup; active native catalog remained unchanged.
Prior world/AI/ecology image backups use `before-server-name-20261010` tags.

Validation: 26/26 protocol, PostgreSQL settings and HTTP tests passed. An
actual authenticated dispatcher TLS connection received `Rubilax`, then the
panel's temporary `Wakemu QA Ω` change on its next request without a restart.
After optimistic restoration, the complete response matched the initial packet
byte for byte. Temporary operator session was cleaned up. The deployed fixture
has no localized labels; unit fixtures cover their replacement when present.
Private probe: `.runtime/admin-ui/server-name-smoke.py`.

Manual acceptance: open Settings, search `server_name`, enter the desired name
and save. Disconnect the game account and sign in again. The server selection
card and selected server title should show the saved name; connect with an
existing character as usual.

---

# Persistent admin login sessions — 2026-10-10

Current admin image: `sha256:851527cd0720564244b074291dfa5aa9d5348727a3a97ebbf2c17c3d11603abe`.
Migration 116 was applied by the standard strict migrator. Session tokens are
persisted as SHA-256 hashes in PostgreSQL with CSRF, credential fingerprint and
eight-hour expiry. Existing memory-only sessions require one new login.

The real browser verified three F5 reloads, a real `docker compose restart admin`,
a further reload with the same session, then logout and reload remaining logged
out. All passed. PostgreSQL/session HTTP regression suites passed 12/12,
including expiry, credential changes and hashed token storage. Python compilation
and whitespace checks passed. Only admin was restarted; world was untouched by
this change.

---

# Expanded combat multiplier range — 2026-10-10

Combat XP, kama and drop multipliers now accept 0 through 9999999.9999,
with an exact 0.0001 multiplier quantum. Migration 115 widens the three basis-point
columns to bigint, preserving versions and active selections. Shared editor and
consumer limits match. Settlement caps packet amounts and remaining signed64
wallet/progression headroom, with limit flags in its immutable receipt.

The complete current world checkout and attached AI/ecology were built and
validated before restarting the single world. Lifecycle operation
`c1c7feb892b444e7a79ea65c9a0c67c5` completed healthy, including profiler recreation.
Current world image:
`sha256:5d0dee8340c5ffef0239cf92c0bdd6b98c587a06eae479af74347fc145aa2da2`.
Current admin image:
`sha256:05a658eb81210305c1ec2df370385a1409c9d685cf45d896ae552c4c2fbced63`.
Active catalog remains `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`.
Backup: `.runtime/backups/multiplier-range-20261010/runtime-before.dump`;
prior world/AI/ecology image tags use `before-multiplier-range-20261010`.

All 51 settings/reward-policy/drop tests passed with isolated PostgreSQL,
including golden formulas, replay, tiny/max multipliers and saturated settlement.
Native TLS + authenticated panel HTTP checks passed after activation: direct
delivery, idempotence, teleport PostgreSQL/Redis agreement, full-inventory
rejection and reconnect persistence. The temporary internal operator character
was retired. Existing configured multipliers were retained: XP 1, kamas 100,
drop 1. Migration 115 was applied by the standard world startup migrator.

---

# Combat multipliers in Settings — 2026-10-10

Current admin image: `sha256:28a027510ddc4d906010c9e9be49ece703f17fac3ab9fb9829aab5e2bed1d737`.
Settings exposes direct numeric multipliers for combat XP, kamas and drop,
backed by their existing versioned policy tables. No runtime multipliers were
changed permanently: the real browser saved/reopened/restored the XP multiplier
from 1 to 1.0001 and back to 1. All three settings were visible and returned
numeric values; mobile layout and remaining panel navigation passed.

The implementation retains compatibility with the deployed pre-114 dungeon
schema. Migration 114 belongs to independent dungeon work and was not applied
by this delivery. No world, AI or ecology restart was needed.

Verification: the complete settings PostgreSQL suite passed 11/11. After the
final numeric display normalization, all four multiplier/compatibility cases
passed again against current source. Python compilation and whitespace checks
passed. The deployed admin is healthy and all three multipliers read back as 1.

---

# Settings and service controls — 2026-10-10

The panel now includes all 262 PostgreSQL settings, scalar/JSON editors,
optimistic revisions, transactional auditing and immutable dungeon version
publication. Current admin image:
`sha256:635d692b533b9f2b269844050164b49e2aefb875debbf6389a1440b334e9e018`.
Private lifecycle broker image:
`sha256:58a3003b4e8709cd71e531912a317ac9d6f3c44a556816047d81241543438c51`.
Both deployed containers are healthy; the broker has no published port.

Verification: 17 settings/HTTP/broker regression tests passed, including real
isolated PostgreSQL. The final HTTP/broker rerun passed 13/13 after controller
changes. Real Chromium loaded every setting, saved/reopened/restored the combat
placement scalar and passed desktop/mobile navigation. All 40 current general
settings passed the consumer validation checks without modification.

Two real web-triggered world operations built and validated the images, then
correctly refused activation when concurrent combat/AI source changed. The
existing world remained healthy and was not restarted by either operation.
Operation receipts: `c670d0a2bf8b4ff8bf43f7895411ef25` and
`861f3a20ca6841dbb7a76bc8ecda1e56`.

A real browser-triggered profiler restart completed successfully, recreated the
previously stopped recorder and verified Docker health. The browser then passed
map/character/profiler/catalog navigation and logout. Full world activation
remains unverified in this milestone while concurrent source edits continue;
the two preparation/source-change abort checks above passed.

The following section is historical evidence for the earlier delivery and
teleport milestone; its image/catalog identifiers are not current deployment
claims.

---

# Administration deployment handoff — 2026-10-10

Hector requested that the concurrent server operator finish first. That work
finished and Hector authorized resuming validation on 2026-10-10 at 16:13 local
time. The final checks below passed without further server restarts.

## Final integrated result

World, AI, ecology and admin are healthy. Using the deployed panel's real HTTP
login, session cookie and CSRF token, the native TLS smoke verified:

- A connected temporary internal-account character received Jalamartillo 2027.
- The receipt completed; repeating the same request reused its handle and did
  not grant another item.
- Teleport to Sufokia 235 completed and matched PostgreSQL and the panel.
  The active Redis journal was absent or matched the new destination/baseline;
  no stale source location remained to overwrite the teleport.
- Filling all 34 inventory slots made the next delivery fail with the English
  inventory-full error and no additional item.
- Reconnecting retained all delivered items and the teleport destination.
- The temporary internal-account character was retired through Store deletion
  and its session closed. No player account or character was changed.
- Profiler status was available, with 25 feature timing rows.

The rest of this document retains the deployment dependency and image evidence.
The earlier pending action check is now complete.

## Delivered panel

Admin is deployed at <http://127.0.0.1:18084>, image
`sha256:11de4e08777ceaec273206ea296553ace8079b0a3c753d422cbc4de89d269f7b`.
The UI includes Characters, direct delivery, teleport, named maps and profiler;
sales/revenue UI was removed. Browser QA passed, including map detail, character
modal and mobile layout. World exposes the new API endpoints and the final native TLS check passed.

## Shared server dependency

A concurrent full world deployment failed during prewarm because current combat
code requires `native-spell-resource-costs.json`, absent from the previous active
catalog. The administration thread used the supported staging tool to validate
and prepare a complete release, then activated it transactionally after checking
that its sole document difference was this addition:

- Previous: `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095`.
- Active at handoff: `1d428d93dd4eeea23c81d10230b33e7bfd897671930efaf8d56ac1c0e82b19f6`.
- Added document SHA256: `fb10cfe102215efac81153552aa112a3a92d95d91dff76e53fb036d754f827b0`.
- Full release: 7,484 documents. All previous document hashes are unchanged.
- Source export: `.runtime/combat-review-20261010/native-spell-resource-costs.json`.

No monster activation release was selected. Catalog readers pin the active
revision and images enforce matching `WAKFU_CATALOG_REVISION`, so a world/AI
image pinned to an earlier revision fails startup. Check the current active
revision again before deployment; another operator may have changed it.

Full current source images built by this thread:

- `wakemu-world:admin-actions-20261010-r77`, SHA
  `5ae93ddb2461e121d1165131c60ce5736a81c6d469afc589c472f82180138e69`.
- `wakemu-ecology:admin-actions-20261010-r77`, SHA
  `45db0670c6bd44b1dcf0fc7c573a5e38330a06189dc2cb31c0577f489b6272ca`.
- AI build SHA `95439c8f75b8e36a1a9eaf90191e14e9d5059e750bec9d05beb1ed15373efba9`.
  Its shared `wakfu-local-ai` tag may have been replaced by another build.

All three were pinned to the new cost-only revision. World matched all 631
shared Python source files at build verification. Recheck against the current
checkout before reuse because concurrent source edits may have followed.
Compose defaults were updated to these matching world/ecology tags and AI build
arguments. The concurrent operator subsequently recreated services using their
own rollback images; these images are not a claim of a healthy final deployment.

Historical migration checksums were repaired by restoring exact original source
104/106 and applying additive 110/111 through the normal strict migrator. Both
applied successfully. Runtime backup is
`.runtime/backups/admin-actions-20261010/state-before.dump`.

## Verification and next step

- 42 executed tests passed in the administration/API/position gate; 9 real Redis
  cases were initially skipped and then passed separately in Redis DB15.
  Total: 51 executed cases, not 60.
- 13 live-console/ecology integration tests passed with real PostgreSQL.
- 12 spell-cost/overflow/Hupper resource tests passed in the complete world image.
- JavaScript syntax, Python compilation, Compose validation and diff whitespace
  checks passed.
- Real Chromium: login, all navigation, Sufokia native map destinations, character
  modal, profiler, catalog editor, mobile layout and logout passed.

After the server operator finishes, verify health and the presence of
`/test/admin-sessions` and `/test/admin-command` using the private operator token.
Do not print the token. The prepared native TLS smoke is
`.runtime/admin-ui/world-actions-smoke.py`; it creates and retires a temporary
character of the internal operator account and checks receipt completion,
delivery idempotency and PostgreSQL/panel teleport agreement. It passed, including full inventory rejection and reconnect persistence.
The complete manual acceptance flow remains available in README.md for Hector.
