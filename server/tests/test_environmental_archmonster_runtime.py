"""Native archmonster sources and one occupied recurrent world-birth lifecycle."""
from collections import Counter
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from psycopg import DatabaseError
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.combat_actor_snapshot import native_actor_catalog
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.monsters import owned_instance, reference
from wakfu_server.npc_actor_identity import allocate_block
from wakfu_server.objectives import environmental_archmonster_geometry as geometry
from wakfu_server.objectives import environmental_archmonster_runtime as runtime


class EnvironmentalArchmonsterRuntimeTests(unittest.TestCase):
    def test_active_normal_event_and_arch_birth_coexist_with_native_count_cooldown_and_spacing(
        self,
    ):
        from test_environmental_owned_resource_population import (
            EnvironmentalOwnedResourcePopulationTests,
        )
        from wakfu_server.objectives import environmental_schedule as schedule
        from wakfu_server import native_catalog

        fixture = EnvironmentalOwnedResourcePopulationTests(
            methodName="test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, world, location = fixture.store, fixture.world, fixture.location
        registry = PersistentGroups(store)
        self.assertTrue(store.heartbeat(fixture.account, fixture.generation, ttl=20000))
        with store.connection() as db:
            db.execute(
                "UPDATE archmonster_spawn_active SET enabled=true WHERE singleton"
            )
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,"
                "anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES('arch-coexist',1,-1320,'resource_collect','collaborative',327,56601,30000000,"
                "0,1,245,'test-only long normal event',%s,%s)",
                ("0" * 64, native_catalog.release()),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives "
                "VALUES('arch-coexist',1,'collect','resource_collect',478,1190,2,'interaction',2)"
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards "
                "VALUES('arch-coexist',1,0,'xp',NULL,100,'test-only')"
            )
            db.execute(
                "INSERT INTO environmental_profile_publication "
                "VALUES('arch-coexist',1,-1320,0,56601,NULL,'remaining_ms','test-only')"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true "
                "WHERE profile_key='arch-coexist'"
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_policies "
                "(policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256) "
                "VALUES('arch-coexist',1,327,56601,'wakemu_round_robin','occupied_sequential_windows',0,'test-only',%s)",
                ("0" * 64,),
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_candidates "
                "VALUES('arch-coexist',1,0,'arch-coexist',1)"
            )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true,enabled=true "
                "WHERE policy_key='arch-coexist'"
            )

        def poll(at):
            fixture.clock[0] = at / 1000
            return runtime.poll(store, world, registry, location=location, now_ms=at)

        first = poll(fixture.now_ms)
        self.assertEqual(len(first), 1)
        with store.connection() as db:
            birth = dict(
                db.execute("SELECT * FROM archmonster_spawn_births").fetchone()
            )
            self.assertTrue(
                runtime.region_pause(db, location=location, now_ms=fixture.now_ms)
            )
            event = dict(
                schedule.select_event(db, location=location, now_ms=fixture.now_ms)
            )
            self.assertEqual(event["state"], "active")
            self.assertLess(birth["cooldown_until_ms"], event["deadline_ms"])
        # The spacing fence must stop birth work before even counting the map;
        # its separate announcement never reserves the normal quest slot.
        with patch.object(
            runtime, "_counts", side_effect=AssertionError("spacing bypassed")
        ):
            self.assertEqual(poll(fixture.now_ms + runtime.REGION_PAUSE_MS - 1), ())
        with store.connection() as db:
            self.assertFalse(
                runtime.region_pause(
                    db,
                    location=location,
                    now_ms=fixture.now_ms + runtime.REGION_PAUSE_MS,
                )
            )
        self.assertEqual(poll(birth["cooldown_until_ms"] - 1), ())
        # Add three actual native actors to the still-living archmonster: the
        # original count<4 rule must continue rejecting a fifth birth.
        taken, members = set(), []
        with registry.lock, store.connection() as db:
            for _ in range(3):
                point = geometry.plan_geometry(
                    db,
                    327,
                    0,
                    56601,
                    birth["monster_reference"],
                    birth["native_level"],
                    taken=taken,
                )
                self.assertIsNotNone(point)
                members.append(
                    owned_instance(
                        birth["monster_reference"],
                        birth["native_level"],
                        -allocate_block(db, 1),
                        map_id=327,
                        instance_id=0,
                        x=point[0],
                        y=point[1],
                        z=point[2],
                    )
                )
                taken.update(
                    footprint(
                        point[:2],
                        native_actor_catalog()["npc_profiles"][
                            str(birth["monster_reference"])
                        ]["physical_radius"],
                    )
                )
            capped = registry.register_transaction(db, 327, 0, 777703, members)
        self.assertEqual(poll(birth["cooldown_until_ms"]), ())
        with store.connection() as db:
            self.assertEqual(
                runtime._counts(db, 327, 0, 56601)[birth["monster_reference"]], 4
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) "
                "VALUES('active','pve') RETURNING id"
            ).fetchone()["id"]
        lease, _ = registry.claim(capped, fixture.generation, fight_id)
        self.assertTrue(registry.finish(lease, defeated=True))
        self.assertEqual(len(poll(birth["cooldown_until_ms"] + 1)), 1)
        with store.connection() as db:
            same = schedule.select_event(
                db, location=location, now_ms=birth["cooldown_until_ms"] + 1
            )
            self.assertEqual(same["instance_id"], event["instance_id"])
            self.assertEqual(same["state"], "active")
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM archmonster_spawn_births"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )

    def test_all_native_sources_real_birth_count_caps_rollback_partial_retry_and_spawn_anchored_cooldown(
        self,
    ):
        from test_environmental_owned_resource_population import (
            EnvironmentalOwnedResourcePopulationTests,
        )

        fixture = EnvironmentalOwnedResourcePopulationTests(
            methodName="test_original_population_real_profession_zero_occupation_and_atomic_cleanup"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, world = fixture.store, fixture.world
        registry = PersistentGroups(store)
        self.assertTrue(store.heartbeat(fixture.account, fixture.generation, ttl=20000))
        location = fixture.location
        with store.connection() as db:
            sources = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM archmonster_spawn_sources ORDER BY scenario_id"
                )
            ]
            self.assertEqual(len(sources), 63)
            blocked = [r for r in sources if r["blocked_by_membership"]]
            self.assertEqual({r["scenario_id"] for r in blocked}, {-2108, -2107})
            self.assertEqual(sum(not r["blocked_by_membership"] for r in sources), 61)
            self.assertTrue(
                all(
                    r["participation_criterion"] == "False"
                    and r["announcement_duration_ms"] == 10000
                    and r["requested_group_count"] == 1
                    for r in sources
                )
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM archmonster_spawn_scopes"
                ).fetchone()["n"],
                65,
            )
            cadence_rows = db.execute(
                "SELECT authority_kind,count(*) AS n FROM archmonster_spawn_cadences WHERE policy_version='wakemu.native-count-archmonster-world-birth-v1' GROUP BY authority_kind"
            ).fetchall()
            self.assertEqual(
                {r["authority_kind"]: r["n"] for r in cadence_rows},
                dict(SOURCE_DERIVED_PUBLIC=59, DECLARED_WAKEMU=2),
            )
            for source in sources:
                self.assertIs(
                    runtime._eligible(db, source, Counter()),
                    not source["blocked_by_membership"],
                )
                self.assertFalse(
                    runtime._eligible(
                        db, source, Counter({source["monster_reference"]: 4})
                    )
                )
            target = next(r for r in sources if r["scenario_id"] == -1319)
            self.assertEqual(
                (
                    target["monster_reference"],
                    target["native_min_level"],
                    target["native_max_level"],
                ),
                (4393, 98, 103),
            )
            active = dict(
                db.execute(
                    "SELECT * FROM archmonster_spawn_active WHERE singleton"
                ).fetchone()
            )
            self.assertFalse(active["enabled"])
            fallback = db.execute(
                "SELECT * FROM archmonster_spawn_policy_versions WHERE policy_version=%s",
                (active["policy_version"],),
            ).fetchone()
            self.assertEqual(fallback["cooldown_ms"], 14400000)
        self.assertEqual(
            runtime.poll(
                store, world, registry, location=location, now_ms=fixture.now_ms
            ),
            (),
        )
        world.leave(fixture.character["id"], fixture.generation)
        untouched = Mock()
        self.assertEqual(
            runtime.poll(
                untouched,
                world,
                SimpleNamespace(store=untouched),
                location=location,
                now_ms=fixture.now_ms,
            ),
            (),
        )
        untouched.connection.assert_not_called()
        db_never = Mock()
        self.assertIsNone(
            geometry.plan_geometry(db_never, 327, 0, 56601, 4393, 98, taken=())
        )
        db_never.execute.assert_not_called()
        world.join(fixture.generation, object(), fixture.character)
        with store.connection() as db:
            db.execute(
                "UPDATE archmonster_spawn_active SET enabled=true WHERE singleton"
            )

        def poll(at):
            fixture.clock[0] = at / 1000
            return runtime.poll(store, world, registry, location=location, now_ms=at)

        def ordinary_group(breed, level, count, group_id):
            taken, members = set(), []
            with registry.lock, store.connection() as db:
                for _ in range(count):
                    point = geometry.plan_geometry(
                        db, 327, 0, 56601, breed, level, taken=taken
                    )
                    self.assertIsNotNone(point)
                    actor_id = -allocate_block(db, 1)
                    members.append(
                        owned_instance(
                            breed,
                            level,
                            actor_id,
                            map_id=327,
                            instance_id=0,
                            x=point[0],
                            y=point[1],
                            z=point[2],
                        )
                    )
                    taken.update(
                        footprint(
                            point[:2],
                            native_actor_catalog()["npc_profiles"][str(breed)][
                                "physical_radius"
                            ],
                        )
                    )
                return registry.register_transaction(db, 327, 0, group_id, members)

        def defeat(key):
            with store.connection() as db:
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
                ).fetchone()["id"]
            lease, _ = registry.claim(key, fixture.generation, fight_id)
            self.assertTrue(registry.finish(lease, defeated=True))

        capped = ordinary_group(4393, 98, 4, 777701)
        with store.connection() as db:
            self.assertEqual(runtime._counts(db, 327, 0, 56601)[4393], 4)
        self.assertEqual(poll(fixture.now_ms), ())
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM archmonster_spawn_births"
                ).fetchone()["n"],
                0,
            )
        defeat(capped)
        ordinary = ordinary_group(5008, reference(5008)["min_level"], 1, 777702)
        with store.connection() as db:
            capacity = dict(
                db.execute(
                    "SELECT * FROM environmental_random_roster_active WHERE singleton"
                ).fetchone()
            )
            db.execute(
                "INSERT INTO environmental_random_roster_versions "
                "SELECT %s,policy_contract,min_members,max_members,1,1,%s,source_sha256 "
                "FROM environmental_random_roster_versions WHERE policy_version=%s",
                (
                    "fixture-one-physical-slot",
                    "explicit single-slot capacity fixture",
                    capacity["policy_version"],
                ),
            )
            db.execute(
                "UPDATE environmental_random_roster_active SET policy_version='fixture-one-physical-slot' WHERE singleton"
            )
        self.assertEqual(poll(fixture.now_ms), ())
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM archmonster_spawn_births"
                ).fetchone()["n"],
                0,
            )
            db.execute(
                "UPDATE environmental_random_roster_active SET policy_version=%s WHERE singleton",
                (capacity["policy_version"],),
            )
        defeat(ordinary)
        original_register = registry.register_transaction

        def abort_registration(*args, **kwargs):
            original_register(*args, **kwargs)
            raise RuntimeError("rollback actual archmonster registration")

        with patch.object(
            registry, "register_transaction", side_effect=abort_registration
        ), self.assertRaisesRegex(RuntimeError, "rollback actual archmonster"):
            poll(fixture.now_ms)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM archmonster_spawn_births"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM archmonster_spawn_publications"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM combat_groups WHERE status='available'"
                ).fetchone()["n"],
                0,
            )
        # A real partial require-all delivery sends the native announcement to
        # one peer, fails the other, and retains the committed outbox. Reconnect
        # after ten seconds retries only the still-current native spawn.
        peer = SimpleNamespace(shutdown=lambda *_: None)
        observer_account = store.register("archmonster-observer", "test-password")["id"]
        observer = store.create_character(observer_account, "Archmonster Observer")
        observer_generation = store.begin_session(observer_account)
        store.select_character(observer_account, observer_generation, observer["id"])
        self.assertTrue(
            store.heartbeat(observer_account, observer_generation, ttl=20000)
        )
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=327,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (
                    fixture.character["x"],
                    fixture.character["y"],
                    fixture.character["z"],
                    observer["id"],
                ),
            )
        observer = store.character(observer_account, observer["id"])
        world.join(observer_generation, peer, observer)
        batches, failing = [], [peer]

        def send_batch(recipient, packets):
            if recipient is failing[0]:
                raise OSError("one recipient unavailable")
            batches.append((recipient, packets))

        world.deliver_batch = send_batch
        with self.assertRaises(OSError):
            poll(fixture.now_ms)
        self.assertTrue(
            any([op for op, _ in packets] == [12608, 12175] for _, packets in batches)
        )
        announcement = next(
            body for _, packets in batches for op, body in packets if op == 12175
        )
        self.assertEqual(struct.unpack(">i", announcement), (-1319,))
        with store.connection() as db:
            birth = dict(
                db.execute("SELECT * FROM archmonster_spawn_births").fetchone()
            )
            self.assertEqual(
                (
                    birth["monster_reference"],
                    birth["native_level"],
                    birth["cooldown_ms"],
                ),
                (4393, 98, 9000000),
            )
            self.assertEqual(
                birth["cooldown_until_ms"], birth["spawned_at_ms"] + 9000000
            )
            self.assertIsNone(
                db.execute(
                    "SELECT published_at_ms FROM archmonster_spawn_publications"
                ).fetchone()["published_at_ms"]
            )
            group = dict(
                db.execute(
                    "SELECT * FROM combat_groups WHERE map_id=327 AND instance_id=0 AND group_id=%s",
                    (birth["group_id"],),
                ).fetchone()
            )
            self.assertEqual(len(group["members"]), 1)
            member = group["members"][0]
            self.assertEqual(
                (member["id"], member["ref"], member["level"]),
                (birth["monster_id"], 4393, 98),
            )
            self.assertGreater(member["hp"], 0)
            self.assertNotIn("environmental_world_action_only", member)
            self.assertTrue(reference(4393)["loot_definitions"])
            with self.assertRaises(DatabaseError), db.transaction():
                db.execute(
                    "UPDATE archmonster_spawn_births SET cooldown_until_ms=cooldown_until_ms+1"
                )
        failing[0] = None
        world.leave(observer["id"], observer_generation)
        world.join(observer_generation, peer, observer)
        batches.clear()
        self.assertEqual(poll(birth["spawned_at_ms"] + 10001), ())
        self.assertTrue(batches)
        self.assertTrue(
            all([op for op, _ in packets] == [12608] for _, packets in batches)
        )
        for _, packets in batches:
            body = packets[0][1]
            self.assertEqual(body[1], 1)
            self.assertEqual(struct.unpack_from(">q", body, 3)[0], birth["monster_id"])
        with store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT published_at_ms FROM archmonster_spawn_publications"
                ).fetchone()["published_at_ms"]
            )
        death_at = birth["spawned_at_ms"] + 1000000
        poll(death_at)  # Announcement expiry is not a monster TTL.
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_groups WHERE group_id=%s",
                    (birth["group_id"],),
                ).fetchone()["status"],
                "available",
            )
        defeat((327, 0, birth["group_id"]))
        self.assertEqual(poll(birth["cooldown_until_ms"] - 1), ())
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM archmonster_spawn_births"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT cooldown_until_ms FROM archmonster_spawn_births"
                ).fetchone()["cooldown_until_ms"],
                birth["cooldown_until_ms"],
            )
        next_ids = poll(birth["cooldown_until_ms"])
        self.assertEqual(len(next_ids), 1)
        with store.connection() as db:
            next_birth = db.execute(
                "SELECT * FROM archmonster_spawn_births WHERE spawn_id=%s",
                (next_ids[0],),
            ).fetchone()
            self.assertNotEqual(next_birth["monster_id"], birth["monster_id"])
            self.assertNotEqual(next_birth["group_id"], birth["group_id"])
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_groups WHERE group_id=%s",
                    (birth["group_id"],),
                ).fetchone()["status"],
                "defeated",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
