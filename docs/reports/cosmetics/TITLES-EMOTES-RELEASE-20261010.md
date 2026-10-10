# Titles and emotes: prepared world release

Status: built and verified, not activated by this task. No running service was
restarted and no runtime gameplay tables were changed. PostgreSQL tests used
disposable schemas in `wakemu_migration_test`.

## Prepared image

- Image: `wakemu-world:titles-emotes-ready-20261010`
- Image ID: `sha256:625abfe281aa4a68b47781eec04f019aafc7b86367c985eb4ab0b500910b21d3`
- Source manifest SHA256: `f8807d8256f51edee826ad73282e2bcd190616fdb20ac62ef3f1c4b3efb058f3`
- Catalog revision: `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`
- Image archive verification: all **689** expected production files match the
  complete shared checkout; no missing, differing, or changed-since-build files.
- Includes migrations through **097**, including the previously prepared rift
  rewards and six-member policy. Existing combat and spell source is included.

The manifest, build image ID and archive verification are recorded under
`.runtime/local/releases/titles-emotes-20261010/`. This image is a frozen build:
later shared source changes require a new complete build before promotion.

## Validation

- Titles/emotes gate: **26/26 passed**, including isolated PostgreSQL migration,
  account ownership, flag changes, item consumption, retry, native ID mapping,
  alternate characters, target scope, occupations and rejected-request keepalive.
- Shared cosmetics/mount regression gate: **52 passed**, one existing
  capture-dependent check skipped because its mounted capture is unavailable.
- Native Java title and emote consumers: passed.
- Full production Python compilation, entrypoint shell syntax and Compose
  configuration validation: passed. This is not a full-suite or visual claim.

## Launch the prepared image

From the repository root, when deploying this frozen checkout:

```sh
WAKFU_WORLD_IMAGE=wakemu-world:titles-emotes-ready-20261010 docker compose up -d --no-deps world
docker compose ps world
docker compose logs --tail=100 world
```

The normal entrypoint applies pending migrations before starting the server.
The command replaces only the existing world service; it does not create an
additional world or build an overlay. It has not been executed by this task.
Keep the same `WAKFU_WORLD_IMAGE` override in subsequent Compose commands if
this image is intended to remain selected; the checkout's default image tag
belongs to the parallel deployment workflow and was not changed here.

## Emote policy

Migration097 defaults `settings.emote_policy.unlock_all` to `true`. All 319
verified native emotes are exposed without writing permanent learned ownership.
With `false`, only emotes explicitly learned by that account are authorized.
This is a database flag; no environment-variable override is required.

To require learning after deployment:

```sh
docker compose exec -T postgres psql -U wakemu -d wakemu_runtime -c "UPDATE settings SET value=jsonb_set(value,'{unlock_all}','false'::jsonb) WHERE name='emote_policy';"
```

Restore the default with the same SQL and JSON value `true`. Play authorization
reads the policy immediately. Reconnect to refresh the visible emote list;
a rejected unlearned request also sends a fresh authoritative list. The native
client considers all exposed emotes known, so test item learning with the flag
set to false. Changing the flag does not delete learned ownership.

## Complete manual acceptance

Use two accounts with clients on the same map, plus an alternate character on
the first account. Complete both linked procedures:

1. [Titles: consumption, selection, peer visibility, reconnect and alternate
   characters](TITLES-IMPLEMENTATION-20261010.md#manual-acceptance-after-deployment).
   Exact fixtures: `!item 11431 2`, `!item 7749 1`, `!item 14199 1`.
2. [Emotes: ordinary and targeted playback, late peer visibility, flag toggle,
   permanent learning and persistence](EMOTES-IMPLEMENTATION-20261010.md#manual-acceptance-after-deployment).
   Exact learning fixture: `!item 8189 1` while `unlock_all=false`.
3. Restore `unlock_all=true` after the restrictive-mode test. Reconnect and
   confirm the complete list returns while the learned emote remains durable.

Costume, aura, sprint, finisher and mount selections must survive the title
journey. Neither learning nor selecting cosmetics should move a player out of
their current Haven Bag room or interrupt combat. Record the first failing step,
character and time; graphical acceptance remains pending the user run.
