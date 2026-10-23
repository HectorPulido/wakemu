"""Native event resources use real occupations and preserve unrelated crops."""
from contextlib import contextmanager
from types import SimpleNamespace
import struct
from unittest.mock import Mock, patch

from postgres_case import PostgresCase
from wakfu_server import health_store, resource_collect, native_catalog
from wakfu_server.planting_cells import cells
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.world import World
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives import environmental_resource_population as population
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents


class EnvironmentalOwnedResourcePopulationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [self.store.clock()]
        self.store.clock = lambda: self.clock[0]
        self.account = self.store.register(
            "environmental-native-resource", "test-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Resource Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.points = [
            (x, y, r["z"])
            for (x, y), rows in cells(327).items()
            for r in rows
            if r["region_id"] == 56601
        ]
        self.points = list(dict.fromkeys(self.points))
        self.assertGreater(len(self.points), 200)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=81,map_id=327,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (*self.points[-1], self.character["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[81], self.character["id"]),
            )
        self.character = health_store.initialize(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.batches = []
        self.world = World(
            lambda _: b"",
            lambda _: b"",
            lambda *_: True,
            deliver_batch=lambda peer, packets: self.batches.append(packets) or True,
        )
        self.world.join(
            self.generation, SimpleNamespace(shutdown=lambda *_: None), self.character
        )
        live = patch.object(presence, "_world", self.world)
        live.start()
        self.addCleanup(live.stop)
        self.location = dict(map_id=327, instance_id=0, region_id=56601)
        self.now_ms = int(self.clock[0] * 1000)

    def profile(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES('owned-resource',1,-1320,'resource_collect','collaborative',327,56601,900000,%s,81,245,'test-only completion target',%s,%s)",
                (self.now_ms - 1000, "0" * 64, native_catalog.release()),
            )
            # Bounded fixture completion target2; original scenario population
            # size100 and its original resource/action/location are unchanged.
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES('owned-resource',1,'collect','resource_collect',478,1190,2,'interaction',2)"
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES('owned-resource',1,0,'xp',NULL,100,'test-only')"
            )
            db.execute(
                "INSERT INTO environmental_profile_resource_population VALUES('owned-resource',1,'installed-environmental-source-v1',"
                "'declared_native_cells','catalog_cvF','test-only reconstructed placement policy')"
            )
            for ordinal, point in enumerate(self.points[:200]):
                db.execute(
                    "INSERT INTO environmental_profile_resource_cells VALUES('owned-resource',1,%s,%s,%s,%s)",
                    (ordinal, *point),
                )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='owned-resource'"
            )

    def refresh(self):
        return service.refresh(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            location=self.location,
            now_ms=int(self.clock[0] * 1000),
        )

    def insert(self, uid, point, *, reference=60, creation_time=100):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources VALUES(%s,327,0,%s,%s,%s,%s,2,%s)",
                (uid, *point, reference, creation_time),
            )

    def ticket(self, resource):
        from wakfu_server.wire import proto_field

        unsigned = lambda v: v if v >= 0 else v + (1 << 64)
        body = (
            proto_field(8, 1190)
            + proto_field(16, unsigned(resource["x"]))
            + proto_field(24, unsigned(resource["y"]))
        )
        prepared = resource_collect.prepare(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            body,
            reachable=lambda *_: True,
        )
        return resource_collect.reserve(
            self.store, self.account, self.generation, prepared
        )

    def test_original_population_real_profession_zero_occupation_and_atomic_cleanup(
        self,
    ):
        self.insert(990001, self.points[0])
        self.insert(990002, self.points[1], reference=478)
        self.profile()
        original_connection = self.store.connection

        @contextmanager
        def bounded_connection():
            with original_connection() as db:
                db.execute("SET LOCAL lock_timeout='750ms'")
                yield db

        with original_connection() as busy:
            key = "planting-cell:327:0:" + ":".join(map(str, self.points[2][:2]))
            busy.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (key,))
            with patch.object(self.store, "connection", side_effect=bounded_connection):
                first = self.refresh()
        event = first["instances"][0]["instance_id"]
        with self.store.connection() as db:
            resources = db.execute(
                "SELECT p.* FROM planted_resources p JOIN environmental_owned_resources r USING(resource_uid) ORDER BY resource_uid"
            ).fetchall()
            self.assertEqual(len(resources), 100)
            self.assertNotIn(self.points[2][:2], [(r["x"], r["y"]) for r in resources])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_resource_publications"
                ).fetchone()["n"],
                100,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM planted_resources").fetchone()[
                    "n"
                ],
                102,
            )
            foreign = dict(
                db.execute(
                    "SELECT * FROM planted_resources WHERE resource_uid=990002"
                ).fetchone()
            )
        with self.assertRaisesRegex(ValueError, "eligible owned"):
            self.ticket(foreign)
        self.assertEqual(len(first["resource_publications"]), 100)
        connection = SelectedEnvironmentalEvents()
        self.world.deliver_batch = Mock(side_effect=OSError("injected socket failure"))
        with self.assertRaises(OSError):
            connection.refresh(
                self.store,
                self.world,
                self.account,
                self.generation,
                self.character["id"],
                location=self.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=self.now_ms,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_resource_publications WHERE published_at_ms IS NULL"
                ).fetchone()["n"],
                100,
            )
        self.world.deliver_batch = (
            lambda peer, packets: self.batches.append(packets) or True
        )
        self.assertTrue(
            connection.refresh(
                self.store,
                self.world,
                self.account,
                self.generation,
                self.character["id"],
                location=self.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=self.now_ms,
            )
        )
        self.assertEqual([opcode for opcode, _ in self.batches[-1]], [13135] * 100)
        self.assertEqual(len(self.refresh()["resource_publications"]), 0)
        for index, resource in enumerate(resources[:2]):
            ticket = self.ticket(dict(resource))
            with self.assertRaises(ValueError):
                resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
            self.clock[0] += 5
            result = resource_collect.complete(
                self.store, ticket, struct.pack(">Bh", 2, 3)
            )
            self.assertTrue(result["applied"])
            self.assertTrue(result["environmental_owned_publication"])
            self.assertEqual(
                (
                    result["outcome"]["xp"],
                    result["outcome"]["quantity"],
                    result["outcome"]["ecology"],
                ),
                (0, 0, {}),
            )
            self.assertEqual(result["world_packets"], [])
            self.assertFalse(
                resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))[
                    "applied"
                ]
            )
        final = self.refresh()
        self.assertEqual(len(final["rewards"]["delivered"]), 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM planted_resources").fetchone()[
                    "n"
                ],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_resources WHERE retired_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_harvest_receipts"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM account_professions WHERE profession_id=0"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                storage._progress(db, dict(instance_id=event)), {"collect": 2}
            )
        self.assertEqual(self.refresh()["rewards"]["delivered"], [])

    def test_terminal_cleanup_preserves_foreign_replacement_and_vacant_scope_performs_no_work(
        self,
    ):
        self.profile()
        first = self.refresh()
        event = first["instances"][0]["instance_id"]
        with self.store.connection() as db:
            owned = dict(
                db.execute(
                    "SELECT * FROM environmental_owned_resources LIMIT 1"
                ).fetchone()
            )
            storage.cancel(db, event, reason="test controller", now_ms=self.now_ms + 1)
            db.execute(
                "UPDATE planted_resources SET creation_time=creation_time+1 WHERE resource_uid=%s",
                (owned["resource_uid"],),
            )
            with self.assertRaisesRegex(
                ValueError, "identity changed"
            ), db.transaction():
                population.cleanup(
                    db, map_id=327, instance_id=0, now_ms=self.now_ms + 1
                )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_resources WHERE retired_at_ms IS NOT NULL"
                ).fetchone()["n"],
                0,
            )
            db.execute(
                "DELETE FROM planted_resources WHERE resource_uid=%s",
                (owned["resource_uid"],),
            )
            db.execute(
                "INSERT INTO planted_resources VALUES(990003,327,0,%s,%s,%s,60,2,100)",
                (owned["x"], owned["y"], owned["z"]),
            )
        self.world.leave(self.character["id"], self.generation)
        db = Mock()
        self.assertEqual(
            population.cleanup(db, map_id=327, instance_id=0, now_ms=self.now_ms + 2),
            (),
        )
        self.assertEqual(
            population.pending_publications(
                db, map_id=327, instance_id=0, now_ms=self.now_ms + 2
            ),
            (),
        )
        db.execute.assert_not_called()
        self.world.join(self.generation, object(), self.character)
        cleaned = self.refresh()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT resource_uid FROM planted_resources").fetchone()[
                    "resource_uid"
                ],
                990003,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_resources WHERE retired_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(len(cleaned["resource_publications"]), 99)
        self.assertTrue(
            all(
                opcode == 12782
                for r in cleaned["resource_publications"]
                for opcode, _ in r["packets"]
            )
        )
        resumed = self.refresh()["instances"]
        self.assertEqual(
            [(r["instance_id"], r["state"]) for r in resumed], [(event, "cancelled")]
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_resources"
                ).fetchone()["n"],
                100,
            )

    def test_ordinary_growth_excludes_event_resources_but_keeps_player_crop_growth(
        self,
    ):
        from wakfu_server.planting_runtime import Plantings

        self.profile()
        self.refresh()
        self.insert(990004, self.points[-2], creation_time=self.now_ms - 60000)
        with self.store.connection() as db:
            # Deliberately due ordinary transition: event resources must never
            # enter this scheduler, even if an overlapping policy is installed.
            db.execute(
                "INSERT INTO resource_growth_transitions "
                "(resource_reference,from_stage,to_stage,delay_ms,probability) "
                "VALUES(478,2,3,1000,1) ON CONFLICT(resource_reference,from_stage) "
                "DO UPDATE SET delay_ms=1000,probability=1"
            )
        self.clock[0] += 2
        runtime = Plantings(self.store)
        with patch("wakfu_server.mining_veins.refill"), patch(
            "wakfu_server.fishing_spots.refill"
        ):
            runtime.mature(Mock(), publish=lambda *args: True, random_draw=lambda: 0)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planted_resources p "
                    "JOIN environmental_owned_resources e USING(resource_uid) WHERE p.stage=2"
                ).fetchone()["n"],
                100,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM resource_growth_decisions d "
                    "JOIN environmental_owned_resources e USING(resource_uid)"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT stage FROM planted_resources WHERE resource_uid=990004"
                ).fetchone()["stage"],
                3,
            )
