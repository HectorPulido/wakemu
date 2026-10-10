# Mission-free dungeon entrance policy

Status: implemented in source; not migrated into the live database, deployed, or restarted. Native client entry behavior has not been accepted manually.

Migration `089_dungeon_entry_access_policy.sql` adds the editable setting `dungeon_entry_access_policy`:

```json
{"version":1,"bypass_mission_prerequisites":true,"bypass_state_prerequisites":true}
```

Only configured dungeon entrances (`12296`, `configured_entry`, before run creation) use this policy. `IsAchievementRunning`, `IsAchievementComplete`, `IsAchievementObjectiveComplete`, and entrance-only `HasState` are waived. No quest/state snapshots are changed. Internal doors and room victory progression retain their existing authority.

Waived predicates propagate an unknown result through AND/OR/NOT, accepted at the expression root. A required false level/date/server-mode predicate still denies access; a mission alternative can permit entry. Invalid identifiers, unsupported predicates, malformed configuration, source proximity, route identity, session ownership, capacity, and transactional run creation are still checked. Item/kama transactions, required levels, calendar dates, Neo mode, missing run configurations, and unsupported predicates are not waived by this policy.

## Catalog coverage

The inventory contains 151 native definitions, 139 native entry routes and 87 local configurations. Configuration and native definition identity are different sets; installing this policy does not materialize the missing dungeon configurations.

Exactly five native entry routes in `inventory.json` contain achievement/state prerequisites:

| Dungeon | Native prerequisites waived | Remaining notable conditions |
| --- | --- | --- |
| Castillo de Wagnar | `not HasState(5724)` | `not IsNeoServer()` |
| Castillo del Wey Wabbit | Achievement 5182/objectives 10854,10855; achievement 5187/objectives 10774,10775, including negations | `not IsNeoServer()` |
| Mazmorra de los Sabanastrales | Achievement 5335/objectives 11278,11279, including negations | None in this route expression |
| Neocastillo del Wey Wabbit | Same Wabbit achievement/objective gates | `IsNeoServer()` and unsupported `GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 8` |
| Teatro Intemporal | Achievement 5553/objectives 11474,11475, including negations | None in this route expression |

These counts describe exported entrance expressions, not all missions associated with every dungeon in the live game. Missing or script-owned entrances remain inventory gaps.

## Native client gate and scoped DEV override

`javap -c -p` against `client/lib/wakfu-client.jar` confirms an independent client-side gate:

- `bFE.f(flF)` invokes `flF.bdt().amb.b(localPlayer, ..., localPlayer.fqE())` to evaluate the static native criterion.
- `bFE.a(flF)` combines criterion and dungeon-instance eligibility and initializes the interaction's disabled status through `cXI.bn(boolean)`.
- `cXI.bxQ()` additionally hides menu actions when `flF.gev()`/`gew()` request criterion/instance filtering.
- `flF.sxF`, the criterion, is a final field populated from native data. `ProtoDungeon` fields 1–8 carry difficulty/level/participant state, not an entry expression override.

No legitimate server packet overriding this static criterion has been demonstrated. The source therefore extends the existing local `OpenPlantingAgent` with a separate `wakfu.local.openDungeonMissions` property. Its ASM transformation intercepts the exact native `flF` constructor and substitutes only the criterion argument for the five exported entrance destination IDs. Copy constructors inherit the already projected criterion. Unrelated destinations, internal doors, quest ledgers, native binaries, and original game data remain untouched.

`server/tools/build_dungeon_entry_overrides.py` builds the five projections automatically from the inventory. It computes definitely-true/definitely-false bounds for the native AST and emits `not(definitely_false)`, equivalent to the server's ternary policy. Original non-mission level/date/item/server-mode predicates remain in the resulting expression. Native eQb/eQd parse the projections at runtime. Unsupported server predicates remain unsupported, including the Neo global variable guard.

`dungeon-entry-source-version.json` pins the reviewed native client JAR SHA-256 and native catalog release. Generation refuses a different client JAR or catalog release until both data sources are re-extracted/reviewed and the pin is deliberately updated; a build cannot silently bless a new client with old route IDs. The generated resource also includes SHA-256 of the client JAR. Before any substitution the agent compares that hash with the JAR actually providing native `amb`; a mismatch fails explicitly. It does not silently apply the policy to another client version. Both the local agent build and portable package build include this generated resource.

The local shell launcher enables this property by default, with `WAKFU_OPEN_DUNGEON_MISSIONS=false` as opt-out. Portable/configured launchers default to enabled only for server host `127.0.0.1`; other hosts require explicit boolean `open_dungeon_missions: true` in the private launcher configuration. Existing network guard behavior is retained. Operators should align this client flag with the database policy; disabling the database bypass continues to deny entry authoritatively even if the client permits attempting it.

This takes effect only in a **future client launch using a rebuilt agent**, together with the future complete server build/migration. The running client and server were not restarted or modified. Menu behavior remains pending visual acceptance.

## Validation and acceptance

`test_dungeon_entry_access` covers positive/negated/nested gates, ternary AND/OR combinations, non-mission level checks, malformed predicates/policy, strict internal-door behavior, live policy reads, and missing settings. Existing criterion, achievement, transport, strict-door, runtime-route and geometry tests passed delegated isolated validation: **83 tests, no failures or skips**, including migration089 in temporary schemas on `wakemu_migration_test`. The offline native oracle `sniffer/java/VerifyDungeonEntryOverride.java` passed against the rebuilt agent: all five expressions parsed with the actual native lexer/parser; both mission-only entries accepted through the transformed `flF` constructor; an unrelated destination retained its false criterion; disabling the opt-in retained the original object. An isolated agent JAR with an altered embedded `native_sha256` was explicitly rejected. No game client process was started.

Build and reproducibility commands:

```sh
PYTHONPATH=server python3 server/tools/build_dungeon_entry_overrides.py
bash client-tools/runtime/build-open-planting-agent.sh
```

A second delegated gate passed **28 tests, no failures or skips**, covering projection/source-pin rejection, access-policy PostgreSQL integration, packaged-resource allowlists, local/remote launcher configuration, and existing launcher behavior. Regression coverage includes `test_build_dungeon_entry_overrides`, `test_dungeon_entry_access`, `test_local_launcher`, and `test_mini_launcher_package`. These overlap the earlier 83-test gate; counts must not be added as unique tests.

After the future complete shared build and authorized restart: verify a character with no relevant quest can use each supported affected entrance; verify required level/mode restrictions still apply; clear a first room and verify its door opens only after the room's authoritative victory. Observe whether any native menu remains hidden/disabled and record its native route ID before claiming frontend completion.
