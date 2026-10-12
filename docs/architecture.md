# Architecture

[Wiki home](README.md) · Related: [Administration](administration.md)

## The main path

The supplied client connects to Wakemu through project-written launch and compatibility tools. The world server receives binary game messages, validates requests, changes game state, and sends the responses the client expects.

`server/local_game_server.py` connects protocol handling to the domain modules in `server/wakfu_server/`. Combat, maps, items, characters, and storage are separated by responsibility. Those folders also extend the Python package search path, so an import such as `wakfu_server.native_catalog` can refer to a module in `storage/`.

## Services

| Service | Responsibility |
| --- | --- |
| `world` | Game connections, sessions, authoritative gameplay, and the local login API. |
| `postgres` | Durable accounts, characters, catalogs, settings, and gameplay records. |
| `redis` | Versioned catalog caching and the movement position journal. |
| `ai` | Tactical planning using the combat engine's legal action previews. |
| `ecology` | Background planning for resource, population, and weather changes. |
| `cron` | Scheduled background work through the world scheduler interface. |
| `shop` | Local shop catalog and its web interface. |
| `admin` | Browser-based administration. |
| `admin-control` | Authenticated service lifecycle operations for the admin panel. |

The optional profiler is configured separately. Compose publishes local endpoints on loopback by default and keeps worker communication on internal networks.

## Who owns the truth?

World decides whether gameplay actions can commit. AI proposes actions; ecology prepares changes that world validates before applying. Neither worker can bypass the relevant gameplay checks.

For the transport and message-level view, read [Protocol and server internals](protocol/README.md).

PostgreSQL owns durable data. Catalogs are published as complete revisions, and processes pin their catalog revision to avoid mixing incompatible definitions. Redis accelerates reads; it is not an alternative source for missing catalogs.

Movement is buffered and journaled with session ownership checks, then written to PostgreSQL in batches and at lifecycle boundaries. This avoids a database write for every step while preventing an old connection from overwriting a newer character session.
