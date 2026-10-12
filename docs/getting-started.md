# Getting started

[Wiki home](README.md) · Next: [Architecture](architecture.md)

## What you need

Use Docker with Compose, Git LFS, Python 3 with Tk support, and JDK 21 or newer. The launcher supports macOS and Linux with a graphical desktop session. Supply your own compatible **Wakfu 1.93.1+79** installation; other versions are unsupported.

Put the installation directly inside `client/`:

```text
client/
  config.properties
  classpath
  contents/
  lib/
  jre/
```

## Current setup requirements

A fresh clone is not yet sufficient to start the complete game. World requires verified bootstrap records imported into PostgreSQL. It no longer reads `frames.jsonl` at runtime, and the reference event stream is not a replacement. See [Bootstrap internals](protocol/world-synchronization.md).

The database snapshot is fetched through Git LFS and restored automatically only when the PostgreSQL volume is empty. Read [database setup](../database/README.md) before restoring anything. Never delete an existing volume just to apply a code update.

`.database/` is the canonical private directory for persistent service secrets, administration state, shop assets, and local backups. `.runtime/` is created as needed for logs, compiled agents, profiles, and temporary outputs. Preparation creates all four service secret files in `.database/secrets/`; every Compose service reads the matching files from that directory.

For an existing installation, preserve the existing credentials **before** running preparation: copy the service secret files from the former `database/secrets/` or `.runtime/local/secrets/` into `.database/secrets/`, without overwriting existing files. Preserve admin state from the former admin directory as well. Keep the originals until the updated services have been verified. Do not generate a new PostgreSQL password for an existing database volume.
Copy `.env.example` to a private `.env` and verify that the catalog revision matches the restored database. Image and revision examples describe a particular development installation, not universally valid defaults.

## Build and launch

Once the required inputs are available:

```sh
git lfs pull
python3 tools/prepare-local-runtime.py
bash tools/build-local.sh
docker compose up -d --build
docker compose ps
bash client-tools/client.sh play
```

Preparation creates generated runtime directories and persistent PostgreSQL, scheduler, ecology, and admin-control secrets without replacing existing values. The build script builds world before AI and cron; Compose builds the other services as needed. World applies database migrations at startup.

The login dialog can register a local account. Use credentials for this experiment rather than your official game account. Create a character after entering the local world.

For a second player, run `bash client-tools/client.sh play --profile second-player`. Run `bash client-tools/client.sh check` to compile agents and check network isolation without opening the game. More options are in [Client tools](../client-tools/README.md).

If startup fails, continue with [Administration](administration.md#troubleshooting).
