# Getting started

[Wiki home](README.md) · Next: [Architecture](architecture.md)

This guide starts a new Wakemu server from the files in this repository. You do not need the game client, a database dump or private captures to install the server. Installing the client is an optional final step.

If you already have a working server with characters you want to keep, go to [Existing installations](#existing-installations) instead.

## 1. Prepare the machine

The verified server installation used **Debian 12, 4 CPUs, 16 GiB of RAM and an 80 GiB disk**. Use that as the tested baseline. A separate 4 GiB machine ran out of memory while importing game data, before World started.

You need Git, Python 3, Docker Engine with Buildx, Docker Compose v2 or newer, and internet access to download packages and images. Python packages for the server run inside Docker; you do not need to install them on the host.

On Debian, install Git first if it is missing:

```sh
sudo apt-get update
sudo apt-get install -y git
```

Clone the repository and enter its directory:

```sh
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/HectorPulido/wakemu.git
cd wakemu
```

Skipping Git LFS downloads avoids fetching old recovery dumps and capture archives. They are not needed for this installation.

Then prepare the host:

```sh
sudo bash tools/bootstrap-debian-host.sh
```

This helper supports Debian 12 and 13. It installs missing prerequisites and preserves a working Docker installation. The complete clean-install flow has been verified on Debian 12.

The server commands below use `sudo` for Docker access. If you are already root, omit `sudo`. On a machine where your user can already run Docker, you can also run the installer and Docker commands without it.

## 2. Install the server

Run this from the repository root:

```sh
sudo python3 tools/install-wakemu.py
```

The installer creates its own configuration and credentials. You do not need to copy `.env.example`, run `git lfs pull`, restore a snapshot or import SQL by hand.

It builds and starts five services: PostgreSQL, Redis, World, AI and the shop. It also applies migrations and loads the versioned game data, fresh bootstrap templates, environmental missions, dungeon configuration, shop content and treasure rules.

Keep the terminal open while it works. Large catalog imports can spend time on a single document. The verified cold installation took about 11 minutes; downloads and machine speed affect the duration.

At the end, expect:

```text
Installation VERIFIED; receipts: ...
```

`VERIFIED` means the content checks passed and a real registration, character creation, native login and reconnection succeeded. The check creates a dedicated test account and character; register your own account when you play. It does not replace testing gameplay with the graphical client.

`READY_UNVERIFIED` means login verification was explicitly skipped. It is not the same result.

## 3. Check that it is running

Use the installation's generated configuration, rather than the separate development Compose stack:

```sh
sudo docker compose \
  --env-file .local-state/installation/wakemu-install/compose.env \
  -f compose.install.yaml \
  -p wakemu-install ps
```

All five services should be running and healthy. On the server machine, you can also open:

| Address | What it provides |
| --- | --- |
| `http://127.0.0.1:18081/health` | World health response |
| `http://127.0.0.1:18083` | Shop |

The native game and dispatcher ports are `15556` and `15558`. By default, the host ports are bound to localhost. On a remote machine, `127.0.0.1` means that server, not your desktop; this command does not publish an internet-facing game server.

To read recent World logs:

```sh
sudo docker compose \
  --env-file .local-state/installation/wakemu-install/compose.env \
  -f compose.install.yaml \
  -p wakemu-install logs --tail=100 world
```

Gameplay events are written to the World data directory:

```sh
sudo tail -n 100 .local-state/installation/wakemu-install/world/logs/game-server.jsonl
```

## 4. Keep the installation data

The default installation directory is:

```text
.local-state/installation/wakemu-install/
  compose.env       Generated configuration and image references
  database/         Private service credentials
  inputs/           Materialized installation data
  world/            World runtime files
  receipts/         Installation checks and verification results
```

PostgreSQL and Redis data are stored in Docker volumes. Keep those volumes and the installation directory together when backing up or moving the server. Do not commit credentials or runtime data to Git.

### If installation stops

If a download or build is interrupted, rerun the same installer command from the same checkout. Completed stages are recorded and reused. If it reports a source or data-pack mismatch, keep the existing state and inspect the error; do not delete volumes to force an update.

### If the final login check fails

For a failure during the final login check, keep the output and the files in `receipts/`. If the probe reached character creation, it may already have created its test account. After resolving the reported cause, use the explicit recheck:

```sh
sudo docker compose \
  --env-file .local-state/installation/wakemu-install/compose.env \
  -f compose.install.yaml \
  -p wakemu-install exec -T world \
  python3 /app/tools/verify_clean_install.py \
  --manifest /installation-receipts/verification-manifest.json \
  --receipt /installation-receipts/native-login-reconnect.json \
  --recheck-after-failed-probe /installation-receipts/zero-player-state.json
```

This requires the original empty-database witness and permits only the verifier's own test accounts. It refuses to overwrite a successful receipt. See [Administration](administration.md#troubleshooting) for further diagnosis.

## 5. Optional: install and launch the client

The server does not need Java, Tk or game assets. These are requirements for the desktop that runs the client.

Use macOS or Linux with a graphical desktop, Python 3 with Tk support, and JDK 21 or newer. Supply your own compatible **Wakfu 1.93.1+79** installation; other versions are unsupported.

Put its files directly inside `client/`:

```text
client/
  config.properties
  classpath
  contents/
  lib/
  jre/
```

For a server running on the same desktop, launch from the repository root:

```sh
bash client-tools/client.sh play
```

The login dialog can register your account. Use credentials for this server rather than your official game account, then create a character.

For a second player:

```sh
bash client-tools/client.sh play --profile second-player
```

To compile the launcher agents and check isolation without opening the game:

```sh
bash client-tools/client.sh check
```

For a server on another machine, read [Choose a private server](../client-tools/README.md#choose-a-private-server). That setup also needs a reachable server address and ports; changing a client setting alone does not expose a localhost-only server.

## Existing installations

The clean installer above is for a new installation, not an upgrade or restore command for an existing development stack. Keep using your existing Compose files, environment, credentials and database volumes. Do not replace them with a newly generated clean-install configuration.

The older local stack uses `.database/` for persistent credentials and administration state, and `.runtime/` for generated logs, agents and temporary files. Preserve its secrets before running preparation. If migrating from the former `database/secrets/` or `.runtime/local/secrets/` directories, copy the existing values into `.database/secrets/` without overwriting files, and keep the originals until the services are verified. An existing PostgreSQL volume must keep its matching password.

Read [Database setup](../database/README.md) for recovery and [Administration](administration.md) for operation. [Bootstrap internals](protocol/world-synchronization.md) explains the protocol templates; it is not a prerequisite for following the clean-install steps above.
