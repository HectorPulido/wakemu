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

The game server does not need Java, Qt, or game assets. Install these desktop requirements only on the machine that runs the client.

The integrated launcher uses the same Python/Qt application on **macOS, Windows, and Linux**. The previous Tk launcher and separate Mac/Windows interfaces have been removed. Requirements:

- Python **3.10–3.14**, with `venv` and `pip`, and Internet access for the first launcher dependency installation.
- **macOS 13+**, **Windows 10/11 x64**, or a graphical **Linux** desktop. Linux needs the Qt WebEngine system libraries; Debian/Ubuntu may require `libegl1`, `libopengl0`, `libnss3`, `libxkbcommon0`, `libxcb-cursor0`, `libopus0`, GLib, and their platform dependencies. Qt WebEngine may also require the distribution's WebP, Snappy, Minizip, LCMS, and audio libraries. Package names vary between distributions. See the [Qt for Python requirements](https://doc.qt.io/qtforpython-6/gettingstarted.html).
- A **JDK 21+** to build the repository's launcher agents. Set `JAVA_HOME` on Windows, or make `javac` available on `PATH`.
- On macOS, **Xcode Command Line Tools** to build the small Keychain helper. The interface itself is shared Python code.
- Your own legally obtained **Wakfu 1.93.1+79** installation for full client compatibility with the features implemented by Wakemu. **1.93.1+81** has partial, unverified compatibility; use +79 for the supported experience. Other versions are unsupported.

Put the client files directly inside `client/`, or select an existing installation under **Advanced settings → Client folder**:

```text
client/
  config.properties
  classpath
  contents/
  lib/
  jre/
```

From the repository root, run the same entry point on every platform:

```sh
python3 client-tools/desktop-launcher.py
```

On Windows, use `py -3 client-tools/desktop-launcher.py`. On macOS and Linux, `bash launcher.sh` and `bash client-tools/client.sh launch` are equivalent shortcuts. The `play` command opens this same launcher.

The first launch prepares the agents and installs the pinned Qt/PySide dependencies into `.local-state/wakemu/launcher-venv/`; it does not install Python packages globally. Later launches reuse unchanged dependencies and agents. Use `python3 client-tools/desktop-launcher.py --prepare-only` to prepare everything without opening a window.

Repository launches initially select **Wakemu Local**, with the repository client folder already configured. Choose another saved server, or use **Advanced settings** for its addresses and ports. **Check connection** reports configured service reachability. **Detect configuration** uses the existing public server's configuration endpoint; local HTTP presets retain their configured addresses and ports. A remote server must already be reachable: changing the launcher does not expose localhost-only services.

Enter your native account on the selected private server and press **Play**, or use **Register** to create a separate player account. Use this server's credentials rather than your official game account. Registration is submitted only by **Create account**; canceling leaves the previous account unchanged.

**Save account and password** uses macOS Keychain, Windows DPAPI, or Linux Secret Service. Linux requires an unlocked compatible keyring, such as GNOME Keyring or KWallet. When secure storage is unavailable, leave password saving disabled; passwords are never saved in plaintext. Existing player data is unchanged, and credentials from other launcher folders are not imported. **Forget saved sign-in** removes the selected account's saved credentials.

The **Achievements and dungeons** tab opens the selected server's existing authenticated portal. This requires that server's `/launcher/login` gateway; local World alone does not provide it. The web page uses the language provided by that server and has no access to the launcher's native account controls. Switching accounts or servers clears the embedded web session. Closing the launcher leaves the game running.

For a second isolated launcher profile:

```sh
python3 client-tools/desktop-launcher.py --profile second-player
```

Launcher state and account-specific runtime files live under `.local-state/wakemu/desktop-launcher/`; additional profiles live under its `instances/` directory. Keep these private files when updating the launcher.

For explicit server configuration, the shell shortcut accepts `--server` or `--config`:

```sh
bash client-tools/client.sh launch --server 192.0.2.20
bash client-tools/client.sh launch --config /path/to/server.json
```

On Windows, select the server in the launcher, or set `WAKFU_LAUNCHER_CONFIG` to the configuration file before running the Python entry point. Read [Choose a private server](../client-tools/README.md#choose-a-private-server) for service ports and configuration files.

To export the same launcher source for all three systems:

```sh
python3 client-tools/desktop-launcher.py --package
```

This creates `.runtime/distribution/Wakemu-Launcher.zip`. Extract it and use `Launch.command` on macOS, `Launch.bat` on Windows, or `bash Launch.sh` on Linux. Python is required; the first run installs the platform's GUI dependencies in a private environment. macOS builds the Keychain helper locally. The package includes the compiled agents but excludes saved profiles, accounts, and official client assets. It is a shared source package, not a prebuilt executable for every operating system.

## Existing installations

The steps above are for a new installation. The clean backup is an installation seed, not a replacement for an existing player database or an upgrade command for an existing development stack. Keep using your existing Compose files, environment, credentials and database volumes. Do not replace them with a newly generated clean-install configuration.

The older local stack uses `.database/` for persistent credentials and administration state, and `.runtime/` for generated logs, agents and temporary files. Preserve its secrets before running preparation. If migrating from the former `database/secrets/` or `.runtime/local/secrets/` directories, copy the existing values into `.database/secrets/` without overwriting files, and keep the originals until the services are verified. An existing PostgreSQL volume must keep its matching password.

Read [Database setup](../database/README.md) for recovery and [Administration](administration.md) for operation. [Bootstrap internals](protocol/world-synchronization.md) explains the protocol templates; it is not a prerequisite for following the backup-based steps above.
