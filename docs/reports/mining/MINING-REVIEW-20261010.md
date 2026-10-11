# Mining review — 2026-10-10

Historical baseline before fixed-vein implementation and installation. For current
runtime status, see [the deployment report](DEPLOYED-VEINS-20261010.md).

Read-only review of the current server code, native PostgreSQL catalogs and
runtime database. No client, sniffer, server behavior or database rows changed.

## Findings

Mining is profession **73**. Its actions use native skill23, whose catalog
animation is `AnimMinage-Debut` and suffix is `desc.mru.skillPickGem`.
`plant-resources.json` contains **51 mining resource definitions**, all kind0,
with107 stage actions. The catalog has species/stages/actions/products and
requirements; it is not an inventory of placed world veins.

Verified low-level examples:

| Resource | Stage | Action | Profession level | Primary item | Duration |
| --- | --- | --- | --- | --- | --- |
| 37 | 1 | 1632 | 0 | 1846 | 6000 ms |
| 37 | 2 | 70 | 0 | 11478 | 6000 ms |
| 447 | 1 | 1135 | 0 | 1846 | 6000 ms |
| 447 | 2 | 1735 | 0 | 11478 | 6000 ms |
| 242 | 1 | 530 | 5 | 2355 | 6000 ms |
| 242 | 2 | 1724 | 5 | 20584 | 6000 ms |
| 433 | 1 | 1119 | 60 | 13180 | 6000 ms |

The native seed-actions catalog contains **zero mining seeds**. Planting cannot
serve as the normal mining population mechanism.

## Population, publication and exhaustion

The current runtime `planted_resources` contains references23,60 and139, but
**zero rows for all51 mining references**. `resource_growth_transitions` also has
**zero mining rows**. No existing mine coordinate can therefore be offered as a
working end-to-end runtime acceptance probe from this database.

`PLANTINGS.snapshots` reads `planted_resources` by map and instance; it has no
native mining placement import. `world_static` publishes13984 states of native
interactive objects; this is separate from resource publication and does not
create resource partitions. `planting.resource_packet` supplies13135 resource
partition data for database-owned resources.

`resource_collect` provides stage action lookup, profession validation,
occupation reservation, duration checks, transactional inventory delivery,
profession XP and completion receipts. This is useful infrastructure, rather
than evidence that world mining is operational. Existing
`test_profession_action_xp_coverage.py` includes the resource433 mining action;
that test does not verify population or respawn.

The verified mining actions above have native `cvF=0`. Completion consequently
deletes their `planted_resources` row and publishes stage0. There is no mining
placement receipt or exhausted-vein respawn queue to restore that location.
The generic growth worker only processes remaining rows/transitions; deletion
cannot regrow a vein without a separate durable placement lifecycle.

The configured reward policy grants one primary item. Native rare/bonus product
lists are not fully implemented as mining yield probabilities.

## Ecology gap

Completion unconditionally calls `flora_ecology.change`. That implementation
classifies any non-monster resource as kind`plant`, and
`ecology_population.snapshot` likewise counts all non-monster resource rows as
plants. Mining definitions are non-monster kind0, so populating them through the
existing table without a domain distinction would count minerals as flora and
could produce incorrect Wakfu/Stasis ecology changes. This needs a general
classification policy before introducing mining populations.

## Coordinates: verified surfaces, not existing veins

The following are literal native planting surfaces also present in native
combat-map walkable cells, with nonzero suitability for resource37. They are
**candidate placement evidence only**, not proof of an existing mineral or an
already verified harvesting approach. Do not instruct the user to mine them
until population and adjacent reachability are implemented and verified.

| Map | x | y | z | Ground | Region |
| --- | --- | --- | --- | --- | --- |
| 527 | 74 | -53 | 3 | 161 | 66701 |
| 527 | -111 | 0 | 3 | 162 | 75801 |
| 527 | -105 | 0 | 3 | 162 | 75801 |
| 1134 | 136 | -31 | 3 | 161 | 79101 |

Map527 has51 such surfaces for resource37; map1134 has1; map1086 has0.
These counts do not establish official vein distributions or mining species per
region. The current collector also requires an exact native movement edge
from the player's cell to the resource cell, which must be checked against the
native mining approach contract when placements are chosen.

## Work required before a complete manual test

1. Import or derive verified mineral placement identity, species, map, instance
   policy and native harvesting approaches; keep provenance with each location.
2. Populate and publish veins idempotently without duplicating dynamic flora.
3. Preserve durable exhausted placement identity and schedule configured
   respawn; restore exactly once after restart or repeated workers.
4. Exclude minerals from flora ecology and personal affinity changes.
5. Verify concurrent collection, interruption, inventory rollback, retry receipts,
   profession XP, exhaustion publication, reconnect and respawn end to end.
6. After automatic verification, provide the exact deployed resource coordinates
   and test one common vein, a level-gated vein and a rare stage with two players.
