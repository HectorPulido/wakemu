"""Native action3 removes real owned UIDs; it never supplies a combat win."""
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch

from psycopg import DatabaseError
from psycopg.types.json import Jsonb
from wakfu_server import heroes
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.combat_groups import Groups
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.monsters import owned_instance, REFERENCES
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.objectives import environmental_gameplay as gameplay
from wakfu_server.objectives import environmental_monster_destroy as destroy
from wakfu_server.objectives import environmental_destroy_publication as publication
from wakfu_server.objectives import environmental_group_population as population
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives import environmental_random_rosters as rosters
from test_environmental_group_bulk_pipeline import seed_sql


class EnvironmentalDestroyLifecycleTests(unittest.TestCase):
    def test_native_actions_owned_company_rollback_once_counters_and_current_roster_publication(
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
        store, account, main = fixture.store, fixture.account, fixture.character["id"]
        registry = PersistentGroups(store)
        hero = store.create_character(account, "Native Destroy Hero")
        with store.connection() as db:
            db.execute("UPDATE characters SET level=81 WHERE id=%s", (hero["id"],))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[81], hero["id"]),
            )
        heroes.add(store, account, fixture.generation, main, hero["id"])
        self.assertTrue(store.heartbeat(account, fixture.generation, ttl=3600))
        profiles = [
            "destroy-native-1327-327-56601",
            "destroy-native-1326-327-56601",
            "destroy-native-1325-327-56601",
        ]
        with store.connection() as db:
            for fragment in seed_sql("environmental_destroy_profiles.sql").split(";\n"):
                text = fragment.strip()
                if any("E'" + key + "'" in text for key in profiles) and (
                    text.startswith("INSERT INTO environmental_profile_")
                    or text.startswith("INSERT INTO environmental_runtime_profiles")
                    or text.startswith(
                        "UPDATE environmental_runtime_profiles SET sealed=TRUE"
                    )
                ):
                    db.execute(text + ";", prepare=False)
            db.execute(
                "UPDATE environmental_runtime_profiles SET enabled=true WHERE profile_key=ANY(%s)",
                (profiles,),
            )
            db.execute(
                "INSERT INTO environmental_regional_schedule_policies "
                "(policy_key,version,map_id,region_id,selection_policy,cadence_policy,intermission_ms,authority,source_sha256) "
                "VALUES('fixture-native-destroy',1,327,56601,'wakemu_round_robin','occupied_sequential_windows',0,"
                "'finite source-exact native destruction component',%s)",
                ("0" * 64,),
            )
            for ordinal, key in enumerate(profiles):
                db.execute(
                    "INSERT INTO environmental_regional_schedule_candidates VALUES('fixture-native-destroy',1,%s,%s,1)",
                    (ordinal, key),
                )
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true,enabled=true WHERE policy_key='fixture-native-destroy'"
            )
            db.execute(
                "UPDATE environmental_random_roster_active SET enabled=true WHERE singleton"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
        ordinary = owned_instance(
            5008,
            REFERENCES[5008]["min_level"],
            -99990001,
            map_id=327,
            instance_id=0,
            x=fixture.points[0][0],
            y=fixture.points[0][1],
            z=fixture.points[0][2],
        )
        ordinary_key = registry.register(327, 0, 777700, [ordinary])
        with store.connection() as db:
            ordinary_before = dict(
                db.execute(
                    "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                    ordinary_key,
                ).fetchone()
            )
        edges = {(tuple(a), tuple(b)) for a, b in map_geometry(327)["edges"]}
        sources = {}
        for source, target in sorted(edges):
            sources.setdefault(target, source)

        def refresh():
            return service.refresh(
                store,
                account,
                fixture.generation,
                main,
                location=fixture.location,
                now_ms=int(fixture.clock[0] * 1000),
                groups=registry,
            )

        def approach(member, *, owner_account=account, identity=main, generation=None):
            generation = fixture.generation if generation is None else generation
            target = tuple(member[k] for k in ("x", "y", "z"))
            self.assertIn(target, sources)
            # Test setup relocates an actual owned actor to a genuine adjacent
            # native floor cell; this does not claim to exercise movement costs.
            with store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=327,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s",
                    (*sources[target], identity, owner_account),
                )
            actual = store.character(owner_account, identity)
            fixture.world.join(generation, object(), actual)
            return actual

        def reachable(owner, target):
            return (
                tuple(owner[k] for k in ("x", "y", "z")),
                tuple(target[k] for k in ("x", "y", "z")),
            ) in edges

        def action(member, *, roll_back=False, loaded=True, reach=reachable):
            actual = approach(member)
            body = struct.pack(">qq", member["id"], 265)
            fixture.clock[0] += 0.01
            with registry.lock, store.connection() as db:
                receipt = destroy.commit(
                    store,
                    db,
                    account,
                    fixture.generation,
                    actual,
                    body,
                    groups=registry,
                    reachable=reach,
                    loaded=loaded,
                    now_ms=int(fixture.clock[0] * 1000),
                )
                changes = gameplay.committed_monster_destroy(db, receipt)
                if roll_back:
                    raise RuntimeError("rollback complete native action")
                return receipt, changes

        for mode, expected_groups in (
            ("race", 3),
            ("competitive", 100),
            ("collaborative", 50),
        ):
            snapshot = refresh()
            event_id = snapshot["instances"][0]["instance_id"]
            with store.connection() as db:
                event = dict(
                    db.execute(
                        "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()
                )
                profile = storage._event_profile(db, event)
                self.assertEqual(profile["mode"], mode)
                owned = db.execute(
                    "SELECT * FROM environmental_owned_groups WHERE instance_id=%s ORDER BY group_ordinal",
                    (event_id,),
                ).fetchall()
                self.assertEqual(len(owned), expected_groups)
                born = db.execute(
                    "SELECT monster_reference,native_level FROM environmental_owned_group_members WHERE instance_id=%s",
                    (event_id,),
                ).fetchall()
                self.assertEqual(
                    {(r["monster_reference"], r["native_level"]) for r in born},
                    {(2253, 1)},
                )
                if mode == "collaborative":
                    self.assertEqual(
                        storage._objectives(db, profile)[0]["required_quantity"],
                        len(born),
                    )
                    self.assertEqual(
                        rosters.frozen_birth_count(db, event, "monster"), len(born)
                    )
                group_rows = [
                    dict(
                        db.execute(
                            "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                            (327, 0, row["group_id"]),
                        ).fetchone()
                    )
                    for row in owned
                ]
            selected = max(group_rows, key=lambda row: len(row["members"]))
            members = deepcopy(selected["members"])
            self.assertTrue(
                all(m.get("environmental_world_action_only") is True for m in members)
            )
            key = (327, 0, selected["group_id"])
            with self.assertRaisesRegex(ValueError, "cannot enter combat"):
                registry.claim(key, fixture.generation, 12345)
            in_memory = Groups()
            in_memory.register(*key, members)
            with self.assertRaisesRegex(ValueError, "cannot enter combat"):
                in_memory.claim(key, fixture.generation, 12345)
            if mode == "collaborative":
                with self.assertRaisesRegex(
                    RuntimeError, "rollback complete native action"
                ):
                    action(members[0], roll_back=True)
                with store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT count(*) AS n FROM environmental_monster_destructions WHERE instance_id=%s",
                            (event_id,),
                        ).fetchone()["n"],
                        0,
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                            key,
                        ).fetchone()["members"],
                        members,
                    )
                with self.assertRaises(ValueError):
                    action(members[0], loaded=False)
                with self.assertRaises(ValueError):
                    action(members[0], reach=lambda *_: False)
                # Lock ownership is a production precondition, never acquired
                # late behind environmental scope locks by the action itself.
                actual = approach(members[0])
                with store.connection() as db, self.assertRaisesRegex(
                    ValueError, "pre-held registry lock"
                ):
                    destroy.commit(
                        store,
                        db,
                        account,
                        fixture.generation,
                        actual,
                        struct.pack(">qq", members[0]["id"], 265),
                        groups=registry,
                        reachable=reachable,
                        loaded=True,
                        now_ms=int(fixture.clock[0] * 1000),
                    )
            receipt, changes = action(members[0])
            self.assertFalse(receipt["replayed"])
            self.assertTrue(changes)
            self.assertEqual(
                receipt["monster"],
                {
                    k: dict(members[0], map_id=327, instance_id=0)[k]
                    for k in (
                        "map_id",
                        "instance_id",
                        "id",
                        "ref",
                        "x",
                        "y",
                        "z",
                        "level",
                    )
                },
            )
            replay, changes = action(members[0])
            self.assertTrue(replay["replayed"])
            self.assertEqual(changes, ())
            with store.connection() as db:
                actual_event = dict(
                    db.execute(
                        "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()
                )
                for identity in (main, hero["id"]):
                    participant = dict(
                        db.execute(
                            "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
                            (event_id, identity),
                        ).fetchone()
                    )
                    self.assertEqual(
                        destroy.counters(db, actual_event, participant, "monster"),
                        (1, 1),
                    )
                    self.assertEqual(
                        destroy.counters(db, actual_event, participant, "group"), (0, 0)
                    )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_monster_destructions WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()["n"],
                    1,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_destroy_progress_facts WHERE instance_id=%s",
                        (event_id,),
                    ).fetchone()["n"],
                    2,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM character_achievement_events WHERE event_key LIKE 'fight:%'"
                    ).fetchone()["n"],
                    0,
                )
            if mode == "collaborative":
                other_account = store.register(
                    "native-destroy-foreign", "test-password"
                )["id"]
                other = store.create_character(other_account, "Foreign Destroy Owner")
                other_generation = store.begin_session(other_account)
                store.select_character(other_account, other_generation, other["id"])
                other_actual = approach(
                    members[0],
                    owner_account=other_account,
                    identity=other["id"],
                    generation=other_generation,
                )
                with registry.lock, store.connection() as db, self.assertRaisesRegex(
                    ValueError, "another owner/action"
                ):
                    destroy.commit(
                        store,
                        db,
                        other_account,
                        other_generation,
                        other_actual,
                        struct.pack(">qq", members[0]["id"], 265),
                        groups=registry,
                        reachable=reachable,
                        loaded=True,
                        now_ms=int(fixture.clock[0] * 1000),
                    )
                fixture.world.leave(other["id"], other_generation)
                self.assertGreaterEqual(len(members), 3)
                with registry.lock, store.connection() as db:
                    obsolete = tuple(
                        d
                        for d in publication.pending(
                            db,
                            map_id=327,
                            instance_id=0,
                            now_ms=int(fixture.clock[0] * 1000),
                        )
                        if d.instance_id == event_id
                    )
                action(members[1])
                with registry.lock, store.connection() as db:
                    self.assertEqual(
                        publication.acknowledge(
                            db,
                            map_id=327,
                            instance_id=0,
                            deliveries=obsolete,
                            now_ms=int(fixture.clock[0] * 1000),
                        ),
                        0,
                    )
                with patch.object(
                    fixture.world, "emit_location_batch", return_value=False
                ):
                    self.assertEqual(
                        publication.publish(
                            store,
                            fixture.world,
                            registry,
                            map_id=327,
                            instance_id=0,
                            now_ms=int(fixture.clock[0] * 1000),
                        ),
                        0,
                    )
                fixture.world.leave(main, fixture.generation)
                fixture.world.join(
                    fixture.generation, object(), store.character(account, main)
                )
                with registry.lock, store.connection() as db:
                    deliveries = publication.pending(
                        db,
                        map_id=327,
                        instance_id=0,
                        now_ms=int(fixture.clock[0] * 1000),
                    )
                    own = [d for d in deliveries if d.instance_id == event_id]
                    self.assertEqual(len(own), 2)
                    expected_remaining = {r["id"] for r in members[2:]}
                    for delivery in own:
                        # The native client resolves the still-registered actor
                        # prototype for cyl12421 before ctA12304 removes it.
                        # Loaded heroes receive credit, not extra action ACKs.
                        self.assertEqual(
                            [packet[0] for packet in delivery.packets],
                            [12421, 12304, 12608],
                        )
                        self.assertEqual(len(delivery.packets[0][1]), 24)
                        self.assertEqual(
                            struct.unpack(">qqq", delivery.packets[0][1]),
                            (delivery.monster_id, main, 265),
                        )
                        self.assertEqual(
                            struct.unpack_from(">q", delivery.packets[1][1], 4)[0],
                            delivery.monster_id,
                        )
                        opcode, body = delivery.packets[2]
                        self.assertEqual(opcode, 12608)
                        ids, cursor = set(), 2
                        for _ in range(body[1]):
                            kind, identity, length = struct.unpack_from(
                                ">BqH", body, cursor
                            )
                            self.assertEqual(kind, 1)
                            ids.add(identity)
                            cursor += 11 + length
                        self.assertEqual(cursor, len(body))
                        self.assertEqual(ids, expected_remaining)
                self.assertGreaterEqual(
                    publication.publish(
                        store,
                        fixture.world,
                        registry,
                        map_id=327,
                        instance_id=0,
                        now_ms=int(fixture.clock[0] * 1000),
                    ),
                    2,
                )
                with store.connection() as db:
                    with self.assertRaises(DatabaseError), db.transaction():
                        db.execute(
                            "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) VALUES(%s,%s,%s,%s,'available') ON CONFLICT DO NOTHING",
                            (*key, Jsonb(members)),
                        )
                for member in members[2:]:
                    action(member)
                with registry.lock, store.connection() as db:
                    final_deliveries = [
                        d
                        for d in publication.pending(
                            db,
                            map_id=327,
                            instance_id=0,
                            now_ms=int(fixture.clock[0] * 1000),
                        )
                        if d.instance_id == event_id
                    ]
                    self.assertEqual(
                        {d.monster_id for d in final_deliveries},
                        {m["id"] for m in members[2:]},
                    )
                    for delivery in final_deliveries:
                        self.assertEqual(
                            [packet[0] for packet in delivery.packets], [12421, 12304]
                        )
                        self.assertEqual(
                            struct.unpack(">qqq", delivery.packets[0][1]),
                            (delivery.monster_id, main, 265),
                        )
                    for identity in (main, hero["id"]):
                        participant = dict(
                            db.execute(
                                "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
                                (event_id, identity),
                            ).fetchone()
                        )
                        self.assertEqual(
                            destroy.counters(db, event, participant, "monster"),
                            (len(members), len(members)),
                        )
                        self.assertEqual(
                            destroy.counters(db, event, participant, "group"), (1, 1)
                        )
                    self.assertEqual(
                        db.execute(
                            "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                            key,
                        ).fetchone(),
                        dict(members=[], status="defeated"),
                    )
            with store.connection() as db:
                storage.cancel(
                    db,
                    event_id,
                    reason="finite native action component finished",
                    now_ms=int(fixture.clock[0] * 1000),
                )
                population.cleanup(
                    db, map_id=327, instance_id=0, now_ms=int(fixture.clock[0] * 1000)
                )
                self.assertEqual(
                    dict(
                        db.execute(
                            "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                            ordinary_key,
                        ).fetchone()
                    ),
                    ordinary_before,
                )
            fixture.clock[0] = (event["deadline_ms"] + 1) / 1000
