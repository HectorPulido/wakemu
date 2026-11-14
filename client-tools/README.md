# Client tools

Project-owned launchers, diagnostics, Java agents and patches. The official game client and its assets are not distributed.

## Setup

Supply Wakfu **1.93.1+79** in the sibling `../client/` directory. Its `config.properties`, `classpath`, `contents/`, `lib/` and `jre/` must be directly inside that directory. The integrated launcher supports macOS 13+, Windows 10/11 x64, and graphical Linux desktops through the same Python/Qt interface. It requires Python 3.10–3.14, a JDK 21 or newer to prepare agents, and the selected server services. GUI dependencies are installed into a private virtual environment on first launch. Linux uses the extracted `client/jre/bin/java` runtime.

**Client compatibility:** **1.93.1+79** is fully compatible with the features implemented by Wakemu. **1.93.1+81** has partial, unverified compatibility. Automated launcher and protocol checks do not establish complete gameplay compatibility; version-specific planting and dungeon agents and changed native content remain unverified with +81. Use +79 for the supported experience.

From the repository root:

```sh
bash client-tools/client.sh check
bash client-tools/client.sh launch
```

`check` compiles the agents and validates network isolation without opening the game. `launch` opens the account launcher.

## Common commands

| Command | Purpose |
| --- | --- |
| `bash client-tools/client.sh play` | Start the local client, requesting login when needed |
| `bash client-tools/client.sh play --profile second-player` | Start an isolated second profile |
| `bash client-tools/client.sh inspect --profile main state` | Read a running client's inspector state |
| `bash client-tools/client.sh package` | Build the portable launcher under `.runtime/distribution/` |
| `bash client-tools/client.sh patch-particles` | Apply the optional empty particle ID patch to the supplied client |
| `bash client-tools/client.sh --help` | Show available commands |

All launch entry points use the integrated launcher: `python3 client-tools/desktop-launcher.py`, `bash launcher.sh`, and `bash client-tools/client.sh launch` or `play`. Windows can use `py -3 client-tools/desktop-launcher.py`. There is no Tk fallback or separate platform-specific launcher UI.

The launcher includes saved servers and accounts, secure password storage, registration, connection checks, and an embedded achievements and dungeon page. Its interface and local messages are in English; embedded pages use the language provided by the selected server. Repository launches initially select localhost and detect the repository's `client/` installation. The Internet preset remains available in the server selector. `--server` and `--config` select the requested configuration without importing credentials from another launcher folder.

The first launch prepares the agents and installs the shared Qt/PySide dependencies into `.local-state/wakemu/launcher-venv/`; subsequent launches reuse them. macOS requires Xcode Command Line Tools only for the small Keychain helper. Linux needs Qt WebEngine system libraries and an unlocked Secret Service to save passwords; signing in without remembering credentials remains available. Use `bash launcher.sh --prepare-only` to prepare without opening a window. Private launcher state lives under `.local-state/wakemu/desktop-launcher/`.

Export the shared source package for macOS, Windows and Linux:

```sh
python3 client-tools/desktop-launcher.py --package
```

The archive `.runtime/distribution/Wakemu-Launcher.zip` contains the same launcher and agents for all three systems. Open `Launch.command` (Mac), `Launch.bat` (Windows), or `bash Launch.sh` (Linux). Python is required; GUI dependencies are installed privately on first run. No saved accounts, machine-specific client paths, or official client assets are included. See [Getting started](../docs/getting-started.md#5-optional-install-and-launch-the-client) for platform requirements and complete setup.

## Layout

```text
client-tools/
├── client.sh               # Common command entry point
├── local-client.sh         # Local launch/build orchestration
├── desktop-launcher.py     # Shared launcher bootstrap and cross-platform source packaging
├── mini-launcher-desktop/  # Shared Qt interface and account backend
├── runtime/                # Login, launcher bridge, profile preparation and network guards
├── diagnostics/            # Inspector, mouse input, combat observations and capture helpers
├── java/                   # Agent sources, tests and native catalog probes
├── packaging/              # Internal Java agent builder
├── dropin/                 # Low-level runner and network guard sources
└── patches/                # Optional patch utilities; no game archives
```

The local and portable bridges have different installation and authentication requirements and are kept separate.

## Diagnostics

```sh
python3 client-tools/diagnostics/check-combat-gui.py --help
python3 client-tools/diagnostics/inspect-client.py --profile main state
```

Combat observation requires an existing legitimate fight and capture/inspector data. `click-client.py` is an advanced single-client helper; it builds its UI attach agent from `sniffer/java/` before use and discovers the installed JDK. It is not part of normal launch. Native Java probes are developer utilities, not runtime dependencies.

## Private files and patches

Game resources stay in `client/`. Private launcher state, session tokens, profiles and logs stay in `.local-state/wakemu/desktop-launcher/`. GUI dependencies stay in `.local-state/wakemu/launcher-venv/`. Generated developer agents, packages and original patch backups stay in `.runtime/`. Persistent server credentials and administration state belong in `.database/`. These private and generated directories are ignored by Git. Never add game assets, patched archives, tokens or generated captures to `client-tools/`.

The particle patch validates the native script before editing the user-supplied `scripts.jar`, keeps the original in `.runtime/client-patches/`, and is safe to repeat. Restart the game client after applying it. An unknown archive layout is rejected without mutation.

The shared package contains explicitly selected launcher source files and generated agents only; its configurable installation directory refers to a separately supplied game client. See `mini-launcher-desktop/README.txt`.

## Choose a private server

Copy `.env.example` to `.env` in this directory and edit `WAKFU_SERVER`
(IP address or DNS hostname) and `WAKFU_API_URL` (HTTP or HTTPS login API on
that same server). Use plain values without shell quotes. Then run:

```bash
bash client-tools/client.sh launch
```

Override the file for one launch:

```bash
bash client-tools/client.sh launch --server game.example.org
bash client-tools/client.sh check --server 192.168.1.20
```

`--server` defaults the login API to `http://HOST:18081`; add `--api-url`
to override it. With no configuration, the existing localhost setup is used.
Launcher accounts and their runtime directories stay under `.local-state/wakemu/desktop-launcher/`. Explicit configuration files stay under `.local-state/wakemu/client-servers/`. Direct
connections do not use SSH. The server must expose its configured ports and advertise
a world address reachable from your machine. The native client uses IPv4.
For custom ports, `--config PATH` accepts `server_host`, `api_url`,
`dispatch_port`, `game_ports`, `chat_host`, `chat_port`, `http_url`, `shop_url`, `achievements_url`, `install_root`, and `certificate` in JSON.

### Linux client launch

Use the shared launcher from a graphical desktop session:

```sh
python3 client-tools/desktop-launcher.py
```

Qt needs the system libraries listed in [Getting started](../docs/getting-started.md#5-optional-install-and-launch-the-client). The game itself uses its extracted `client/jre/bin/java` and requires X11/XWayland `DISPLAY` access. Over SSH, preserve the existing desktop session credentials; setting `DISPLAY` alone does not grant access to its X server. An unlocked Secret Service keyring enables credential saving; otherwise leave saving disabled.

Advanced diagnostics can still run `bash client-tools/client.sh check` to build and verify the Java network guard without opening the game. `local-client.sh` no longer opens a separate account dialog: a launch without a supplied session goes through the shared launcher. Game logs appear in the selected account's runtime directory under `logs/client-console.log`.

Linux isolation currently uses the mandatory Java network guard: it rejects
external Java DNS/socket destinations and limits connections to the configured
server ports and loopback. There is no OS network sandbox on Linux in this
launcher. The Python launcher bridge and native libraries are therefore outside
the Java guard. Both launch and check print this difference explicitly. macOS
continues using its OS sandbox in addition to the Java guard.
