# WakIA host scenario runner

This runner executes the actual C# `PlanningGate` and `Planner.Decide` against
prepared advisory protocol-1 requests. It tests host policy, action selection,
rejection alternatives and input handling without World, a client, Docker or a
database. The adjacent `Lab` tests multi-action plans and private replay; this
runner checks the host's first offered action. Neither tool verifies native
World commit, fight state changes, packets or client ACKs.

```sh
dotnet run --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --list
dotnet run --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --repeat 2
dotnet run --no-build --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --category coordination
dotnet run --no-build --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --scenario host-blocked-sight
python3 -m unittest discover -s server/ai-jondo-service/HostLab -p test_validation.py
```

The `native-linear-path-*` scenarios adapt the map 363 / spell 5777 C#
regression fixture into HostLab requests. They check confirmed blocked proof,
missing proof, rule override and movement to a different source. They use
prepared advisory facts; they do not recompute map geometry or execute a cast.

The following scenarios use published geometry from real maps 527 and 1134.
Their actors and resources are synthetic; the two map 527 arrangements are
reconstructed positions, not historical fight snapshots. Their movement
permissions were produced by the native bridge, not manually added:

```sh
dotnet run --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --scenario map527-fight455-reconstructed-native-snapshot
dotnet run --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --scenario map527-fight456-reconstructed-native-snapshot
dotnet run --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --scenario map1134-synthetic-native-snapshot
```

These saved requests run offline: they need neither World, a client, Docker nor
a database. To generate and validate another synthetic map fixture, copy and
edit `NativeFixtures/map1134.json`, then run:

```sh
mkdir -p /tmp/wakia-map-exports
server/tools/wakia-map527-probe.sh --fixture /path/to/synthetic-fixture.json --export-dir /tmp/wakia-map-exports
dotnet run --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --request /tmp/wakia-map-exports/wakia-map-custom.json
```

The generator accepts a published `mapId`, exactly two player positions and
three monster positions as XYZ integer arrays, and optional `playerLevel`,
`monsterLevel` and `actorMp`. It creates synthetic characters and monster
reference 1; it does not accept character names, account data, inventories or
other personal information. The example file contains a complete input. The
export directory must exist and the output file must not already exist.

Generation and native movement validation use a separate process in the
running local World container, the existing published catalog and a read-only
database connection. They do not require a client, read player logs, or publish
a fight. The tool also calls the checkout Host and validates its movement on the
same private fight. A non-movement custom action is checked with a private
native preview. HostLab alone does not validate native movement or commit.

With explicit authorization to use a local character, the following separate
probe reads that character's current active build, inventory and stats, then
runs both sides under WakIA in a new private fight against a monster. It uses
the monster's level from the character by default; `--monster-level` overrides
it. Quote names containing spaces:

```sh
server/tools/wakia-real-character-private-probe.sh --character 'CHARACTER NAME' --monster-level 200 --timeout 180
```

This probe requires the running local World container and its database for
read-only character and published catalog access, but no game client. It does
not publish the synthetic fight or change the character. The checkout C# host
runs in a separate local process; temporary request files are private and
removed after the run. Do not copy their contents into public fixtures or logs.
The summary includes source and initialized HP separately: native fight-start
effects may change resources. It reports a failure if the fight does not reach
a terminal state within 50 turns. The global timeout defaults to 180 seconds
and accepts 1–3600 seconds, starting after the remote temporary directory has
been created. Timeout or interruption stops the identified private worker and
removes temporary files. If interruption occurs while the worker is starting,
before its identity is registered, cleanup waits up to two seconds for that
identity; a worker stalled before registration may outlive this window. A
manual interruption while Docker is creating the remote temporary directory can
also leave that directory behind before its path is returned to the wrapper. A
private terminal state does not test
rewards, durable return to the world, or client behavior.

Each JSON output row reports the result, any failures, first action and the
minimum and maximum elapsed time at the gate. These times exclude the Python
snapshot, transport, World commit and client; they are not full-turn latency.
See `../Benchmarks/README.md` for controlled timing and percentile comparisons.
Exit status is 0 when all expectations pass, 1 on a scenario failure, and 2
for malformed input or runner errors. In scenario mode every repetition
invalidates cached turn continuations.

To test a continuation across supplied authoritative snapshots in one process:

```sh
dotnet run --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --sequence server/ai-jondo-service/HostLab/Sequences/resource-revalidation.json
```

Each sequence entry supplies `request` and nonempty `expect` fields. Supported
expectations are `type`, `spellId`, `planReused` and `pathFirst` (the first XYZ
movement cell); the cache is cleared before
and after the complete sequence, not between its steps. The supplied case checks
that a planned cast is discarded when the next snapshot has insufficient MP.
The snapshots represent externally supplied state; the runner does not execute
the actions, commit them in World or regenerate resources between turns. Exit 0
means all step assertions passed, 1 means an assertion failed, and 2 means the
input or runner failed. Sequence outputs are not the scenario-batch format.

`Sequences/hazard-revalidation.json` adapts the C# hazard regression into a
three-request sequence: equivalent danger entries reuse a plan, while a changed
danger value invalidates it and selects a different first path cell. The danger
facts are synthetic advisory inputs; this does not exercise native trap effects.

To compare a complete batch with a previously saved HostLab JSON-lines result:

```sh
if dotnet run --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- > /private/current.jsonl; then
    python3 server/tools/wakia_compare_hostlab.py /private/baseline.jsonl /private/current.jsonl
else
    printf '%s\n' 'HostLab failed; current results may be incomplete.' >&2
    false
fi
```

The comparator reports missing/new scenarios, changed pass status or changed
first action, and any current failures. Exit 0 means no differences or current
failures; exit 1 means changes or failures; exit 2 means invalid input. It ignores
timing, sample counts and other diagnostics. A changed action needs review and
is not necessarily a regression; the comparison also cannot identify a changed
later repetition or certify gameplay. Compare equivalent scenario sets, options
and budgets. Exit 0 compares only the rows supplied: it cannot detect two equally
truncated batches. Check HostLab's successful exit and the expected scenario
coverage for both files. Keep result files private when using private scenarios.

To inspect an authorized, private real advisory protocol request directly,
without first wrapping it as a scenario or predicting its answer:

```sh
dotnet run --no-build --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --request /path/to/request.json --repeat 2
```

The file must contain the protocol request object itself. Each output line
contains the status, full response and gate time; status 200 exits 0, a rejected
request exits 1 and invalid runner input exits 2. This is inspection, not an
assertion that the chosen action is correct. The output may contain identifiers
from the request, so keep requests and output private. The initial build is
required before `--no-build` can use a newly changed runner.

The comparator above also accepts two `--request` JSON-lines outputs, matching
each repetition by `sample` and comparing its status and action. Use the exact
same request and repeat count for both runs; it does not verify request identity,
inspect diagnostics, or establish which decision is better. It rejects mixing
request and scenario outputs. A non-200 current sample fails the comparison.

Add an array to `Scenarios/*.json` or specify `--dir PATH`. Each case contains a
unique `name`, a `category`, the full `request` protocol object, and `expect`:

- `status` defaults to 200; use it to assert invalid input is rejected.
- `types` lists acceptable action types. Optional `spellId` and `targetId`
  constrain a cast, and `diagnosticContains` checks an advisory diagnostic.
- `targetCell` asserts the exact XYZ cast destination. `targetIdAbsent: true`
  requires a null or absent target actor, allowing empty-cell area targeting
  to be checked; it cannot be combined with `targetId`.
- Expectations must not be empty and unknown field names are rejected, so a
  typo cannot silently turn an assertion into a passing scenario.
- `pathExcludes` optionally lists XYZ cells that a proposed movement path must
  not cross. It is an assertion about a test case, not a game rule.
- `pathEndsAt` optionally asserts the XYZ destination of the movement path.
- Source identity is checked for every successful response; planning must not
  mutate the request.

Fixtures shipped here are synthetic. For a real-world case, use an authorized
advisory request and supply its expected result; do not commit private player
data or captures. Validate actual legality and effects separately using the
native World tests.

To extract a request from an existing local protocol capture for private replay:

```sh
python3 server/tools/wakia_extract_request.py --input /private/capture.json --output /private/request.json --index 0
dotnet run --project server/ai-jondo-service/HostLab/WakIA.HostLab.csproj -c Release -- --request /private/request.json
```

The input may be a protocol-1 request, an object containing `request`, or an
array of such objects; `--index` selects a zero-based array entry. The output
is created with mode 0600 and never overwrites an existing file. The tool
preserves the request fields and identifiers; it does not sanitize, anonymize,
capture live traffic, or guarantee that a planner chooses the same action on a
different version. Both files and the HostLab output can contain sensitive
gameplay information: keep them private and do not commit or share them.

When a native reproduction nests the request, select it explicitly with a JSON
Pointer, for example `--path /result/firstRequest`. Array positions may appear
in the pointer; `~1` represents `/` and `~0` represents `~`. An invalid pointer
fails without creating the output or printing the captured request.

