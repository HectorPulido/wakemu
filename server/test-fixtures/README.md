# Regression fixtures

Small deterministic inputs for server tests, independent of private `.runtime/` snapshots.

- `combat/`: native offline kill, direction and neighborhood oracles plus a serialized trigger context.
- `dungeons/`: reviewed Jalató topology and versioned runtime configuration.
- `manifest.json`: original provenance paths and SHA256 checksums.

Tests resolve these paths relative to the repository source. Dungeon tests accept their documented `WAKFU_JALATO_*_FIXTURE` environment overrides. Captures, logs, credentials, generated launchers and complete databases do not belong here. The game server's historical bootstrap capture is separate and has not been moved into this fixture directory.

## Validation after relocation

All six moved file checksums match their originals. The targeted seven-module suite ran 38 tests: 37 passed; the HUD concentration integration test failed during initialization with `Missing complete owned native QI population`, before its former report-writing block. No missing fixture errors remain in that run. Launcher/package tests ran 15 tests successfully with a freshly generated temporary package.
