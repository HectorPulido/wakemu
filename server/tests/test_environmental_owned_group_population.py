"""Real PersistentGroups ownership, no partial spawn, lease-safe cleanup/replay."""
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import native_catalog
from wakfu_server.world import World
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.planting_cells import cells
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.objectives import environmental_group_population as population
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage


class EnvironmentalOwnedGroupPopulationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        with self.store.connection() as db:
            if (
                db.execute(
                    "SELECT to_regclass('environmental_owned_groups') AS t"
                ).fetchone()["t"]
                is None
            ):
                db.execute(
                    (
                        Path(__file__).parents[1]
                        / "migrations/283_environmental_owned_group_population.sql"
                    ).read_text(),
                    prepare=False,
                )
        self.account = self.store.register(
            "environmental-owned-group", "test-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Owned Group Tester")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.points = list(
            dict.fromkeys(
                (x, y, row["z"])
                for (x, y), rows in cells(1134).items()
                for row in rows
                if row["region_id"] == 79001
            )
        )[:8]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=17,x=%s,y=%s,z=%s WHERE id=%s",
                (*self.points[-1], self.character["id"]),
            )
        self.character = self.store.character(self.account, self.character["id"])
        self.world = World(lambda _: b"", lambda _: b"", lambda *_: None)
        self.world.join(self.generation, object(), self.character)
        self.enterContext(patch.object(presence, "_world", self.world))
        self.groups = PersistentGroups(self.store)
        self.now = int(self.store.clock() * 1000)

    def profile(self, *, reference=5838):
        self.reference = reference
        level = REFERENCES[reference]["min_level"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES('owned-group',1,-2288,'group_defeat','solo',1134,79001,60000,%s,1,245,'test-only explicit Wakemu placement and quantity',%s,%s)",
                (self.now - 1000, "0" * 64, native_catalog.release()),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES('owned-group',1,'win','group_defeat',2643,NULL,NULL,'interaction',1)"
            )
            db.execute(
                "INSERT INTO environmental_profile_group_composition VALUES('owned-group',1,2643,%s,2,'test-only Wakemu quantity; not type74')",
                (reference,),
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES('owned-group',1,0,'xp',NULL,100,'test-only')"
            )
            db.execute(
                "INSERT INTO environmental_profile_group_population VALUES('owned-group',1,'installed-environmental-source-v1',-2288,'wakemu.explicit-native-breed-roster.v1','test-only Wakemu roster')"
            )
            for index, point in enumerate(self.points[:2]):
                db.execute(
                    "INSERT INTO environmental_profile_group_cells VALUES('owned-group',1,0,%s,2643,%s,%s,%s,%s,%s)",
                    (index, reference, level, *point),
                )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='owned-group'"
            )
        result = service.refresh(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            location=dict(map_id=1134, instance_id=17, region_id=79001),
            now_ms=self.now,
        )
        with self.store.connection() as db:
            return dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (result["instances"][0]["instance_id"],),
                ).fetchone()
            )

    def test_real_atomic_owned_group_replay_lease_guard_and_foreign_group_preservation(
        self,
    ):
        event = self.profile()
        foreign = [
            owned_instance(
                5008,
                REFERENCES[5008]["min_level"],
                -990000,
                map_id=1134,
                instance_id=17,
                x=self.points[3][0],
                y=self.points[3][1],
                z=self.points[3][2],
            )
        ]
        self.groups.register(1134, 17, 990000, foreign)
        with self.store.connection() as db:
            keys = population.populate(db, event, self.groups, now_ms=self.now)
            self.assertEqual(len(keys), 1)
            self.assertEqual(
                population.populate(db, event, self.groups, now_ms=self.now), ()
            )
            owned = db.execute(
                "SELECT * FROM environmental_event_memberships WHERE instance_id=%s",
                (event["instance_id"],),
            ).fetchall()
            self.assertEqual(len(owned), 1)
            self.assertTrue(owned[0]["spawn_owned"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_group_members"
                ).fetchone()["n"],
                2,
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
            ).fetchone()["id"]
        lease, members = self.groups.claim(keys[0], self.generation, fight_id)
        with self.store.connection() as db:
            storage.cancel(
                db, event["instance_id"], reason="fixture expiry", now_ms=self.now + 1
            )
            self.assertEqual(
                population.cleanup(
                    db, map_id=1134, instance_id=17, now_ms=self.now + 2
                ),
                (),
            )
        self.groups.finish(lease, defeated=False)
        with self.store.connection() as db:
            self.assertEqual(
                population.cleanup(
                    db, map_id=1134, instance_id=17, now_ms=self.now + 3
                ),
                keys,
            )
            self.assertEqual(
                population.cleanup(
                    db, map_id=1134, instance_id=17, now_ms=self.now + 4
                ),
                (),
            )
            self.assertEqual(
                db.execute(
                    "SELECT members FROM combat_groups WHERE group_id=990000"
                ).fetchone()["members"],
                foreign,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_group_publications WHERE kind='despawn'"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_cleanup_outbox WHERE completed_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )

    def test_occupied_cell_and_failed_outer_publication_rollback_create_no_partial_population(
        self,
    ):
        event = self.profile()
        point = self.points[0]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources VALUES(990001,1134,17,%s,%s,%s,60,2,100)",
                point,
            )
            self.assertEqual(
                population.populate(db, event, self.groups, now_ms=self.now), ()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_groups"
                ).fetchone()["n"],
                0,
            )
            db.execute("DELETE FROM planted_resources WHERE resource_uid=990001")
        with self.assertRaisesRegex(ValueError, "publication"):
            with self.store.connection() as db:
                self.assertEqual(
                    len(population.populate(db, event, self.groups, now_ms=self.now)), 1
                )
                raise ValueError("failed publication preparation")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_groups"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM combat_groups").fetchone()["n"], 0
            )

    def test_non_source_breed_and_vacant_scope_cannot_spawn(self):
        event = self.profile(reference=5008)
        with self.store.connection() as db:
            with self.assertRaisesRegex(ValueError, "positive original breed"):
                population.populate(db, event, self.groups, now_ms=self.now)
        self.world.leave(self.character["id"], self.generation)
        with self.store.connection() as db:
            self.assertEqual(
                population.populate(db, event, self.groups, now_ms=self.now), ()
            )

    def test_busy_native_population_lock_skips_birth_and_cleanup_without_waiting(self):
        event = self.profile()
        with self.store.connection() as busy:
            busy.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended('monster-population:1134:17',0))"
            )
            with self.store.connection() as db:
                db.execute("SET LOCAL lock_timeout='750ms'")
                self.assertEqual(
                    population.populate(db, event, self.groups, now_ms=self.now), ()
                )
                self.assertEqual(
                    population.cleanup(
                        db, map_id=1134, instance_id=17, now_ms=self.now
                    ),
                    (),
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_owned_groups"
                    ).fetchone()["n"],
                    0,
                )
        with self.store.connection() as db:
            self.assertEqual(
                len(population.populate(db, event, self.groups, now_ms=self.now)), 1
            )

    def test_native_publication_defers_claimed_group_and_requires_all_map_peers_before_ack(
        self,
    ):
        from types import SimpleNamespace
        from wakfu_server.objectives import (
            environmental_group_publication as publication,
        )

        event = self.profile()
        with self.store.connection() as db:
            keys = population.populate(db, event, self.groups, now_ms=self.now)
            prepared = publication.pending(
                db, map_id=1134, instance_id=17, now_ms=self.now
            )
            self.assertEqual(len(prepared), 1)
            self.assertEqual(prepared[0].packets[0][0], 12608)
            self.assertEqual(prepared[0].packets[0][1][:2], b"\x00\x02")
            self.assertEqual(
                publication.acknowledge(
                    db,
                    map_id=1134,
                    instance_id=18,
                    deliveries=prepared,
                    now_ms=self.now,
                ),
                0,
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
            ).fetchone()["id"]
        lease, _ = self.groups.claim(keys[0], self.generation, fight_id)
        self.assertEqual(
            publication.publish(
                self.store,
                self.world,
                self.groups,
                map_id=1134,
                instance_id=17,
                now_ms=self.now,
            ),
            0,
        )
        self.groups.finish(lease, defeated=False)
        good, bad = SimpleNamespace(shutdown=lambda *_: None), SimpleNamespace(
            shutdown=lambda *_: None
        )
        self.world.join(self.generation, good, self.character)
        account = self.store.register("environmental-second-peer", "test-password")[
            "id"
        ]
        other = self.store.create_character(account, "Second Group Viewer")
        other = dict(
            other,
            map_id=1134,
            instance_id=17,
            x=self.points[-2][0],
            y=self.points[-2][1],
            z=self.points[-2][2],
        )
        self.world.join("second-peer", bad, other)
        received = []

        def partial(peer, packets):
            if peer is bad:
                raise OSError("one map peer failed")
            received.append(packets)

        self.world.deliver_batch = partial
        with self.assertRaisesRegex(OSError, "unpublished recipients"):
            publication.publish(
                self.store,
                self.world,
                self.groups,
                map_id=1134,
                instance_id=17,
                now_ms=self.now,
            )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT published_at_ms FROM environmental_group_publications WHERE kind='spawn'"
                ).fetchone()["published_at_ms"]
            )
        self.world.deliver_batch = lambda peer, packets: received.append(packets)
        self.assertEqual(
            publication.publish(
                self.store,
                self.world,
                self.groups,
                map_id=1134,
                instance_id=17,
                now_ms=self.now + 1,
            ),
            1,
        )
        self.assertEqual(
            publication.publish(
                self.store,
                self.world,
                self.groups,
                map_id=1134,
                instance_id=17,
                now_ms=self.now + 2,
            ),
            0,
        )
        with self.store.connection() as db:
            storage.cancel(
                db,
                event["instance_id"],
                reason="fixture publication end",
                now_ms=self.now + 3,
            )
            self.assertEqual(
                population.cleanup(
                    db, map_id=1134, instance_id=17, now_ms=self.now + 4
                ),
                keys,
            )
        self.assertEqual(
            publication.publish(
                self.store,
                self.world,
                self.groups,
                map_id=1134,
                instance_id=17,
                now_ms=self.now + 5,
            ),
            1,
        )
        self.assertEqual(received[-1][0][0], 12304)

    def test_sealed_population_cells_cannot_move_to_an_unsealed_profile(self):
        self.profile()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES('unsealed-target',1,-2288,'group_defeat','solo',1134,79001,60000,%s,1,245,'test-only',%s,%s)",
                (self.now - 1000, "0" * 64, native_catalog.release()),
            )
            db.execute(
                "INSERT INTO environmental_profile_group_composition VALUES('unsealed-target',1,2643,5838,2,'test-only')"
            )
            db.execute(
                "INSERT INTO environmental_profile_group_population VALUES('unsealed-target',1,'installed-environmental-source-v1',-2288,'wakemu.explicit-native-breed-roster.v1','test-only')"
            )
        with self.assertRaisesRegex(
            Exception, "Sealed environmental group population policy"
        ):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE environmental_profile_group_cells SET profile_key='unsealed-target' WHERE profile_key='owned-group'"
                )

    def test_selected_service_spawns_and_retires_owned_groups_with_real_scope_socket_retry_and_wild_preservation(
        self,
    ):
        from types import SimpleNamespace
        from wakfu_server.objectives.environmental_world import (
            SelectedEnvironmentalEvents,
        )

        event = (
            self.profile()
        )  # Native profile admitted; groups=None creates no population.
        foreign = [
            owned_instance(
                5008,
                REFERENCES[5008]["min_level"],
                -990000,
                map_id=1134,
                instance_id=17,
                x=self.points[3][0],
                y=self.points[3][1],
                z=self.points[3][2],
            )
        ]
        self.groups.register(1134, 17, 990000, foreign)
        good, bad, outside = (
            SimpleNamespace(shutdown=lambda *_: None) for _ in range(3)
        )
        self.world.join(self.generation, good, self.character)
        other_account = self.store.register(
            "environmental-selected-peer", "test-password"
        )["id"]
        other = self.store.create_character(other_account, "Selected Group Viewer")
        other = dict(
            other,
            map_id=1134,
            instance_id=17,
            x=self.points[-2][0],
            y=self.points[-2][1],
            z=self.points[-2][2],
        )
        self.world.join("selected-peer", bad, other)
        outside_account = self.store.register(
            "environmental-outside-peer", "test-password"
        )["id"]
        outsider = self.store.create_character(outside_account, "Other Group Scope")
        outsider = dict(
            outsider,
            map_id=1134,
            instance_id=18,
            x=self.points[-2][0],
            y=self.points[-2][1],
            z=self.points[-2][2],
        )
        self.world.join("outside-peer", outside, outsider)
        location = dict(map_id=1134, instance_id=17, region_id=79001)
        connection = SelectedEnvironmentalEvents(groups=self.groups)
        checkpoints, received = [], []

        def refresh(now, *, ready=True):
            return connection.refresh(
                self.store,
                self.world,
                self.account,
                self.generation,
                self.character["id"],
                location=location,
                ready=ready,
                checkpoint=lambda: checkpoints.append(1),
                now_ms=now,
            )

        def partial(peer, packets):
            if peer is bad:
                raise OSError("selected group map peer unavailable")
            received.append((peer, packets))

        self.world.deliver_batch = partial
        self.assertFalse(refresh(self.now, ready=False))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_groups"
                ).fetchone()["n"],
                0,
            )
        with self.assertRaisesRegex(OSError, "unpublished recipients"):
            refresh(self.now)
        with self.store.connection() as db:
            owned = db.execute("SELECT * FROM environmental_owned_groups").fetchall()
            self.assertEqual(len(owned), 1)
            self.assertIsNone(
                db.execute(
                    "SELECT published_at_ms FROM environmental_group_publications WHERE kind='spawn'"
                ).fetchone()["published_at_ms"]
            )
            member_ids = {
                row["monster_id"]
                for row in db.execute(
                    "SELECT monster_id FROM environmental_owned_group_members"
                ).fetchall()
            }
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM combat_groups").fetchone()["n"], 2
            )
        self.world.deliver_batch = lambda peer, packets: received.append(
            (peer, packets)
        )
        self.assertTrue(refresh(self.now + 1))
        self.assertTrue(
            any(opcode == 12608 for peer, packets in received for opcode, _ in packets)
        )
        self.assertFalse(any(peer is outside for peer, _ in received))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_group_publications WHERE kind='spawn' AND published_at_ms IS NOT NULL"
                ).fetchone()["n"],
                1,
            )
        prior = len(received)
        refresh(self.now + 2)
        self.assertEqual(len(received), prior)
        with self.store.connection() as db:
            storage.cancel(
                db,
                event["instance_id"],
                reason="selected component complete",
                now_ms=self.now + 3,
            )
        self.assertTrue(refresh(self.now + 4))
        removals = [
            body
            for peer, packets in received
            for opcode, body in packets
            if opcode == 12304
        ]
        self.assertEqual(len(removals), 2)  # One native batch per actual map peer.
        import struct

        expected_removal_ids = member_ids
        for body in removals:
            self.assertEqual(body[:3], bytes((0, 0, 2)))
            self.assertEqual(
                {
                    struct.unpack_from(">q", body, 4 + 9 * index)[0]
                    for index in range(2)
                },
                expected_removal_ids,
            )
        with self.store.connection() as db:
            remaining = db.execute(
                "SELECT group_id,members FROM combat_groups"
            ).fetchall()
            self.assertEqual(
                [(row["group_id"], row["members"]) for row in remaining],
                [(990000, foreign)],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_group_publications WHERE published_at_ms IS NOT NULL"
                ).fetchone()["n"],
                2,
            )
        prior = len(received)
        refresh(self.now + 5)
        self.assertEqual(len(received), prior)
        self.world.leave(self.character["id"], self.generation)
        self.world.leave(other["id"], "selected-peer")
        self.assertFalse(
            refresh(self.now + 6)
        )  # Other world-instance occupancy is insufficient.
        self.assertEqual(len(received), prior)
