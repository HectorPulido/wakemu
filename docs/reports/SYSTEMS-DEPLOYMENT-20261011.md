# Systems deployment — 2026-10-11

Status: deployed and automatically verified at2026-10-11 08:07 UTC. All four services are healthy; the atomic lock and stable-server window are released. Graphical acceptance remains pending.

Request: `systems-20261011-stationary-reviewed`. Both Monsters / AI and Classes explicitly acknowledged this request in `WORLD_COORDINATION.md`; root acquired the atomic lock at08:02:03 UTC.

## Images and source proof

Images were built from the complete shared server checkout, with World built before AI. File hashes were checked inside the image archives without launching another World server.

| Service | Image | Verified image source files |
| --- | --- | --- |
| world | `sha256:ed508b166abd9280f619820ba0fea79b4304ce1df6a41dbb37ddc587c130ab5c` | 792 |
| ai | `sha256:8cc77ebedda2efd39b36ffae59f1f5d1192e670c5562199518710f14bfa77250` | 1114 |
| ecology | `sha256:827cd3895edc7d0c536e175d3f7ecc8846d1cba22e32a07c58a6a8071f6ea492` | 660 |
| admin | `sha256:b5694664fbb07b6faa6627dc8a567518248cddcbc80f8194d150383440c50b63` | 787 |

The source baseline records2445 files; all2264 Python files passed syntax validation. Known five Systems-only differences from the earlier Classes regression baseline are disclosed on the coordination board; all final source hashes remained stable through the build.

## Automated evidence

- Shared combat regression399 cases completed with zero failures/errors. Its11 PostgreSQL skips were then executed using isolated schemas/current migrations:11/11 passed. Independent Classes follow-up15/15 also passed; overlapping counts are not additive.
- Systems gates: core133; planting/weather109; Haven Bag60; corpse59; E05 builds26; chat/bans/admin37; NPC/weather22; rift/drop context25; final territory integration80 and updated territory module15.
- Planting native oracle60,802 arithmetic/display combinations, actual retained-effect lifecycle, native weather consumers and corpse visibility oracle passed. The native planting bonus remains disabled pending graphical acceptance.

## Backup and preserved policy

A consistent custom-format mutable-runtime backup is stored privately with verified archive listing and SHA256. It includes the complete schema and mutable game data, but deliberately excludes data for native_catalog_records/native_catalog_documents; it is not a standalone full catalog backup. Previously running images are tagged for recovery.

No bulk monster activation is included. Catalog677 and all247 existing enablements, separately pinned mining/fishing revisions and native combat flags must remain unchanged. PostgreSQL, Redis, cron, shop and admin-control are outside this restart.

## Acceptance

Run the [complete systems manual journey](SYSTEMS-MANUAL-ACCEPTANCE-20261011.md) after final runtime verification. Issues21,29,33 remain open for Hector. NPC rollout contains four explicitly local initial conversations, not verified original world-wide placements. EPIC/RELIC and general combat sublimation effects remain open.

Private evidence directory: `.runtime/local/systems-deploy-20261011/`.

## Final runtime verification

Live source hashes match953 World files (including its shared AI SDK mount),1114 AI files,660 ecology files and787 administrator files. All2445 checkout hashes remained stable through verification. Startup logs contain no detected exceptions; World-to-AI health and local game/admin ports pass. Migrations118–123 applied; four enabled initial NPCs and both weather/planting policy settings are present. Active catalog677 and all247 enabled monsters exactly match the predeployment baseline. Ecology exposes the new bonuses domain and reported496 planned/delivered proposals, zero retries, no domain errors and no exhausted proposals at verification time.

No client files were modified. The existing open-planting profile and disabled native bonus flag are preserved. Known NPC placement and sublimation scope limits above remain open.

## Dashboard and independent postdeployment checks

Luna independently confirmed HTTP200 for the deployed dashboard and JavaScript, English Ban/Unban text and POST handlers, healthy ecology with bonuses and no domain errors or pending work, migration123 and four enabled NPCs. Evidence: `.runtime/local/postdeploy-readonly-check-20261011.log`. The available dashboard session was unauthenticated (401) and no browser controller was available, so the authenticated account editor and actual sanction journey remain manual acceptance, not a claimed visual pass. No sanctions were created by this check. Compose defaults now name the verified systems images for World/ecology and the matching AI build source; explicit owner image overrides remain available.

## Real HTTP sanction acceptance

After the initial read-only check, Luna authenticated to the deployed administrator API using the existing local bootstrap secret in memory and tested only a newly-created disposable account (private ID9). Missing CSRF was rejected403 and an empty reason400, both without creating a ban. Permanent ban rejected fresh authentication and token issuance and revoked all five token types plus session/heartbeat. Unban restored fresh authentication without reviving old tokens. A timed ban blocked authentication until expiry and old tokens remained invalid afterward. Administrator logout invalidated the dashboard session. Final normal audited HTTP cleanup left zero tokens, sessions and bans for this QA account; the disposable account itself is retained. No existing account was sanctioned. Evidence: `.runtime/local/ban-http-acceptance-20261011.log` and `.runtime/local/ban-http-cleanup-20261011.log`. This is HTTP/domain acceptance; authenticated visual editor rendering and native socket closure are separate checks.

## Live native NPC and session-ban acceptance

Using only QA account9 and its new disposable character23, a real TLS World session received all four native NPC appearance packets and the exact13222→12969 initial roots6274,6554,7122,7279. Rejoining at a verified distant cell rejected the old interaction with native349 and no dialogue. The real dashboard HTTP ban closed this active native socket0.719 seconds after the response. Final audited cleanup left the QA account unbanned with zero sessions/tokens/ban rows; its disposable character is retained. Evidence: `.runtime/local/npc-ban-tls-acceptance-20261011.log`. This verifies native transport, authoritative range checks and actual session termination; names/portraits/localized text rendering remain graphical acceptance. No client/server files or services were changed for this probe.

## Dashboard graphical acceptance limitation

The browser skill runtime initialized successfully, but URL selection reported no browser available and the documented discovery call returned an empty list. Authenticated graphical dashboard acceptance is therefore NOT RUN. The independently completed authenticated HTTP sanction journey and live TLS disconnect remain valid; they do not certify rendered controls.
