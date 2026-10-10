# Reproduction operation fences

The reproduction dispatcher previously held both global group and harvest
locks across an entire tick: every tracked location, every due parent,
outbox enumeration and all publication acknowledgments. Captures from the
03:57 UTC incident show both client receive threads waiting behind that fence.

The dispatcher now supplies an operation coordinator to `tick`. It acquires
group then harvest locks separately for each location observation, each birth
attempt, and each outbox group publication. It releases both between independent
operations. Advisory enumeration runs outside these fences.

Each guarded operation receives fresh player presence and harvest exclusions.
If players leave before a delayed observation or attempt, that location is
treated as absent. Birth attempts retain their existing SQL row/advisory locks,
receipt identity, capacity checks and occupation exclusions. Publication
requeries only its current group under the fence, avoiding stale pre-claim
snapshots and an all-groups requery for every group. Removal, spawn and durable
acknowledgment remain ordered within that publication fence.

Validated reproduction settings are loaded once per tick outside the fences
and passed explicitly to observation and attempts. Standalone callers still
load settings normally. There is no global immutable settings cache; database
changes apply on the next tick. Existing timer intervals retain their original
semantics.

Six bounded profiler labels distinguish wait from held time for observation,
attempt and publication. Absent-location observation shares the observation
labels. These measurements will show whether any individual transaction still
holds its operation fence too long.

This removes the **whole-cycle** critical section. It does not eliminate SQL
inside individual operation fences or guarantee that no individual transaction
can stall. No SQL timeout, NOWAIT behavior, row-lock ordering change, shortened
timer or skipped reproduction cycle was introduced. Fully removing global
fences from SQL requires coordinated claim, harvest, planting and ecology
reservation APIs across all consumers.

`test_monster_reproduction_coordination.py` contains five focused regressions:
fresh occupation/player facts between operations; a claim between advisory
enumeration and publication; removal/spawn/ack fence ordering; one policy read
outside the fence per tick with next-tick refresh; and departed-player presence.
The existing PostgreSQL reproduction suite provides durable receipt, population
and concurrency coverage. Full validation is delegated to the test agent.
## Matching maturation coordination

Maturation now uses the same optional per-operation coordination contract.
The world dispatcher releases group and harvest fences between observations,
individual maturation attempts, and individual group publications. Each
observation and attempt refreshes harvest exclusions and actual player presence
for that location. Departure pauses growth rather than charging an offline zone.

Policy is fetched once per active cycle outside the operation fences, validated
at its consumers, and refreshed on the next cycle. Publication enumeration is
advisory: `unpublished(group_id=...)` reloads only the selected group's current
roster and status under its publication fence. Removal, replacement spawn, and
revision-qualified acknowledgment remain ordered under that same fence.

`test_monster_maturation_coordination.py` covers fresh harvest occupations,
departure before an attempt, a claim between outbox enumeration and publication,
and the shared removal/spawn/acknowledgment fence. Existing PostgreSQL clock,
attempt, and publication tests are included in delegated combined validation.
Python compilation passed for maturation, its new tests, and the world dispatcher.
SQL within each authoritative operation still holds the existing global fences;
this change does not claim to eliminate those waits completely.

## Validation and deployment

The combined ecology/combat/spectator/duel selection passed 247 tests without
skips. Additional current-checkout coverage ran 379 tests: 378 passed and one
was skipped. It includes migration 097, titles/emotes, combat authority,
resurrection, summons, haven chest/mount, dungeons and rifts. Two combat authority
test fixtures were completed with valid native QI terrain and actor topology;
production authority validation was preserved. Database writes used isolated
`wakemu_migration_test` schemas.

The complete image `wakemu-world:performance-20261009-r65` was deployed to the
existing single world service. All 680 running source/migration hashes matched
the built image and current checkout. Health returned ok and both game ports
were published. The external continuous profiler resumed with one-hour retention
and no reported error. Prior image r64 remains tagged as a rollback backup.

## Manual acceptance

1. Connect two accounts on an outdoor map containing monsters and resources.
2. Move both characters, collect an available resource and repeat after its
   normal cooldown. Both clients should remain responsive; resources must not
   duplicate rewards or become permanently unavailable.
3. Start a normal monster fight, press Ready, move, cast a spell and end the
   turn. Have the second account observe. Complete the fight, then move and
   collect again outside combat. Record the exact local time of any pause.
4. Challenge the second character to a friendly duel, accept it, play a turn
   and surrender. Repeat the challenge. Neither invitation should stay stuck.
5. Keep playing on the same outdoor map while ecology cycles run. Existing
   growth/reproduction rules must continue; do not change population settings
   merely to force a test. Correlate any pause with the new guard wait/held
   profiler labels before declaring the remaining SQL fence cost resolved.

Live acceptance remains pending. This deployment does not claim to fix the
separately reported invisible beacon or late spectator summon behavior.
