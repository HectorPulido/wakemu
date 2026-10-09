# Dungeon runtime integration

The reviewed composition JSON is compiled automatically by
`wakfu_server.maps.dungeon_catalog`. It generates immutable room rosters and a
reproducible draft import plan, preserving source and document hashes. All 87
reviewed guide documents and 221 recorded rooms are consumed together. The
initial native-reference mapping gives 12 fully resolved dungeon rosters.

Run from the repository root:

```sh
PYTHONPATH=server python3 -m wakfu_server.maps.dungeon_catalog \
  --compositions .runtime/local/methodwakfu-dungeons/composition-catalog.json \
  --native-monsters server/protocol/monsters.json \
  --output .runtime/local/methodwakfu-dungeons/compiled-import-plan.json
```

Unknown counts, unresolved references, missing native level ranges, incomplete
compositions, unreviewed extraction, version mismatches and discontinuous room
orders are explicit readiness diagnostics. Native level ranges are retained
separately from guide ranges; an absent guide level does not prevent a native
roster compiling. Native zero-level placeholders remain unknown. The compiler
never chooses grades, resolves ambiguous names, or fabricates coordinates.

## Existing implementation

`dungeon_instances.py` owns durable party sessions, membership authorization and
atomic party relocation intent. Migration 069 stores per-member transition
outbox delivery keyed by session generation and transition revision. Delivery
acknowledgement is not a combat victory or room-completion event.

`dungeon_context.py` and migration 070 freeze a configured native context policy
version per instance. The fight-in-progress flag must be supplied from actual
runtime state. This policy is not an encounter catalog.

## Remaining general integration

A compiled roster is not yet an activated dungeon. Every import record lists
these runtime prerequisites:

- Native asset-map identity must remain distinct from server instance identity.
- A shared encounter spawn policy must select actual supported grades and legal
  placement using the common NPC/map machinery.
- Room encounter identities and gates must be durable and instance-owned.
- Combat settlement must publish an idempotent victory handoff keyed by fight
  and room encounter; defeat or withdrawal must not advance the room.

No room-progression or victory handoff exists in the current dungeon instance
API. The implementation must reuse atomic settlement evidence and move the
party through the existing transition outbox, rather than derive victory from a
client disconnect or transition acknowledgement. No dispatcher, engine, world
service or normal database was changed by this compiler work.

Validation: `PYTHONPATH=server python3 -m unittest server.tests.test_dungeon_catalog -q`:
11 tests passed. Coverage includes immutable input detachment, unknown data,
invalid counts/references, duplicate identities, version/review gates and
atomic draft output.

## Verified-roster bulk refresh — 2026-10-08

The latest automatic preparation consumes all 87 reviewed guides and 221 rooms.
It emits **35 configurations with resolved guide rosters**, validated against the
native route catalog. This does not imply official spawn coordinates: 31 use
an explicitly recorded local accessible-anchor topology, with frozen exterior
completion destinations. Four use the native topology directly.

The configuration bundle is
`.runtime/local/methodwakfu-dungeons/bulk-prepared-refined/configurations.json`,
SHA-256 `06ca021545f167ddc5a2543837daefc76375f9dac083ad0f7ff4c4b7730af0ee`.
No database activation occurred during this refresh. Optional generated local
rosters remain a separate staged artifact and are not included in this bundle.

Remaining coverage reasons overlap: seven unresolved dungeon identities,
19 unavailable verified topologies, 21 guides with unresolved references/native
level ranges, 28 incomplete compositions, seven unknown quantities, 12 guides
without reviewed rooms, and 13 with an empty room roster. Exact per-guide reasons
remain in `bulk-prepared-refined/coverage.json`.
