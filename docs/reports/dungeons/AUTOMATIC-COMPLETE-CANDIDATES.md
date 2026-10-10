# Offline complete physical dungeon candidates

Eight configurations now combine native directed exploration, physical gate
order, reviewed or explicit DEV rosters, validated combat formation, and literal
native entrance/final exterior exits:

- Trinchera de Huelguerreros
- Mazmorra de los Demorribles
- Mazmorra del Charcoso Real
- Mazmorra de los Fitoformes
- Mazmorra de los Vaciantes
- Cuerbokueva
- Pasto Real
- Tofullero (existing accepted runtime configuration remains unchanged)

The previous eleven candidates covered geometric placement only. Three included
unresolved reviewed monster identities and are now withheld rather than filling
them by name or substituting another species: Devastadores, Antro Olvidado and
Yech'Ti'Wawa. The general roster validator now rejects these identities.

All eight prepared candidates pass a full **offline exploration sequence**:
entry reaches an adjacent engagement cell in every room at its proper gate
stage, while treating that room's monsters as occupied cells; future gates reject
crossing, opening the next stage permits it, and the final native exit approach
is reachable after all gates open. The native state packet layouts and immutable
plan hashes also validate. Complete path witnesses are recorded in
[AUTOMATIC-FLOW-SEQUENCE-VALIDATION.json](AUTOMATIC-FLOW-SEQUENCE-VALIDATION.json).
Native source objects, destination coordinates and approach cells are recorded
in [AUTOMATIC-COMPLETE-CANDIDATES.json](AUTOMATIC-COMPLETE-CANDIDATES.json).

Exit binding accepts only literal native approach cells, or the literal source
center when native metadata explicitly permits center use. It requires a unique
entrance and final exit, a native walkable exterior destination, and supported
free/unconditional transport. No guessed neighbor or nearest-cell replacement
is used.

All eight additionally pass the isolated PostgreSQL lifecycle gate with three
players: validated native entry requests, atomic first spawn and whole-party
movement, bootstrap/outbox delivery after companion movement, nonleader exterior
return/reentry preserving companions inside, durable victory settlement and
idempotent replay in every room, next-room spawning and native door state,
completed-run no-spawn, final native exit requests for all three players, closed
old run and fresh entry into a new instance. The test uses authoritative finished
fight fixtures and the actual reward policy/award services with the spawned
native monster references and levels. It verifies three XP/wallet receipts per
room, duplicate-award rejection and atomic rollback of rewards plus progression.
It does not simulate boss AI or spell execution.

At Hector's explicit request, seven configurations were activated at immutable
version 3 and accepted Tofullero v3 was preserved. Runtime pointers were read back
and verified; no restart was performed. Existing runs keep their pinned versions.
All eight retain incomplete boss spell or mechanic coverage. Actual boss combat simulation and client acceptance
remain separate pending gates. No server was restarted. The activation is an explicit reversible runtime database
configuration update with a saved backup; no bulk activation migration was generated. Generated versions are offline proposals only; installation must
assign immutable versions against current active settings and preserve accepted
Tofullero.

Reproduce:

```sh
PYTHONPATH=server python3 server/tools/prepare_native_physical_candidates.py
PYTHONPATH=server python3 server/tools/validate_prepared_physical_flows.py
python3 -m unittest discover -s server/tests -p test_physical_candidate_exits.py
```

The database lifecycle regression is
`test_prepared_physical_flow_postgres.PreparedPhysicalFlowPostgresTests`; it
passed all eight candidate subcases in 6.999 seconds against a disposable schema
in `wakemu_migration_test`. Candidate versions are rebound to disposable test
version 10001 rather than replacing migration-seeded immutable configurations.
The test restores the process route registry and drops its isolated schema.

### Native NPC economy correction

Actual reward settlement initially rejected the native level 218–233 monsters
in three candidates because the reward service and tables limited NPCs to the
player cap of 200. Migration 099 and the reward validator now support positive
native signed-short NPC levels independently of player progression. Existing
levels 1–200 and reference overrides are unchanged. Levels 201–32767 receive an
explicit DEV nearest-lower extension of migration 041's level-200 default, with
nonofficial provenance; these database rows remain individually configurable.
This is an emulation balance policy, not official Wakfu reward data.

All eight candidate lifecycle/economy subcases now pass: 20 room victories and
60 durable player reward receipts. The actual isolated PostgreSQL run writes
[per-route economy evidence and source hashes](AUTOMATIC-PG-LIFECYCLE-ECONOMY.json)
when `WAKFU_DUNGEON_LIFECYCLE_AUDIT` names an output path. The final recorded run
passed in 12.094 seconds. Three dedicated tests additionally verify high NPC
levels, unchanged player cap, nearest-lower provenance and explicit reference
overrides. Production source changes are finalized. The eight flows are activated under
Hector's explicit instruction with incomplete boss combat mechanics documented;
full boss gameplay acceptance remains pending.

See [activation verification and complete manual commands](AUTOMATIC-PHYSICAL-ACTIVATION.md)
and [the read-back database audit](AUTOMATIC-PHYSICAL-ACTIVATION.json).
