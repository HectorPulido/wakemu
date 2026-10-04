# Repository Guidelines

## Project Structure & Module Organization

- `server/local_game_server.py` connects the Wakfu protocol to Python services. Keep domain logic in `server/wakfu_server/`, organized into `combat/`, `items/`, `maps/`, `storage/`, and `characters/`.
- `server/tests/` contains automated tests; `server/protocol/` contains protocol catalogs. `server/ai-service/` and `server/cron-service/` provide separate services.
- `client/` contains the game client and assets; `client/tools/` contains launch and inspection scripts.
- `sniffer/` contains capture and decoding tools, with Java sources in `sniffer/java/`.
- `docs/reports/` holds investigations and evidence. `.runtime/` holds generated and private data.

## Build, Test, and Development Commands

Run from the repository root in the appropriate authorized environment. These are documented commands, not permission to start or restart services:

- `docker compose up -d --build`: build and start the Compose stack; obtain explicit authorization before restarting services.
- `docker compose ps`: inspect service status.
- `docker compose logs -f world`: follow game-server logs.
- `bash client/tools/local-client.sh`: launch the client; `--profile nombre` selects another profile.
- `bash sniffer/build-capture-agent.sh`: build the capture agent using JDK 21 or newer.
- `PYTHONPATH=server python3 -m unittest discover -s server/tests`: run server tests.

## Coding Style & Naming Conventions

Follow surrounding code: four-space Python indentation, `snake_case` functions and modules, and `PascalCase` classes. Keep protocol identifiers and binary layouts explicit. Preserve shell quoting and strict error handling. No formatter or lint configuration was found; avoid unrelated formatting changes.

## Testing Guidelines

Use `unittest`, `test_*.py` filenames, and descriptive `test_*` methods. Add regression tests for changed protocol or game behavior, including malformed packets and state transitions. No numerical coverage target is documented. Record the command and result when submitting changes.

## Commit & Pull Request Guidelines

This checkout has no available Git history, so commit conventions cannot be verified. Use concise imperative subjects. Describe behavior changes, supporting protocol evidence, related issues, and validation; include screenshots for visible client changes.

## Security & Agent Instructions

Keep credentials, captures, certificates, databases, and logs out of commits. Preserve localhost bindings and internal service networks.

For Dofus/Starloco, work remotely only: verify server, repository, and DEV branch `0.7` before editing. Report actual location, branch, commit, and push status. Promote only explicitly authorized commits to `main` or production. Never restart services without explicit authorization. Maintaining this guide locally is permitted.
