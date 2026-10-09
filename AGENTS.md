# Repository Guidelines

## Project Structure & Module Organization

- `server/local_game_server.py` connects the Wakfu protocol to Python services. Keep domain logic in `server/wakfu_server/`, organized into `combat/`, `items/`, `maps/`, `storage/`, and `characters/`.
- `server/tests/` contains automated tests; `server/protocol/` contains protocol catalogs. `server/ai-service/` and `server/cron-service/` provide separate services.
- `client/` contains the game client and assets; `client-tools/` contains launch and inspection scripts.
- `sniffer/` contains capture and decoding tools, with Java sources in `sniffer/java/`.
- `docs/reports/` holds investigations and evidence. `.runtime/` holds generated and private data.

## Build, Test, and Development Commands

Run from the repository root in the appropriate authorized environment. These are documented commands, not permission to start or restart services:

- `docker compose up -d --build`: build and start the Compose stack; obtain explicit authorization before restarting services.
- `docker compose ps`: inspect service status.
- `docker compose logs -f world`: follow game-server logs.
- `bash client-tools/local-client.sh`: launch the client; `--profile nombre` selects another profile.
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

## Preferred delivery workflow (user instruction)

### Project scope and existing authorization

This repository is Wakfu/Wakemu, not Dofus/Starloco. The Dofus/Starloco remote-only and DEV branch `0.7` rules above do not apply here. Do not stop or block the Wakemu goal because of rules belonging to that other project. The user has explicitly authorized work in this local Wakemu checkout, Docker changes, and server restarts for the active issue-resolution goal; that authorization persists. Preserve combat and spell behavior and prioritize original issues without E.

1. Prefer automatic, general solutions across the affected system rather than handling individual maps, species, or cases separately.
2. Validate with automated tests; delegate testing to Luna when using sub-agents.
3. Prepare one general manual acceptance test with exact steps, commands and expected results.
4. Let the user review the complete result after automated verification. Request individual manual probes only to isolate a concrete failure.

Keep the issue README current. Prioritize original issues without E; E issues only as dependencies or after originals. Preserve combat and spell behavior. Existing explicit session authorization remains applicable; do not request the same authorization again.


### If you need to test something and Hector is available

Let him know if he should test anything. It could be any issue; He just want you to move faster.

Rules:
Tell him exactly what to test, step by step.
If He need something, like a command to get an object, tell him the exact command.
Exactly what should he see?
He's here for a limited time, so He recommends you let him test the things that are pending. You can progress much faster than with Luna, since Luna takes a long time to run tests, while He can do them in minutes.
He prefer testing complete systems rather than small tests.

### Contenedores de Wakemu

Trabajar sobre un único contenedor `world`: modificarlo y reiniciarlo con la autorización persistente. No crear ni acumular servidores candidatos por versión; conservar copias de seguridad y validación automática. Esta preferencia no exige fusionar servicios distintos como PostgreSQL o IA en un único proceso.


### Complete world builds

Before restarting world, build and validate the complete current server checkout. Do not deploy an overlay on an older image that drops concurrent agents' spell or combat changes. Verify that the deployed image contains the current shared implementation and preserve changes owned by other agents.

### Idioma
Codigo y comentarios en ingles, Documentacion en ingles, conversacion con Hector en español
Aunque lo que ya este en español, puede estar en español, no traduzcas un archivo existente a menos que te lo indiquen
