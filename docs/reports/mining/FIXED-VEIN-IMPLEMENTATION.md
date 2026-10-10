# Fixed mining veins: source implementation and acceptance

Status: prepared and automatically validated; not deployed or installed.

Minerals use fixed database slots, independently of flora ecology and reproduction.
Successful collection atomically grants the native product and profession XP, removes
the vein, and schedules its return at the same position. Failed or duplicate
completion does not consume the vein or duplicate rewards. Respawn defaults to300
seconds in `settings.mining_vein_policy`; per-slot overrides are supported.
Exhaustion deadlines survive reconnects and server restarts. Planting cannot occupy
reserved mineral slots.

## Distribution and evidence

The expanded local plan allocates2881 unambiguous accessible slots on46 maps,
representing all51 catalog mineral references. Lower-level minerals receive higher
probability; alternate stages receive a lower weight. All51 have at least one slot.
Eighteen references lack a verified native terrain association and use explicitly
marked `local-mineral-ground-fallback` placements under the approved local rules.
Reference643 selects one existing native candidate product through the configurable
`native_candidates_weighted` policy; this is a local rule, not a verified official
interpretation of its candidate list.

Read-only extraction scanned961 map pairs and31238 chunk pairs. There are3078
candidate records:2881 usable unambiguous targets,196 records sharing ambiguous XY
heights, and1 target without a native harvesting approach. There remain1509 chunks
with native decoding/query failures. Therefore the plan covers100% of the extracted
unambiguous accessible slots and51/51 mineral references; it does not establish100%
of official vein locations. Mining approach checks use native profession adjacency,
including nonwalkable resource targets, rather than requiring the vein itself to
be a walkable combat cell.

## Release preparation

Migration100 creates slots and policy. `stage_mining_navigation_catalog.py` prepares
a complete immutable catalog revision and preserves unrelated documents and records;
default mode only reads, and explicit staging never activates a release.
`install_mining_veins.py` defaults to validation only. Its `--navigation-dir` permits
offline evidence validation and cannot be combined with `--apply`. Runtime
installation requires published navigation authority and a matching plan revision.
No runtime migration, catalog activation, slot import, deployment or restart has been
performed for this work.

## Automated verification

- Vein lifecycle, product selection and51-reference support:19 tests passed.
- Placement and native navigation:8 tests passed.
- Planner and navigation regression:10 tests passed.
- Immutable catalog staging:7 tests passed, including preservation of unrelated data.
- Existing flora growth and harvest regression gates remain recorded in their tests.

## Complete manual acceptance after deployment and import

1. Enter with a new account and an existing account. All15 professions must appear;
   new professions start at0 and existing progress remains unchanged.
2. Locate a level0 slot using the reviewed final plan's `minimum_profession_level`
   and coordinates. Use `!teleport MAP X Y Z` with that row's exact values, move onto
   one of its verified adjacent approach cells, then collect. Expect the native
   product and configured XP after its native action duration.
3. With a second player watching, verify depletion on both clients and unchanged
   ecology. Concurrent collection must grant only one completion reward.
4. Reconnect while exhausted: the vein must remain absent. After the configured
   respawn interval, both players must see it return at the same position and be
   able to collect it again. Reconnect after respawn and verify visibility.
5. Repeat with a full inventory: failure must preserve the vein and grant nothing.
   Free a slot and collect successfully. Try a vein above your miner level: reject
   without reward or depletion.
6. Test one explicitly marked alternate-stage slot and reference643. Verify only
   catalog-native products are granted and replaying completion grants nothing.
7. Harvest/grow an ordinary plant and verify unchanged behavior. Attempt planting
   on an exhausted reserved mineral position: reject without consuming seeds.

Final plan coordinates are source preparation, not currently live veins. Graphical
acceptance remains pending.
