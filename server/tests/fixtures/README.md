# Server test fixtures

Shared deterministic inputs for server tests, independent of private `.runtime/` snapshots.

- `combat/`: native kill, direction and neighborhood oracles, passive-witness geometry and a serialized trigger context.
- `dungeons/`: reviewed Jalató topology and versioned runtime configuration.
- `manifest.json`: provenance paths and SHA-256 checksums for the curated combat and dungeon inputs.
- Other files and subdirectories contain domain-specific regression inputs and their own provenance.

Tests resolve these paths relative to the repository source. Dungeon tests accept their documented `WAKFU_JALATO_*_FIXTURE` environment overrides. Captures, logs, credentials, generated launchers and complete databases do not belong here.
