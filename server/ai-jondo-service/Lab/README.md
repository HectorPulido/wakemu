# WakIA tactical laboratory

The lab runs the same C# turn planner as the service, with synthetic geometry,
fighters and spells, then replays its plan in the planner's private advisory
simulation. It needs only the .NET 8 SDK: no client, World, Docker or database.
It does not prove native World rules, actual execution, or live turn latency.

```sh
dotnet run --project server/ai-jondo-service/Lab/WakIA.Lab.csproj -c Release -- --list
dotnet run --project server/ai-jondo-service/Lab/WakIA.Lab.csproj -c Release -- --repeat 5 --warmup 1
dotnet run --project server/ai-jondo-service/Lab/WakIA.Lab.csproj -c Release -- --category support
dotnet run --project server/ai-jondo-service/Lab/WakIA.Lab.csproj -c Release -- --scenario approach-and-attack
```

Each output line is JSON containing outcome checks, the first sample's actions,
and nearest-rank percentiles of planner time. Repeated samples run serially;
these numbers exclude startup, snapshot creation, serialization, networking,
queueing, native commit and client animation. Use sufficient repetitions and
the same machine, scenarios and options when comparing versions. Warmup samples
are excluded. Exit codes: 0 passed, 1 tactical expectation failed, 2 input or
execution error. A failed sample fails its scenario even if other samples pass.

Add a JSON array of scenarios under `Scenarios/`, or use `--dir PATH` for an
external scenario directory. See the existing fixtures for the format. A map
can be a line (`length`) or explicit XYZ cells and directed index-pair edges.
Each actor has an id, team, cell, HP (max HP defaults to 100), AP and MP. The
current actor defaults to id 1 (`actorId` overrides it). Spells currently cover
damage, healing and AP gain; optional `zone` and `hurtsAllies` model circular
area damage. Expectations constrain outcome totals, action count and optional
per-actor HP bounds. `actionPrefix` checks the ordered initial actions, each
with `actor`, `spell` and an optional `target` actor ID. This can assert that
an AP boost precedes an attack; it covers the private replay, not native
resource validation. Use `--budget-ms` to bound each planner search.

Run the focused assertion checks with:

```sh
python3 -m unittest discover -s server/ai-jondo-service/Lab -p test_validation.py
```

Optional `turns` lists distinct actors in execution order; nested planner replays
carry each advisory action's simulated changes into the next actor's planning.
Each actor acts at most once and can have its own `spellIds` repertoire. This
does not run native start/end-of-turn effects, resource regeneration, initiative,
or World publication, and is not an authoritative combat simulator. Follow up
with native integration when changing combat semantics.
