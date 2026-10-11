# Frozen active47 baseline: source-only roster policy migration

All37 ordinary dungeon configurations now have fresh versioned replacement candidates. Ten ultimate-boss arenas are retained unchanged after checking that they contain no dominant, archmonster or unknown native actor. No runtime settings, active pointers or database configuration rows were written; no services restarted.

## Validation result

- 37 ordinary replacements prepared; zero blocked.
- 92 room formations validated for six player slots.
- Full native physical-door or teleporter progression validated for every replacement.
- Output topology equals the original active topology exactly: maps, cells, heights, doors, entry and exit metadata are preserved.
- Native monster minimum levels remain the deterministic spawn policy. The composition difficulty proxy (sum of count times native minimum level) increases strictly between successive rooms.
- Native ARCH45 and DOMINANT_NPC115 actors are forbidden. Native BOSS43 actors occur only in the final room and must belong to the certified final-boss set.

## Corrected early guest bosses

Aguabrial5165 is removed from preliminary family encounters in dungeons127 and128; their actual final bosses are4327 and4260. Guest boss5155 is excluded from dungeons158 and159; their actual final bosses are5131 and5137. Anathar5305 is also excluded from ordinary family pools176–178. Guest-boss removal is based on native family and BOSS metadata, not names or levels.

All37 ordinary final-boss identities were certifiable from native dungeon membership and property43. Ultimate-boss identities use the native ultimate-boss definition and existing arena policy, rather than requiring ordinary BOSS43; their native actor flags differ. These arenas were not rebuilt or promoted as ordinary bosses.

## Compatibility adapters

Kali121 and Mineral Tower133 are single-room arenas without a directed multiroom-flow record. They are validated directly against their literal native entry, encounter and exit.

The already active Tofullero27 configuration omits detailed source approaches and exterior destination fields from its exit objects. For validation only, these fields are recovered from installed native object coordinates, adjacent same-height source cells and the unique verified native exterior destination. The candidate persisted topology remains exactly equal to the original. No geometry or exit behavior is changed by this adapter.

## Artifacts

- `BASELINE47-ROLE-PROGRESSIVE-MIGRATION-20261010.json`: per-route original version/hash, replacement path/version, actual bosses, exclusions, formation, sequence and progression evidence.
- `.runtime/local/baseline47-role-progressive-v1-20261010/`:37 immutable candidate configurations.
- `.runtime/local/baseline47-configuration-export-20261010.json`: read-only frozen runtime export used as input.
- `server/tools/prepare_baseline_dungeon_role_migration.py`: reproducible offline migration preparation. It rejects immutable candidate overwrites and never activates a configuration.

Existing runs and live configurations remain unchanged. Independent validation and eventual explicit release activation belong to the parent release workflow.
