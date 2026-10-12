import struct
import threading
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from postgres_case import PostgresCase
from psycopg.errors import RaiseException
from psycopg.types.json import Jsonb
from wakfu_server import personal_ecology, wire, planting, resource_collect
from wakfu_server.inventory_items import grant
from wakfu_server.planting import RESOURCES, SEEDS
from wakfu_server.planting_cells import cells
from wakfu_server.world import World
from wakfu_server.mount_publication import snapshot as mount_snapshot
from wakfu_server.personal_ecology import snapshot as ecology_snapshot
from wakfu_server.profession_store import ensure_learned
from wakfu_server.profession_wire import MAX_XP
from wakfu_server.characters.ecology_progression import native_score
from wakfu_server.ecology_feedback import information


class FloraEcologyIntegrationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.native_wish = dict(family_id=10, minimum=300, maximum=300)
        self.native_catalog = {
            "territories": {
                "79001": dict(
                    map_id=1134, plant_wishes=[self.native_wish], monster_wishes=[]
                )
            }
        }
        native = patch(
            "wakfu_server.ecology_equilibrium.catalog", return_value=self.native_catalog
        )
        native.start()
        self.addCleanup(native.stop)
        self.clock = [1_700_000_000.0]
        self.store.clock = lambda: self.clock[0]
        self.account = self.store.register("flora-ecology", "test-password")["id"]
        self.character = self.store.create_character(self.account, "Flora Ecology")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        # This fixture uses real exported surfaces and region IDs. Ground checks
        # are relaxed explicitly through the planting test policy.
        self.map_id = 1134
        self.instance_id = 17
        self.region_id = 79001
        unique = {}
        for (x, y), rows in cells(self.map_id).items():
            for row in rows:
                if row["region_id"] == self.region_id:
                    unique.setdefault((x, y), row["z"])
        self.region_cells = [(x, y, z) for (x, y), z in unique.items()]
        self.assertGreater(len(self.region_cells), 302)
        start = self.region_cells[-1]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (self.map_id, self.instance_id, *start, self.character["id"]),
            )
        self.character = self.store.character(self.account, self.character["id"])

        self.seed_item = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=4275,
            quantity=10,
            container=self.character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )
        ensure_learned(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            [72],
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=%s WHERE account_id=%s AND profession_id=72",
                (123, self.account),
            )

    def _insert_plants(self, count):
        with self.store.connection() as db:
            for index, (x, y, z) in enumerate(self.region_cells[:count]):
                db.execute(
                    "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                    "resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,60,2,0)",
                    (1_000_000 + index, self.map_id, self.instance_id, x, y, z),
                )

    def _insert_resource(self, point, *, resource_uid, stage, reference=60):
        x, y, z = point
        resource = dict(
            resource_uid=resource_uid,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=x,
            y=y,
            z=z,
            resource_reference=reference,
            stage=stage,
            creation_time=100,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
        return resource

    def _prepare_plant(self, point, *, native=True):
        x, y, _z = point

        def authorize(_character, request, _seed, _resource):
            if not native:
                return 0
            return next(
                row["z"]
                for row in cells(self.map_id)[(request["x"], request["y"])]
                if row["region_id"] == self.region_id
            )

        body = struct.pack(
            ">iqii", SEEDS[4275]["action_id"], self.seed_item["uid"], x, y
        )
        return planting.prepare(
            self.store,
            self.account,
            self.generation,
            self.character,
            body,
            authorize_cell=authorize,
            open_test_policy=True,
        )

    def _plant(self, prepared, operation_id, *, success=True):
        return planting.complete(
            self.store,
            self.account,
            self.generation,
            prepared,
            operation_id=operation_id,
            stage=2,
            creation_time=int(self.clock[0] * 1000),
            result_prefix=(0, 1),
            success=success,
        )

    def _resource_ticket(self, resource, action_id):
        def unsigned(value):
            return value if value >= 0 else value + (1 << 64)

        body = (
            wire.proto_field(8, action_id)
            + wire.proto_field(16, unsigned(resource["x"]))
            + wire.proto_field(24, unsigned(resource["y"]))
        )
        prepared = resource_collect.prepare(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            body,
            reachable=lambda _actor, _target: True,
        )
        return resource_collect.reserve(
            self.store, self.account, self.generation, prepared
        )

    def _advance_harvest(self):
        self.clock[0] += 4

    def _ecology(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
                (self.character["id"],),
            ).fetchone()

    def _install_ecology_failure(self):
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_flora_ecology() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'forced flora ecology receipt failure'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_flora_ecology BEFORE INSERT ON personal_ecology_receipts "
                "FOR EACH ROW EXECUTE FUNCTION reject_flora_ecology()"
            )

    def test_plant_improving_population_balance_then_worsening_population_stasis(self):
        # Start one below the singleton native band. The first planting moves
        # toward it; the second leaves it and must apply Stasis.
        self._insert_plants(299)
        first = self._prepare_plant(self.region_cells[300])
        first_result = self._plant(first, "flora-boundary-one")
        first_ecology = next(
            (body for opcode, body in first_result["packets"] if opcode == 13574), None
        )
        self.assertEqual(
            struct.unpack(">qi", first_ecology),
            (self.character["id"], native_score(25)),
        )
        self.assertEqual(1, sum(opcode == 349 for opcode, _ in first_result["packets"]))
        first_receipt = first_result["ecology"]["receipt"]
        self.assertEqual(
            (299, 300, 300, 300),
            tuple(
                first_receipt["evidence"][key]
                for key in (
                    "before_population",
                    "after_population",
                    "minimum",
                    "maximum",
                )
            ),
        )
        self.assertEqual(1, first_receipt["revision"])

        # Replaying the same planting receipt cannot change personal ecology or
        # emit another action delta.
        replay = self._plant(first, "flora-boundary-one")
        self.assertTrue(replay["duplicate"])
        self.assertEqual([], replay["packets"])
        self.assertEqual(
            {"ecology_value": 25, "ecology_revision": 1}, dict(self._ecology())
        )

        second = self._prepare_plant(self.region_cells[301])
        second_result = self._plant(second, "flora-boundary-two")
        second_ecology = next(
            body for opcode, body in second_result["packets"] if opcode == 13574
        )
        self.assertEqual(
            struct.unpack(">qi", second_ecology), (self.character["id"], 0)
        )
        self.assertEqual(
            300, second_result["ecology"]["receipt"]["evidence"]["before_population"]
        )
        self.assertEqual(-25, second_result["ecology"]["receipt"]["requested_delta"])
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 2}, dict(self._ecology())
        )

    def test_failed_plant_consumes_seed_but_grants_no_ecology_or_profession_xp(self):
        prepared = self._prepare_plant(self.region_cells[300])
        result = self._plant(prepared, "flora-failed", success=False)
        self.assertFalse(result["success"])
        self.assertEqual("planting_failed", result["ecology"]["reason"])
        self.assertEqual(1, sum(opcode == 349 for opcode, _ in result["packets"]))
        self.assertNotIn(13574, [opcode for opcode, _ in result["packets"]])
        character = self.store.character(self.account, self.character["id"])
        seed_stack = next(
            i for i in character["inventory_items"] if i["uid"] == self.seed_item["uid"]
        )
        self.assertEqual(9, seed_stack["quantity"])
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute("SELECT count(*) AS n FROM planted_resources").fetchone()[
                    "n"
                ],
            )
            xp = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                (self.account,),
            ).fetchone()["xp"]
        self.assertEqual(123, xp)
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._ecology())
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["n"],
            )

    def test_unknown_native_surface_fails_closed_without_invented_ecology_reward(self):
        prepared = self._prepare_plant((100_000, 100_001, 0), native=False)
        result = self._plant(prepared, "flora-unknown-surface")
        self.assertTrue(result["success"])
        self.assertEqual("native_region_unavailable", result["ecology"]["reason"])
        self.assertEqual(
            [packet for packet in result["packets"] if packet[0] == 349],
            [
                information(
                    "Ecosistema: región del recurso no disponible; "
                    "no se aplica un cambio de afinidad sin esos datos."
                )
            ],
        )
        self.assertNotIn(13574, [opcode for opcode, _ in result["packets"]])
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._ecology())
        )
        self.assertIsNotNone(result["resource"])
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["n"],
            )

    def test_incomplete_native_population_explains_no_affinity_packet_without_receipt(
        self,
    ):
        self._insert_resource((100_000, 100_001, 0), resource_uid=700_009, stage=2)
        prepared = self._prepare_plant(self.region_cells[0])
        result = self._plant(prepared, "flora-incomplete-population")
        self.assertEqual("incomplete_native_population", result["ecology"]["reason"])
        self.assertEqual(
            [packet for packet in result["packets"] if packet[0] == 349],
            [
                information(
                    "Ecosistema: población regional incompleta; "
                    "no se aplica un cambio de afinidad sin esos datos."
                )
            ],
        )
        self.assertNotIn(13574, [opcode for opcode, _ in result["packets"]])
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._ecology())
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["n"],
            )

    def test_harvest_removal_below_native_minimum_awards_stasis_and_freezes_metadata(
        self,
    ):
        self._insert_plants(298)
        target = self._insert_resource(
            self.region_cells[298], resource_uid=700_001, stage=3
        )
        ticket = self._resource_ticket(target, 203)
        self._advance_harvest()
        result = resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        packet = next(body for opcode, body in result["packets"] if opcode == 13574)
        self.assertEqual(
            struct.unpack(">qi", packet), (self.character["id"], native_score(-25))
        )
        metadata = result["outcome"]["ecology"]
        receipt = metadata["receipt"]
        self.assertEqual("native_chief_wish", receipt["evidence"]["limit_source"])
        self.assertEqual(
            (299, 298, 300),
            tuple(
                receipt["evidence"][key]
                for key in ("before_population", "after_population", "minimum")
            ),
        )
        self.assertEqual(-25, receipt["requested_delta"])
        self.assertNotIn("packets", metadata)
        self.assertNotIn("packet", receipt)
        saved = self.store.connection
        with saved() as db:
            stored = db.execute(
                "SELECT result FROM resource_harvest_receipts WHERE token=%s",
                (ticket["token"],),
            ).fetchone()["result"]
            self.assertEqual(metadata, stored["ecology"])
        replay = resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertFalse(replay["applied"])
        self.assertEqual([], replay["packets"])
        self.assertEqual(
            {"ecology_value": -25, "ecology_revision": 1}, dict(self._ecology())
        )

    def test_nonremoving_harvest_records_neutral_ecology_and_emits_one_owner_info(self):
        target = self._insert_resource(
            self.region_cells[0], resource_uid=700_002, stage=3
        )
        ticket = self._resource_ticket(target, 100)
        self._advance_harvest()
        result = resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertEqual(2, result["outcome"]["stage"])
        ecology = result["outcome"]["ecology"]
        self.assertEqual("applied", ecology["reason"])
        self.assertEqual("harvest", ecology["receipt"]["evidence"]["action"])
        self.assertEqual(0, ecology["receipt"]["requested_delta"])
        self.assertEqual(
            ecology["receipt"]["before_value"], ecology["receipt"]["after_value"]
        )
        self.assertEqual(1, sum(opcode == 349 for opcode, _ in result["packets"]))
        self.assertEqual(1, sum(opcode == 13574 for opcode, _ in result["packets"]))
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 1}, dict(self._ecology())
        )
        with self.store.connection() as db:
            saved = db.execute(
                "SELECT result FROM resource_harvest_receipts WHERE token=%s",
                (ticket["token"],),
            ).fetchone()["result"]
        self.assertEqual("applied", saved["ecology"]["reason"])
        self.assertEqual(0, saved["ecology"]["receipt"]["requested_delta"])

        replay = resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertFalse(replay["applied"])
        self.assertEqual([], replay["packets"])

    def test_cancelled_or_early_harvest_does_not_consume_ecology_or_resource(self):
        target = self._insert_resource(
            self.region_cells[0], resource_uid=700_003, stage=3
        )
        ticket = self._resource_ticket(target, 203)
        with self.assertRaisesRegex(ValueError, "before duration"):
            resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._ecology())
        )
        cancelled = resource_collect.complete(
            self.store, ticket, struct.pack(">Bh", 3, 3)
        )
        self.assertFalse(cancelled["applied"])
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM planted_resources WHERE resource_uid=%s",
                    (target["resource_uid"],),
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM resource_harvest_receipts WHERE token=%s",
                    (ticket["token"],),
                ).fetchone()
            )
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._ecology())
        )

    def test_sql_failure_rolls_back_plant_seed_resource_profession_and_ecology(self):
        prepared = self._prepare_plant(self.region_cells[0])
        self._install_ecology_failure()
        with self.assertRaises(RaiseException):
            self._plant(prepared, "flora-plant-trigger-failure")
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._ecology())
        )
        character = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            10,
            next(
                row["quantity"]
                for row in character["inventory_items"]
                if row["uid"] == self.seed_item["uid"]
            ),
        )
        with self.store.connection() as db:
            for table in (
                "planted_resources",
                "planting_receipts",
                "personal_ecology_receipts",
            ):
                self.assertEqual(
                    0, db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
                )
            xp = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                (self.account,),
            ).fetchone()["xp"]
        self.assertEqual(123, xp)

    def test_sql_failure_rolls_back_harvest_resource_product_xp_receipt_and_ecology(
        self,
    ):
        target = self._insert_resource(
            self.region_cells[0], resource_uid=700_004, stage=3
        )
        ticket = self._resource_ticket(target, 203)
        self._advance_harvest()
        self._install_ecology_failure()
        before_inventory = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ]
        with self.assertRaises(RaiseException):
            resource_collect.complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0}, dict(self._ecology())
        )
        after_inventory = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ]
        self.assertEqual(before_inventory, after_inventory)
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM planted_resources WHERE resource_uid=%s AND stage=3",
                    (target["resource_uid"],),
                ).fetchone()
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM resource_harvest_occupations WHERE token=%s",
                    (ticket["token"],),
                ).fetchone()
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM resource_harvest_receipts WHERE token=%s",
                    (ticket["token"],),
                ).fetchone()
            )
            xp = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=72",
                (self.account,),
            ).fetchone()["xp"]
        self.assertEqual(123, xp)

    def test_concurrent_planting_actions_share_population_lock_and_do_not_lose_delta(
        self,
    ):
        self._insert_plants(299)
        first = self._prepare_plant(self.region_cells[300])
        second = self._prepare_plant(self.region_cells[301])
        barrier = threading.Barrier(2)

        def apply(prepared, operation):
            barrier.wait(timeout=10)
            return self._plant(prepared, operation)

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(
                workers.map(
                    lambda args: apply(*args),
                    ((first, "flora-race-a"), (second, "flora-race-b")),
                )
            )
        ecology_bodies = [
            body
            for result in results
            for opcode, body in result["packets"]
            if opcode == 13574
        ]
        self.assertEqual(2, len(ecology_bodies))
        self.assertEqual(
            {native_score(25), native_score(0)},
            {struct.unpack(">qi", body)[1] for body in ecology_bodies},
        )
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 2}, dict(self._ecology())
        )
        character = self.store.character(self.account, self.character["id"])
        self.assertEqual(
            8,
            next(
                row["quantity"]
                for row in character["inventory_items"]
                if row["uid"] == self.seed_item["uid"]
            ),
        )

    def test_different_character_leases_serialize_same_region_population_boundary(self):
        self._insert_plants(299)
        second_account = self.store.register("flora-ecology-second", "test-password")[
            "id"
        ]
        second_character = self.store.create_character(second_account, "Flora Second")
        second_generation = self.store.begin_session(second_account)
        self.store.select_character(
            second_account, second_generation, second_character["id"]
        )
        ensure_learned(
            self.store, second_account, second_generation, second_character["id"], [72]
        )
        point = self.region_cells[-2]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (self.map_id, self.instance_id, *point, second_character["id"]),
            )
        second_character = self.store.character(second_account, second_character["id"])
        second_seed = grant(
            self.store,
            second_account,
            second_generation,
            second_character["id"],
            reference=4275,
            quantity=2,
            container=second_character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )

        first = self._prepare_plant(self.region_cells[300])
        x, y, _z = point
        second = planting.prepare(
            self.store,
            second_account,
            second_generation,
            second_character,
            struct.pack(">iqii", SEEDS[4275]["action_id"], second_seed["uid"], x, y),
            authorize_cell=lambda _actor, request, _seed, _resource: next(
                row["z"]
                for row in cells(self.map_id)[(request["x"], request["y"])]
                if row["region_id"] == self.region_id
            ),
            open_test_policy=True,
        )
        barrier = threading.Barrier(2)

        def apply_first():
            barrier.wait(timeout=10)
            return self._plant(first, "flora-independent-lease-a")

        def apply_second():
            barrier.wait(timeout=10)
            return planting.complete(
                self.store,
                second_account,
                second_generation,
                second,
                operation_id="flora-independent-lease-b",
                stage=2,
                creation_time=int(self.clock[0] * 1000),
                result_prefix=(0, 1),
                success=True,
            )

        with ThreadPoolExecutor(max_workers=2) as workers:
            first_result, second_result = list(
                workers.map(lambda call: call(), (apply_first, apply_second))
            )

        outcomes = (first_result, second_result)
        receipts = [result["ecology"]["receipt"] for result in outcomes]
        self.assertEqual(
            [299, 300],
            sorted(receipt["evidence"]["before_population"] for receipt in receipts),
        )
        self.assertEqual(
            [300, 301],
            sorted(receipt["evidence"]["after_population"] for receipt in receipts),
        )
        self.assertEqual(
            {25, -25}, {receipt["requested_delta"] for receipt in receipts}
        )
        for result in outcomes:
            receipt = result["ecology"]["receipt"]
            packet = next(body for opcode, body in result["packets"] if opcode == 13574)
            self.assertEqual(
                (receipt["character_id"], native_score(receipt["after_value"])),
                struct.unpack(">qi", packet),
            )
        with self.store.connection() as db:
            population = db.execute(
                "SELECT count(*) AS n FROM planted_resources WHERE map_id=%s AND instance_id=%s",
                (self.map_id, self.instance_id),
            ).fetchone()["n"]
            values = db.execute(
                "SELECT id,ecology_value,ecology_revision FROM characters WHERE id=ANY(%s)",
                ([self.character["id"], second_character["id"]],),
            ).fetchall()
        self.assertEqual(301, population)
        self.assertEqual({25, -25}, {row["ecology_value"] for row in values})
        self.assertEqual({1}, {row["ecology_revision"] for row in values})

    def test_world_join_update_and_new_generation_replay_absolute_ecology(self):
        second = self.store.create_character(self.account, "Flora Observer")
        third = self.store.create_character(self.account, "Other Location")
        for actor in (second, third):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (
                        self.map_id,
                        self.instance_id,
                        *self.region_cells[-1],
                        actor["id"],
                    ),
                )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=%s",
                (self.instance_id + 1, third["id"]),
            )
            personal_ecology.apply(
                db,
                self.character["id"],
                operation="world-owner-start",
                delta=25,
                evidence={"source": "fixture"},
            )
            personal_ecology.apply(
                db,
                second["id"],
                operation="world-observer-start",
                delta=-25,
                evidence={"source": "fixture"},
            )
            personal_ecology.apply(
                db,
                third["id"],
                operation="world-other-start",
                delta=77,
                evidence={"source": "fixture"},
            )

        def state_packets(character):
            return (*mount_snapshot(character), *ecology_snapshot(character))

        sent = []
        world = World(
            lambda character: ("spawn", character["id"]),
            lambda character_id: ("remove", character_id),
            lambda peer, opcode, body: sent.append((peer, opcode, body)),
            state_packets=state_packets,
        )
        owner = self.store.character(self.account, self.character["id"])
        observer = self.store.character(self.account, second["id"])
        other_location = self.store.character(self.account, third["id"])
        world.join("owner-g1", "owner", owner)
        owner_snapshot = personal_ecology.packet(owner["id"], 25)
        self.assertEqual([("owner", *owner_snapshot)], sent)

        sent.clear()
        world.join("observer-g1", "observer", observer)
        self.assertIn(
            ("observer", 13574, personal_ecology.packet(owner["id"], 25)[1]), sent
        )
        self.assertIn(
            ("owner", 13574, personal_ecology.packet(observer["id"], -25)[1]), sent
        )
        self.assertIn(
            ("observer", 13574, personal_ecology.packet(observer["id"], -25)[1]), sent
        )

        sent.clear()
        world.join("other-g1", "other-location", other_location)
        self.assertEqual(
            [("other-location", *personal_ecology.packet(third["id"], 77))], sent
        )

        # An action refresh updates the live cache and informs same-location
        # observers, while the origin gets its direct owner packet separately.
        with self.store.connection() as db:
            applied = personal_ecology.apply(
                db,
                owner["id"],
                operation="world-owner-next",
                delta=10,
                evidence={"source": "fixture"},
            )
        updated_owner = self.store.character(self.account, owner["id"])
        sent.clear()
        world.update(
            "owner-g1", updated_owner, *applied["packet"], include_sender=False
        )
        self.assertEqual([("observer", *applied["packet"])], sent)
        self.assertEqual(
            35,
            next(
                actor["ecology_value"]
                for actor in world.snapshot()
                if actor["id"] == owner["id"]
            ),
        )

        # Replacing the membership generation replays the latest absolute
        # value to that owner and other observers; stale-generation leave does
        # not erase the replacement.
        replacement = self.store.begin_session(self.account)
        sent.clear()
        world.join(replacement, "owner-new", updated_owner)
        self.assertIn(
            ("owner-new", 13574, personal_ecology.packet(owner["id"], 35)[1]), sent
        )
        self.assertFalse(world.leave(owner["id"], "owner-g1"))
        self.assertEqual(
            replacement,
            next(
                generation
                for generation, _peer, actor in world.players.values()
                if actor["id"] == owner["id"]
            ),
        )
        self.assertTrue(
            any(
                peer == "observer"
                and opcode == 13574
                and body == personal_ecology.packet(owner["id"], 35)[1]
                for peer, opcode, body in sent
            )
        )


if __name__ == "__main__":
    unittest.main()
