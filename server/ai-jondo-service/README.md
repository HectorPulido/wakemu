# Jondo AI backend

Independent C#/.NET 8 service using the JondoEmu turn planner with an explicit
Wakemu extension for advisory movement danger. The
existing Python AI remains available. Only TCP is enabled, on the internal Docker
network at `ai-jondo:8091`; there is no published host port.

`upstream-provenance.json` pins the upstream commit, seven unchanged source files,
and the reviewed local extension in `Core/MonsterTactics.cs` with its original and
local hashes. Run `python3 server/ai-jondo-service/verify_upstream.py` to verify
them. Native
Wakfu topology and spell semantics are supplied by compatibility adapters; this
is not the complete Dofus engine. World validates and commits every chosen action
with its existing native combat rules.

From the repository root:

```sh
docker compose -f compose.yaml -f compose.jondo.yaml build ai-jondo
docker compose -f compose.yaml -f compose.jondo.yaml up -d --no-deps --no-build ai-jondo
python3 server/tools/ai_backend.py --use jondo
python3 server/tools/ai_backend.py --status
```

Return to the previous backend without restarting World:

```sh
python3 server/tools/ai_backend.py --use current
```

The selector verifies the chosen service's framed health response before an
atomic configuration write. Selection is pinned for an entire actor turn and
changes at the next actor turn. Missing configuration selects `current`; invalid
configuration fails explicitly. Both services remain separate from World.

The adapter sends a compact current-actor snapshot and executes only the first
validated step. Continuations retain planned steps, not previous state or scores,
and are revalidated against the next authoritative snapshot. Unsupported complex
effects are advisory unknowns; native execution remains authoritative.

Focused checks:

```sh
dotnet run --project server/ai-jondo-service/Tests/JondoAI.Tests.csproj -c Release
PYTHONPATH=server/ai-service:server:server/ai-service/tests python3 -m unittest test_backend_selection
```

Native integration checks require the configured local World catalogs and
database. Their evidence and manual acceptance procedure are in
`agents_docs/reports/jondo-ai-service-20261025/README.md`.

Movement danger is a soft route cost supplied per native cell. Weighted routing
retains nondominated AP/MP/risk alternatives, so safe detours cannot hide a shorter
risky route needed to reach a target or pay a spell's MP cost. Danger influences
route, attack and reposition preferences; it never consumes real AP or MP or
makes a cell unwalkable. A melee actor can still advance through unavoidable
danger rather than waiting indefinitely. Continuations are replanned when the
advisory danger field changes.
