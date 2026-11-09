# WakIA tactical AI

WakIA is an independent C#/.NET 8 service using the JondoEmu turn planner with an explicit
Wakemu extension for advisory movement danger. Only TCP is enabled, on the internal Docker
network at `wakia:8091` (`ai-jondo` remains a compatibility alias); there is no published host port.

`upstream-provenance.json` records the upstream commit, source files and local
adaptations. Run `python3 server/ai-jondo-service/verify_upstream.py` to verify
the recorded hashes. Native
Wakfu topology and spell semantics are supplied by compatibility adapters; this
is not the complete Dofus engine. World validates and commits every chosen action
with its existing native combat rules.

From the repository root:

```sh
docker compose build wakia
docker compose up -d --no-deps --no-build wakia
python3 server/tools/ai_backend.py --use wakia
python3 server/tools/ai_backend.py --status
```

`WAKIA_IMAGE` selects the C# image; the previous `WAKFU_JONDO_AI_IMAGE` name
remains a fallback when `WAKIA_IMAGE` is unset.

The selector verifies the chosen service's framed health response before an
atomic configuration write. Selection is pinned for an entire actor turn and
changes at the next actor turn. Missing configuration selects WakIA; invalid
configuration fails explicitly. WakIA runs separately from World.
The legacy name `jondo` remains accepted by the selector and stored internally
for compatibility with existing configurations and pinned turns. The selector
is included in World at `wakfu_server/wakia_bridge/ai_backend.py`.

The adapter sends a compact current-actor snapshot and executes only the first
validated step. Continuations retain planned steps, not previous state or scores,
and are revalidated against the next authoritative snapshot. Unsupported complex
effects are advisory unknowns; native execution remains authoritative.

The standalone [tactical laboratory](Lab/README.md) runs reproducible planner
scenarios without World or the client. The [host laboratory](HostLab/README.md)
exercises protocol requests and first-action selection. The
[planner benchmark](Benchmarks/README.md) measures planning and queueing
separately from native execution.

For a local native integration check, run from the repository root:

```sh
sh server/tools/wakia-native-probe.sh
sh server/tools/wakia-native-probe.sh dispatch
sh server/tools/wakia-native-probe.sh shared
```

This creates a short-lived planner from the prepared WakIA image and uses the
running local World container as a separate process environment. The encounter
exists only in memory; PostgreSQL access is read-only and Redis writes are
blocked. The tool uses the running World's engine and the bridge from the
current source tree, so it does not certify an unactivated World image. It does
not launch the client or verify client animations. The local World, PostgreSQL,
Redis, and the prepared WakIA image must already be available.

The `dispatch` option uses the running local WakIA service and tests the
non-shared World dispatcher with a synthetic in-memory Store.
It does not test shared-fight publication or a real client's acknowledgement.

The `shared` option uses the running WakIA service with an isolated in-memory
shared Registry and one synthetic participant. It checks native move, cast,
damage, turn end, publication of packet batches and arming the ACK barrier.
It calls the shared-turn function and real planner
directly, using the bridge from the source tree. It does not test the live
session's lease, dispatcher, participant connection or an actual client ACK.

To exercise summon projection through two native turn boundaries and the C#
planner, run:

```sh
sh server/tools/wakia-summon-probe.sh
```

This requires the .NET 8 SDK, local Docker Compose, the running local World,
PostgreSQL and Redis, and World's native catalog. It runs a separate process
inside the existing World container; it does not restart World or require a
running WakIA service. A synthetic in-memory encounter uses the installed
engine to create native summon 3786, build its snapshot, advance its turn and
build a snapshot for its summoner. The current source bridge supplies the spell projections; the
current C# source is built locally and consumes that snapshot. PostgreSQL is
read-only, Redis writes are blocked, and temporary files are removed afterward.
Redis permission warnings are expected when the catalog tries to populate its
cache. Success prints that the Host accepted the native summon snapshot and
the action it proposed; a nonzero exit indicates failure.

This verifies that the previously projected 5228 estimate reaches the C#
planner. It does not prove that the estimate changed its action, validate an
eventual summon attack, or test shared combat publication or a client.

Focused checks:

```sh
dotnet run --project server/ai-jondo-service/Tests/JondoAI.Tests.csproj -c Release
PYTHONPATH=server python3 -m unittest server.tests.test_wakia_selector_cli server.tests.test_wakia_dispatch_safety server.tests.test_wakia_reproduction_sdk_selection
```

The general-effects checks run against the current engine and the committed
native JSON fixtures. Comparisons with the historical 89179 binary are reported
as skipped when the binary is unavailable. To include them, supply the path to
the original assembly explicitly:

```sh
WAKIA_LEGACY_CONSUMER_DLL=/path/to/original/JondoAI.dll dotnet run --project server/ai-jondo-service/Tests/JondoAI.Tests.csproj -c Release -- --general-effects-only
```

Supplying an invalid path fails the check. The old binary is not a runtime
dependency of WakIA.

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
