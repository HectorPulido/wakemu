# Fight82 corpse obstacles and summon refresh

The server retained ordinary dead NPC QI obstacles after the native state2 completion boundary. The shared completion now performs OUT_OF_PLAY retirement and QI removal, retaining fighter history. HP0 IN_PLAY actors remain obstacles. This is not a general HP visibility bypass.

Capture also proves beacon52 pW.Uh changed from1 to0 after bulk tactical movement refreshes, then back to1. The embedded NativeStats serializer now delegates to the registered summon serializer for all classes.

NPC IDs passed to native Lua must remain exact through double conversion. The shared allocator and migrations079/080 preserve durable group receipts and alias old identities. Offline repair remapped166 available groups;33 unavailable historical/active groups were intentionally skipped.

Deployed image: wakemu-world:combined-lua-exact-qi-20261008-r39 (SHA f05925eee8c42a345d6190abdd3495c104cf4e8dbe982d68c45e1b2412189f20). It preserves the other coordinator's dungeon breeding changes. Private backup and repair results are under .runtime/combat-review-20261009/pre-r38/.

Validation:26 focused QI/recovery/runtime tests; shared finisher E2E passes after asserting NPC states0 then2;6 isolated PostgreSQL repair tests;5 allocator tests;4 tactical summon refresh tests.

Manual acceptance: start a fresh fight, place a beacon behind one monster, kill that monster, wait for its death animation to finish, and target the beacon directly through the vacated cell. Expect no corpse LOS rejection and no collision at the vacated cell. Let surviving monsters move, then check Desbalizaje remains usable with a living owned beacon and at least1 AP. Kill distinct monsters and check each death animation belongs to its actual victim. Verify final rewards and victory dialog. Old already-active fights were not rekeyed; use a fresh fight.

The screenshots demonstrate the symptom; historical checkpoints alone do not establish a live blocking actor at screenshot time. Fight81 second beacon obstruction remains unproven pending fresh manual verification.

## r40 snapshot regression correction

Fight83 lethal cast at21:50:28UTC disconnected the session with NameError native_qi_retired in monster_actor_stats. The retirement parameter and forwarding argument had been added to the player functions instead of the NPC functions. Moved both to their correct NPC boundaries. Deployed r40 is a one-file delta over r39, preserving concurrent changes. Focused tests now traverse actual lethal death through spectator and reconnect snapshots:33/33 pass. Additional actor/recovery/runtime tests:30/30 pass. The deployed image directly serializes the attested retired NPC slot -1.

## r41 inventory initialization and delayed entry

The client actual hR parser rejected login packet13078 because identified empty shard sockets omitted required nested lK field11. Obfuscated protobuf reflection reported getItemsList instead of the missing required field. Native parser reproduction rejects the original and accepts normalized field11=0 with isInitialized=true. Producer and outgoing legacy serialization corrected; no equipment/DB deletion. r41 adds only inventory_shards.py, shard_identification.py, shard_identification_wire.py above r40.

Acceptance:41 pure tests and14 isolated PostgreSQL tests pass. Includes native-owned bootstrap, spectator/reconnect snapshots, shard persistence and new fight entry after terminal abort. The first invisible-player screenshot remains unproven: selection and world movement completed; native13974 explicitly reattaches and shows the local actor. Do not assert a missing self-spawn packet or checkpoint root cause.

Fight83 was terminally aborted at restart. New fight84 entry succeeded after83.4seconds, then Ready and movement succeeded; reattempts correctly rejected an already-active session. Cold preparation delay requires separate instrumentation; it is not proof of an actor-registration rejection.


### Startup recovery: r43/r44

The r41 shard patch accidentally copied a workspace dependency on a catalog module absent from the deployed image. r43 restores the exact baseline shard files with only the required protobuf initialization changes. Read-only validation with actual character 6 equipment passed. The database already contained migration 082; r44 includes its exact matching source without changing database checksums or reapplying SQL. The bind-mounted AI bridge also required the unavailable catalog module. Its optional database branch now checks module availability; installed database authority still fails closed. Ten focused tests passed, and the actual r44 catalog seal completed successfully. Host API health returned HTTP 200. Client login and combat validation remain pending.


### Host storage outage

OrbStack stopped at 18:04:27 local time with an I/O error. Its host block writer reported StorageFull (errno 28), followed by BTRFS write errors and VM shutdown. Docker socket disappearance took all services offline. Removed disposable build cache and untagged images; retained volumes, databases, and tagged images. Host free space increased from about 7 to 15 GiB. Restarted existing services; world became healthy. Thirty-second API samples: [200, 200, 200, 200, 200, 200, 200]. This confirms recovery, not indefinite stability.
