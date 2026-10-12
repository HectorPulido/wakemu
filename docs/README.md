# Wakemu wiki

Wakemu is an experimental Python server for a separately supplied Wakfu client. This wiki explains the main systems in plain English. It describes the implementation, not a promise that every game feature works or that the running Docker images contain every source change.

## Start here

| Guide | What you will learn |
| --- | --- |
| [Getting started](getting-started.md) | Client placement, prerequisites, startup, and first login. |
| [Architecture](architecture.md) | How the client, world server, workers, and database connect. |
| [Protocol and server internals](protocol/README.md) | Connections, binary layouts, request handling, and client synchronization. |
| [Combat and AI](combat-and-ai.md) | How fights, spells, states, and monster decisions work. |
| [World and ecology](world-and-ecology.md) | Maps, transport, resources, monsters, and dungeons. |
| [Characters and items](characters-and-items.md) | Progression, inventory, builds, crafting, and social systems. |
| [Administration](administration.md) | Local tools, settings, persistence, backups, and troubleshooting. |
| [Contributing](contributing.md) | Where to change code and how to verify a contribution. |
| [Limitations](limitations.md) | What remains incomplete and where help is useful. |

For a first visit, read Getting started and Architecture. To contribute, follow the relevant system guide and Contributing.

## Documentation boundaries

`docs/` is the readable wiki. `agents_docs/` holds internal protocol research, issue histories, validation evidence, and deployment reports; those records stay separate and are not required to navigate this wiki. Commands below assume the repository root. Persistent private data and service credentials belong in `.database/`. `.runtime/` is created on demand for generated files, logs, and temporary session data. The user-supplied client belongs in `client/`.
