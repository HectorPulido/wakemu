# Versioned dungeon configuration from JSON

`server/tools/import_dungeon_runtime_config.py` prepares one explicitly selected dungeon from the compiled room JSON, native topology, authoritative entry routes and native monster catalog. `--slug` is mandatory; there is no implicit bulk import. Every input requires a SHA-256 argument. Preparation writes a configuration artifact; SQL installation requires `--apply`.

The current selected artifact is `server/test-fixtures/dungeons/jalato-runtime-config-v1.json`. It contains Jalató definition 90, template 91, asset map 1086, reviewed room rosters and derived native room topology. No runtime database was modified while preparing it.

The context is an explicit local server policy, not an assertion about the official Jalató instance: minimum and maximum context levels 0, fixed difficulty 2, difficulty controls disabled, no level scaling, competitive cancellation false and an empty authorization-ID list. The native `eUZ` constructor supports default difficulty 2, level 0 and an empty list; it does not establish official dungeon-specific values or the meaning of authorization IDs. The native `aKU.aWb()` value 12 is not used as a guessed minimum or maximum context level.

The common monster grade policy selects the native minimum level and rejects changed native grade bounds. This choice is recorded with local-policy provenance, independently of the website's suggested levels. Future policies require another configuration version rather than mutation of existing runs.

`maps/dungeon_runtime_config.py` stores versioned JSON in `settings` and inserts the matching immutable context-policy version. It selects the active version only after both are installed inside the caller transaction. A route advisory lock serializes competing installations. The caller must commit the transaction before publication.

Runtime integration APIs:

- `active_configuration(db, route_key)` selects the configuration for a new run.
- `pinned_configuration(db, route_key, version, expected_plan_hash=...)` loads a reconnecting run without consulting the active pointer. The context version and configuration version share the same number.
- `plan_from_configuration(config)` reconstructs the frozen `DungeonPlan` after verifying its hash.
- `level_selector(config)` returns the common native-grade selector used by room spawning.
- `install_configuration(db, config)` installs prepared configuration inside a caller-owned transaction.

Seven focused tests pass, covering explicit policy, native grade bounds, route identity, incomplete rosters, native anchors, plan hash integrity and pinned-version reconnect lookup. SQL installation and playable dungeon acceptance remain separate deployment gates.
