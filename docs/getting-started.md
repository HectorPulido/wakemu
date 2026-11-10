# Getting started

[Wiki home](README.md) · Next: [Architecture](architecture.md)

This guide starts a new Wakemu server using the clean PostgreSQL backup included in this repository. You do not need private captures or the game client to install the server. Installing the client is an optional final step.

If you already have a working server with characters you want to keep, go to [Existing installations](#existing-installations) instead.

## 1. Prepare the machine

The verified server installation used **Debian 12, 4 CPUs, 16 GiB of RAM and an 80 GiB disk**. Use that as the tested baseline. With the bounded importer, a separate 4 GiB machine completed the game-data imports and environmental mission setup, but ran out of memory when World started. Use the 16 GiB baseline for the complete server.

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

Skipping automatic Git LFS downloads lets you fetch only the clean backup in the next step.

Then prepare the host:

```sh
sudo bash tools/bootstrap-debian-host.sh
```

This helper supports Debian 12 and 13. It installs missing prerequisites and preserves a working Docker installation. The host preparation has been verified on Debian 12.

The server commands below use `sudo` for Docker access. If you are already root, omit `sudo`. On a machine where your user can already run Docker, you can run the Docker commands without it.

## 2. Install the server

From the repository root, install Git LFS and download only the installation backup:

```sh
sudo apt-get install -y git-lfs
git lfs install --local
git lfs pull --include="database/backups/wakemu-clean.dump" --exclude=""
(cd database/backups && sha256sum -c wakemu-clean.dump.sha256)
```

Expect `wakemu-clean.dump: OK`. On macOS, use `shasum -a 256 -c` instead of `sha256sum -c`.

The archive is approximately **240 MB**. It contains the native catalogs and their mining/fishing dependencies, synthetic protocol templates, public dungeon/shop/treasure content and static environmental rules. It has no existing characters, sessions, tokens, inventories or running-world ecology. Its only game account is:

| Username | Password | Permissions |
| --- | --- | --- |
| `admin` | `admin` | Administrator |

The account starts with no characters and a zero wallet. The administration website has separate locally generated credentials; see [Administration](administration.md).

In a **new checkout with no existing server data**, prepare the configuration and start the stack:

```sh
cp .env.example .env
python3 tools/prepare-local-runtime.py --runtime-root .local-state/wakemu/world
cp -R database/shop-assets/. .database/shop-assets/
sudo docker compose up -d --build
```

Preparation creates private service secrets and matches service permissions to their owner. The example configuration selects the catalog revision included in the backup. The copy command installs the shop images shipped with the repository.

PostgreSQL restores and validates the archive only when its data volume is empty. Existing volumes are never overwritten on restart. World then applies any newer migrations and builds the omitted compiled catalogs on its first startup; allow several minutes for this initial publication before game connections become available. Later unchanged starts reuse those publications. Ecology generates a new population from the static rules.

The archive was fully restored into an isolated PostgreSQL 17 database: all 561 table counts matched its manifest, empty player/ecology state was checked, and `admin` / `admin` authenticated successfully. See [Database setup](../database/README.md) for its manifest and standalone restore commands.

## 3. Check that it is running

Use the repository's standard Compose configuration:

```sh
sudo docker compose ps
sudo docker compose logs --tail=100 postgres world
```

PostgreSQL logs should include `Wakemu clean seed restored (admin/admin)`. World should become healthy after its first compiled publication. Normal restarts use `sudo docker compose up -d`; rebuilding is needed only when delivering code changes.

The services should be running and healthy. On the server machine, you can also open:

| Address | What it provides |
| --- | --- |
| `http://127.0.0.1:18081/health` | World health response |
| `http://127.0.0.1:18083` | Shop |

The native game and dispatcher ports are `15556` and `15558`. By default, the host ports are bound to localhost. On a remote machine, `127.0.0.1` means that server, not your desktop; this command does not publish an internet-facing game server.

Gameplay events are written to the World data directory:

```sh
sudo tail -n 100 .local-state/wakemu/world/logs/game-server.jsonl
```

## 4. Keep the installation data

The default local paths are:

```text
.env                         Compose configuration and image references
.database/secrets/           Private service and administration credentials
.database/shop-assets/       Shop images copied from the repository
.local-state/wakemu/world/   World runtime files and logs
```

PostgreSQL and Redis data are stored in Docker volumes. Keep those volumes, `.database/secrets/`, `.env` and the World directory together when backing up or moving a running server. Do not commit credentials or runtime data to Git. The repository's clean seed does not back up your players' later progress.

### If installation stops

Inspect `sudo docker compose logs --tail=100 postgres world`. If the backup is missing or is still an LFS pointer, repeat the targeted LFS download and checksum check before continuing. Keep existing volumes and inspect any restore error; do not delete a volume containing player data to force initialization.

The first compiled publication can take several minutes. A later unchanged start should report `compiled_publication_reused` instead of recompiling the catalogs. See [Administration](administration.md#troubleshooting) for further diagnosis.

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

Sign in as `admin` / `admin` and create your first character, or register a separate player account in the login dialog. Use credentials for this server rather than your official game account.

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

The steps above are for a new installation. The clean backup is an installation seed, not a replacement for an existing player database or an upgrade command for an existing development stack. Keep using your existing Compose files, environment, credentials and database volumes. Do not replace them with a newly generated clean-install configuration.

The older local stack uses `.database/` for persistent credentials and administration state, and `.runtime/` for generated logs, agents and temporary files. Preserve its secrets before running preparation. If migrating from the former `database/secrets/` or `.runtime/local/secrets/` directories, copy the existing values into `.database/secrets/` without overwriting files, and keep the originals until the services are verified. An existing PostgreSQL volume must keep its matching password.

Read [Database setup](../database/README.md) for recovery and [Administration](administration.md) for operation. [Bootstrap internals](protocol/world-synchronization.md) explains the protocol templates; it is not a prerequisite for following the backup-based steps above.
