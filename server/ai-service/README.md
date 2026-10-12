# Wakemu tactical AI service

A deterministic planner based on archetypes and capabilities. It receives the
complete fight context and requests previews from the native engine; world
retains combat authority. No species-specific rules, Laya, or invented effects.

## Structure

```text
ai-service/
├── wakfu_ai/                 # Service implementation and SDK used by world
│   ├── bridge/               # Combat entry, transport, and world coordination
│   ├── context/              # Graph, serialization, caches, and complete catalog
│   ├── http/                 # HTTP endpoints and server limits
│   ├── native/               # Oracle, turn execution, profiles, and statistics
│   └── planning/             # Search, scoring, capabilities, threats, and coordination
├── tests/                    # SDK, HTTP, and integration contract tests
├── scripts/                  # Provisioning, acceptance, and preparation tools
├── benchmarks/               # Fixtures and reproducible measurements
│   └── results/              # Preserved historical results
├── tools/java/               # Protocol and serialization probes
├── Dockerfile
├── rebuild.sh                # Rebuilds/restarts AI and provisions the catalog
├── server.py                 # Compatibility entry for consumers loading this file
├── planner.py                # Planner compatibility entry
├── world_loader.py           # Stable, versioned loader used by world
├── world_entry.py            # Stable entry delegated to wakfu_ai.bridge
└── prepare_catalog_cache.py  # Stable catalog provisioning entry used by world
```

Internal modules use relative package imports. This preserves the private
namespace and the SDK version loaded by world without duplicating logic
between compatibility entries and implementation. Tests import the real
package and live outside production code. Do not add new modules at the root.

## Run

From this directory, with database configuration and dependencies available:

```sh
python3 -m wakfu_ai
```

Configuration: `WAKFU_AI_BIND` (default `0.0.0.0`), `WAKFU_AI_PORT` (`8090`),
and `WAKFU_AI_CONTEXT_ROOT` (`/tmp/wakfu-ai-context`). The complete turn keeps
its 10-second budget and 0.25 search fraction. Preparation neither trims data
nor resets the actual turn deadline.

Concurrency: `WAKFU_AI_MAX_DECISIONS` defaults to **16 active searches**
(range 1–64); `WAKFU_AI_MAX_CONNECTIONS` defaults to **64 HTTP connections/threads**
(range 1–128, at least as many as searches). The session registry uses the same
search limit. `/health` exposes both limits. Increasing them allows more
simultaneous fights; it does not turn a Python search into parallel CPU work
or extend its 10-second budget.

From the repository root, rebuild the single AI service:

```sh
sh server/ai-service/rebuild.sh
```

This command rebuilds and restarts AI using the live world image as its engine
source, then provisions the complete catalog. It does not restart world or
modify source outside `server/ai-service`. The Dockerfile retains `COPY . /app`
and copies the authoritative engine from the selected world image. The
experimental fragmented format remains disabled.

## Validate

Historical reorganization verification: **459 passing tests** against frozen
engine `3af10843cbc6`, 169 native imports and no external imports; 104 packaged
Python files matched source SHA hashes. Only AI was rebuilt and restarted in
that verification; world kept running. These are historical results, not a
claim that the current checkout has just passed the same gate.

From the repository root, using an environment with the dependencies from
`server/requirements.txt` installed:

```sh
PYTHONPATH=server:server/ai-service python3 -m unittest discover -s server/ai-service/tests -p 'test_*.py'
PYTHONPATH=server:server/ai-service:server/tests python3 -m unittest test_ai_service test_combat_tactical_ai test_combat_ai_policy
```

When comparing images, freeze the engine and load only its modules. Each run's
evidence should identify the image and verify imports. Private benchmarks do
not establish client animation acceptance.

Example native benchmark inside a running world container:

```sh
docker exec -e PYTHONPATH=/app:/app/ai-service:/app/tests wakfu-local-world-1 python3 -m benchmarks.benchmark_native_concurrent --url http://ai:8090 --concurrency 1 2 4 --repeats 2 --budget 10 --cold-catalog --npc-position -5 -7 -1 --output /data/e18-native-concurrent.json
```

World preparation retains the stable entry
`/app/ai-service/prepare_catalog_cache.py`. Other tools run as modules of
`scripts` or `benchmarks`, with this directory on `PYTHONPATH`.

## Documentation

- [Combat and AI overview](../../docs/combat-and-ai.md).
- [Combat synchronization](../../docs/protocol/combat-synchronization.md).
- [Architecture and service responsibilities](../../docs/architecture.md).
- [Testing and contributions](../../docs/contributing.md).

Detailed historical investigations remain in `agents_docs/`, outside the public
wiki. The former service-local documentation directory is no longer present.

## Walking without executable attacks

The native repertoire includes a state-bound prerequisite certificate for NPC
abilities blocked by missing positive-level casting tables or required casting
root metadata. The planner removes only explicitly certified unavailable
spell keys. Unknown abilities, PC casting sources, level-zero tables and
stale or unfamiliar certificates retain ordinary native queries. The complete
repertoire, catalogue and arena are preserved.

When every owned ability is certified unavailable, or the native repertoire
is empty, `policy.movementOnlySearchMs` caps additional position exploration
at 100 ms by default (accepted range: 1–10,000). The first action still needs
native certification, and the absolute turn deadline and commit reserve stay
in force. This is an exploration allowance, not a total turn latency promise.

Shared turns reuse the fully transferred immutable catalogue manifest across
fresh action sessions. The scope ends with that turn and is isolated by fight,
exporter and service URL; every action still captures its complete runtime and
checks its source. Each certified batch is published before replanning, through
the shared Registry sequence and the existing real client ACK barrier.
