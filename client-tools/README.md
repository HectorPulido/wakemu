# Client tools

Project-owned launchers, diagnostics, Java agents and patches. The official game client and its assets are not distributed.

## Setup

Supply Wakfu **1.93.1+79** in the sibling `../client/` directory. Its `config.properties`, `classpath`, `contents/`, `lib/` and `jre/` must be directly inside that directory. The local tools require macOS (`sandbox-exec`), Python 3 with Tk support for account dialogs, a JDK 21 or newer, and the local server services.

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

All command arguments are forwarded to the underlying tool. The direct `local-client.sh` and `local-launcher.py` entry points remain available. The root `launcher.sh` also opens the graphical launcher.

## Layout

```text
client-tools/
├── client.sh               # Common command entry point
├── local-client.sh         # Local launch/build orchestration
├── local-launcher.py       # Graphical account launcher
├── runtime/                # Login, launcher bridge, profile preparation and network guards
├── diagnostics/            # Inspector, mouse input, combat observations and capture helpers
├── java/                   # Agent sources, tests and native catalog probes
├── packaging/              # Portable launcher builder
├── dropin/                 # Portable launcher source/template
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

Game resources stay in `client/`. Isolated configuration, credentials, profiles, logs, compiled agents, packages and original patch backups stay in `.runtime/`. Both directories are ignored by Git. Never add game assets, patched archives, tokens or generated captures to `client-tools/`.

The particle patch validates the native script before editing the user-supplied `scripts.jar`, keeps the original in `.runtime/client-patches/`, and is safe to repeat. Restart the game client after applying it. An unknown archive layout is rejected without mutation.

The portable package contains explicitly selected project files and generated agents only; its configurable installation directory refers to a separately supplied game client. See `dropin/README.txt`.

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
Server-specific profiles stay under `.runtime/client-servers/`. Direct
connections do not use SSH. The server must expose its configured ports and advertise
a world address reachable from your machine. The native client uses IPv4.
For custom ports, `--config PATH` accepts `server_host`, `api_url`,
`dispatch_port`, `game_ports`, `chat_port`, and `http_port` in JSON.
