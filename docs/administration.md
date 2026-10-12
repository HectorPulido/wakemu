# Administration and troubleshooting

[Wiki home](README.md) · Related: [Getting started](getting-started.md)

## Local interfaces

| Interface | Default address |
| --- | --- |
| Game login API | `http://127.0.0.1:18081` |
| Shop | `http://127.0.0.1:18083` |
| Administration panel | `http://127.0.0.1:18084` |
| PostgreSQL | `127.0.0.1:15432` |

Admin credentials are stored privately in `.database/secrets/admin/admin-credentials.json`; they are separate from player accounts. The panel offers account and character management, map inspection, shop editing, settings, audit records, and service controls. Check the [setup prerequisites](getting-started.md#current-setup-requirements) for storage layout and upgrade precautions.

Item delivery and teleportation are delegated to world on the character's session. The panel tracks pending, completed, or failed receipts. A queued action is not yet a completed action, and a stale online indicator does not prove a character can receive it.

## Settings, builds, and storage

Settings are validated and stored in PostgreSQL. Some affect later actions immediately; others require a restart, and existing fights or dungeon instances may retain their starting configuration. Follow the editor's indication rather than assuming every setting is live.

World code comes from its Docker image. Editing source does not update that image. Build the complete checkout before restarting world, keeping AI and ecology compatible with it. Use a single world service rather than accumulating alternate servers.

Persistent service files live in `.database/`; generated logs and profiling files live in `.runtime/`. PostgreSQL uses the persistent `postgres-data` Docker volume. The included snapshot initializes an empty volume only. Back up current state before migrations or restoration; restoring a snapshot is not a merge. `.runtime/local/world.sqlite3` is historical and is not the active database.

## Troubleshooting

Start with service status and log checks:

```sh
docker compose ps
docker compose logs --tail=100 world ai ecology postgres
curl --fail http://127.0.0.1:18081/health
```

Then run `bash client-tools/client.sh check` if needed. It compiles local agents and checks network isolation without opening the game; it creates generated files.

- **World cannot start:** check imported PostgreSQL bootstrap records, secret mounts, migrations, and catalog revision errors.
- **Client cannot connect:** verify client version, service health, selected endpoint, and advertised world address.
- **Monster does not attack:** inspect AI and world logs; distinguish missing executable abilities from planning failures.
- **World stops evolving:** check ecology health and delivery errors; do not start a competing worker.
- **Progress disappears:** verify the active database and volume, then inspect save or ownership errors.

Detailed world events are written to `.runtime/local/logs/game-server.jsonl`. Remove credentials and player/session details before sharing logs.
