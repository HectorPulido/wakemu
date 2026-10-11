# Fishing review, 2026-10-10

Fishing is native profession 75. The installed client defines 52 non-monster resource references and 103 harvest actions: 80 remove their resource (`cvF=0`), while 23 leave an empty resource stage (`cvF=1`). One hundred actions take six seconds; three take five seconds. Native action criteria are empty. Resource 306 has two opaque encounter actions with no fixed primary item; these are excluded pending verified encounter handling.

Native approach evidence differs from mining: `fyk.aaa(75)` returns 3, `gE(distance,75)` accepts distances up to three, and the profession-75 height predicate accepts different source and target heights. Fishing uses independently exported native `cWn.gu:VF.a:profession75` approach positions; combat movement remains governed by its own geometry. See [native bytecode evidence](native-fyk-approach.javap).

Terrain export identifies 3,823 candidate surfaces on 41 maps, with native eligibility for 32 references. Explicit local distribution may place otherwise unsupported species on verified fishing grounds; those placements must retain `local-fishing-ground-fallback` provenance and must never be described as official spawn locations. Native terrain alone does not prove official resource population or rarity.

Fixed fishing spots must preserve identity, transactional item/XP rewards, harvest occupation, exhaustion deadlines, and durable publication. Both resource deletion and empty-stage retention must restore through the same deadline-owned lifecycle. Fishing resources do not reproduce as flora and cannot be planted; reserved cells remain unavailable during exhaustion. Default local respawn policy is 300 seconds, matching mining.

The gameplay catalog and AI service are outside this change. Fishing navigation is published as a compact immutable, independently pinned SQL catalog without activating a different global gameplay catalog.

Installed and verified: 3,377 spots, 51 supported references, 40 maps; 144 focused tests pass and live external-worker restoration succeeds for both exhaustion forms. See [deployment and complete manual acceptance](DEPLOYED-FISHING-20261010.md).
