"""PostgreSQL lifecycle tests for fixed, non-flora mineral placements."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import struct
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.mining_veins import install, refill
from wakfu_server.planting_runtime import Plantings
from wakfu_server.planting import (
    SEEDS,
    complete as complete_plant,
    prepare as prepare_plant,
)
from wakfu_server.inventory_items import grant
from wakfu_server.profession_store import ensure_learned
from wakfu_server.resource_collect import complete, prepare, reserve
from wakfu_server.wire import proto_field


class MiningVeinPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [1_700_000_000.0]
        self.store.clock = lambda: self.clock[0]
        account = self.store.register(
            "mining-" + uuid.uuid4().hex[:12], "local-password"
        )
        self.account = account["id"]
        self.character = self.store.create_character(self.account, "Mining Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        ensure_learned(
            self.store, self.account, self.generation, self.character["id"], [73]
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=%s "
                "WHERE account_id=%s AND profession_id=73",
                (75 * 60 * 60, self.account),
            )
            db.execute(
                "UPDATE settings SET value=%s WHERE name='mining_vein_policy'",
                (
                    Jsonb(
                        {
                            "version": 1,
                            "respawn_seconds": 30,
                            "product_selection": {
                                "mode": "native_candidates_weighted",
                                "weights": {},
                            },
                        }
                    ),
                ),
            )
        self.slot = dict(
            resource_uid=780_001,
            map_id=self.character["map_id"],
            instance_id=self.character["instance_id"],
            x=self.character["x"],
            y=self.character["y"],
            z=self.character["z"],
            resource_reference=433,
            stage=1,
            respawn_seconds=None,
            enabled=True,
            active=False,
            available_at=self.store.now(),
            provenance={"source": "test", "surface": "explicit-fixture"},
        )
        self.plantings = Plantings(self.store)

    def _insert_slot(self, slot=None):
        values = dict(self.slot if slot is None else slot)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO mining_vein_slots(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,respawn_seconds,enabled,active,available_at,provenance) "
                "VALUES(%(resource_uid)s,%(map_id)s,%(instance_id)s,%(x)s,%(y)s,%(z)s,"
                "%(resource_reference)s,%(stage)s,%(respawn_seconds)s,%(enabled)s,%(active)s,"
                "%(available_at)s,%(provenance)s)",
                {**values, "provenance": Jsonb(values["provenance"])},
            )
        return values

    def _reviewed_placement(self, *, uid=781_001, **changes):
        report = (
            Path(__file__).resolve().parents[2]
            / "docs/reports/mining/NATIVE-MINING-SURFACES.json"
        )
        candidates = json.loads(report.read_text())["candidate_surfaces"]
        candidate = next(
            row
            for row in candidates
            if row["map_id"] == 235
            and row["x"] == 10
            and row["y"] == 124
            and row["z"] == 3
            and 37 in row["eligible_resource_references"]
        )
        self.reviewed_candidate = candidate
        placement = {
            "resource_uid": uid,
            "map_id": candidate["map_id"],
            "instance_id": 0,
            "x": candidate["x"],
            "y": candidate["y"],
            "z": candidate["z"],
            "resource_reference": 37,
            "stage": 1,
            "respawn_seconds": 45,
            "provenance": {
                "evidence_kind": candidate["evidence_kind"],
                "chunk": candidate["chunk"],
                "ground_id": candidate["ground_id"],
                "environment_chunk_sha256": candidate["environment_chunk_sha256"],
            },
        }
        return {**placement, **changes}

    def _install_reviewed(self, placements):
        """Use report-backed terrain for DB lifecycle tests, not live catalog state."""
        candidate = self.reviewed_candidate

        def reviewed_surface(map_id, x, y, z):
            if (map_id, x, y, z) != (
                candidate["map_id"],
                candidate["x"],
                candidate["y"],
                candidate["z"],
            ):
                raise AssertionError(
                    "Unexpected placement outside the reviewed fixture"
                )
            return {
                "ground_id": candidate["ground_id"],
                "eligible_refs": frozenset(candidate["eligible_resource_references"]),
                # Native adjacency is covered independently by test_mining_navigation.
                "approaches": frozenset({(x + 1, y, z)}),
            }

        with patch(
            "wakfu_server.mining_navigation.surface", side_effect=reviewed_surface
        ):
            return install(self.store, placements)

    def _slot(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM mining_vein_slots WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            ).fetchone()

    def _resource(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM planted_resources WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            ).fetchone()

    def _outbox(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM planting_growth_outbox WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            ).fetchone()

    def _harvest(self, action_id=1119):
        resource = self._resource()
        body = (
            proto_field(8, action_id)
            + proto_field(
                16, resource["x"] if resource["x"] >= 0 else (1 << 64) + resource["x"]
            )
            + proto_field(
                24, resource["y"] if resource["y"] >= 0 else (1 << 64) + resource["y"]
            )
        )
        prepared = prepare(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            body,
            reachable=lambda _actor, _target: True,
        )
        ticket = reserve(self.store, self.account, self.generation, prepared)
        self.clock[0] += 6.1
        return ticket, complete(self.store, ticket, struct.pack(">Bh", 2, 3))

    def test_harvest_depletes_fixed_slot_and_refills_same_native_resource_once(self):
        self._insert_slot()
        self.assertEqual(1, refill(self.store))
        self.assertEqual(0, refill(self.store))
        self.assertTrue(self._slot()["active"])
        self.assertEqual(self.slot["resource_uid"], self._resource()["resource_uid"])

        def publish(value):
            deliveries.append(value)

        deliveries = []
        self.plantings.mature(None, publish=publish)
        self.assertEqual(1, len(deliveries))
        self.assertEqual(self.slot["resource_uid"], deliveries[0]["resource_uid"])
        self.assertEqual([13135], [opcode for opcode, _ in deliveries[0]["packets"]])
        self.assertTrue(deliveries[0]["packets"][0][1])
        initial = self._outbox()
        self.assertTrue(initial["published"])
        self.assertTrue(initial["resource"]["mining_spawn"])

        ticket, harvested = self._harvest()
        self.assertTrue(harvested["applied"])
        self.assertEqual(13180, harvested["outcome"]["item_reference"])
        self.assertEqual(50, harvested["outcome"]["xp"])
        self.assertEqual(
            "mineral_not_ecological", harvested["outcome"]["ecology"]["reason"]
        )
        self.assertFalse(any(opcode == 13574 for opcode, _ in harvested["packets"]))
        self.assertIsNone(self._resource())
        depleted = self._slot()
        self.assertFalse(depleted["active"])
        self.assertEqual(
            self.store.now() + timedelta(seconds=30), depleted["available_at"]
        )
        self.assertEqual(
            {"applied": False, "packets": [], "world_packets": []},
            complete(self.store, ticket, struct.pack(">Bh", 2, 3)),
        )

        # Publish the completed removal separately; before the policy deadline
        # the slot remains absent and after it the same fixed identity returns.
        self.plantings.mature(None, publish=publish)
        self.assertEqual(0, refill(self.store))
        self.clock[0] += 30.1
        respawn = self.plantings.mature(None, publish=publish)
        self.assertEqual(1, len(respawn))
        self.assertEqual(self.slot["resource_uid"], respawn[0]["resource_uid"])
        self.assertEqual([13135], [opcode for opcode, _ in respawn[0]["packets"]])
        self.assertTrue(respawn[0]["packets"][0][1])
        self.assertTrue(self._slot()["active"])
        self.assertEqual(self.slot["resource_uid"], self._resource()["resource_uid"])

    def test_reference643_uses_one_local_native_candidate_then_depletes_once(self):
        self.slot = dict(
            self.slot,
            resource_uid=780_643,
            resource_reference=643,
            stage=1,
        )
        self._insert_slot()
        self.assertEqual(1, refill(self.store))

        ticket, harvested = self._harvest(action_id=1779)
        self.assertTrue(harvested["applied"])
        self.assertIn(harvested["outcome"]["item_reference"], (9797, 9787))
        self.assertEqual(1, harvested["outcome"]["quantity"])
        self.assertGreater(harvested["outcome"]["xp"], 0)
        self.assertEqual(
            "mineral_not_ecological", harvested["outcome"]["ecology"]["reason"]
        )
        self.assertFalse(any(opcode == 13574 for opcode, _ in harvested["packets"]))
        self.assertIsNone(self._resource())
        depleted = self._slot()
        self.assertFalse(depleted["active"])
        self.assertEqual(
            self.store.now() + timedelta(seconds=30), depleted["available_at"]
        )

        candidate = harvested["outcome"]["item_reference"]
        inventory = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ]
        self.assertEqual(
            1,
            sum(row["quantity"] for row in inventory if row["reference"] == candidate),
        )
        retry = complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertFalse(retry["applied"])
        inventory_after_retry = self.store.character(
            self.account, self.character["id"]
        )["inventory_items"]
        self.assertEqual(
            1,
            sum(
                row["quantity"]
                for row in inventory_after_retry
                if row["reference"] == candidate
            ),
        )

    def test_concurrent_refill_claims_one_slot_and_preserves_one_identity(self):
        self._insert_slot()
        start = threading.Barrier(2)

        def run():
            start.wait(timeout=5)
            return refill(self.store)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(1, sum(results))
        self.assertEqual(1, sum(row is not None for row in [self._resource()]))
        self.assertTrue(self._slot()["active"])
        self.assertEqual(
            1, self._outbox()["resource"]["resource_uid"] == self.slot["resource_uid"]
        )

    def test_cell_collision_keeps_due_slot_for_a_later_retry(self):
        self._insert_slot()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(780002,%s,%s,%s,%s,%s,60,3,0)",
                (
                    self.slot["map_id"],
                    self.slot["instance_id"],
                    self.slot["x"],
                    self.slot["y"],
                    self.slot["z"],
                ),
            )
        self.assertEqual(0, refill(self.store))
        self.assertFalse(self._slot()["active"])
        self.assertIsNone(self._outbox())
        with self.store.connection() as db:
            db.execute("DELETE FROM planted_resources WHERE resource_uid=780002")
        self.assertEqual(1, refill(self.store))
        self.assertTrue(self._slot()["active"])

    def test_install_is_idempotent_and_preserves_an_exhausted_slot_deadline(self):
        placement = self._reviewed_placement()
        self.assertEqual(1, self._install_reviewed([placement]))
        self.assertEqual(0, self._install_reviewed([placement]))
        due = self.store.now() + timedelta(seconds=75)
        with self.store.connection() as db:
            db.execute(
                "UPDATE mining_vein_slots SET active=FALSE,available_at=%s "
                "WHERE resource_uid=%s",
                (due, placement["resource_uid"]),
            )
        self.assertEqual(0, self._install_reviewed([placement]))
        with self.store.connection() as db:
            slot = db.execute(
                "SELECT * FROM mining_vein_slots WHERE resource_uid=%s",
                (placement["resource_uid"],),
            ).fetchone()
        self.assertFalse(slot["active"])
        self.assertEqual(due, slot["available_at"])
        self.assertEqual(placement["provenance"], slot["provenance"])

    def test_install_rejects_duplicate_invalid_and_occupied_placements_atomically(self):
        placement = self._reviewed_placement()
        duplicate = {**placement, "resource_uid": placement["resource_uid"] + 1}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self._install_reviewed([placement, duplicate])
        with self.assertRaisesRegex(ValueError, "incompatible with native terrain"):
            self._install_reviewed(
                [self._reviewed_placement(uid=781_002, resource_reference=242)]
            )
        with self.assertRaisesRegex(
            ValueError, "no supported terminal mineral harvest"
        ):
            self._install_reviewed([self._reviewed_placement(uid=781_003, stage=16)])
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(781004,%s,0,%s,%s,%s,60,3,0)",
                (placement["map_id"], placement["x"], placement["y"], placement["z"]),
            )
        with self.assertRaisesRegex(ValueError, "already contains a resource"):
            self._install_reviewed([placement])
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute("SELECT count(*) FROM mining_vein_slots").fetchone()[
                    "count"
                ],
            )

    def test_invalid_policy_rolls_back_mining_harvest_and_slot_depletion(self):
        self._insert_slot()
        self.assertEqual(1, refill(self.store))
        resource = self._resource()
        body = (
            proto_field(8, 1119)
            + proto_field(
                16, resource["x"] if resource["x"] >= 0 else (1 << 64) + resource["x"]
            )
            + proto_field(
                24, resource["y"] if resource["y"] >= 0 else (1 << 64) + resource["y"]
            )
        )
        prepared = prepare(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            body,
            reachable=lambda _actor, _target: True,
        )
        ticket = reserve(self.store, self.account, self.generation, prepared)
        self.clock[0] += 6.1
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='mining_vein_policy'",
                (Jsonb({"version": 999, "respawn_seconds": 0}),),
            )
        with self.assertRaisesRegex(ValueError, "Invalid mining vein policy"):
            complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertIsNotNone(self._resource())
        self.assertTrue(self._slot()["active"])
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) FROM resource_harvest_receipts WHERE token=%s",
                    (ticket["token"],),
                ).fetchone()["count"],
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='mining_vein_policy'",
                (Jsonb({"version": 1, "respawn_seconds": 30}),),
            )
        completed = complete(self.store, ticket, struct.pack(">Bh", 2, 3))
        self.assertTrue(completed["applied"])
        self.assertFalse(self._slot()["active"])
        self.assertIsNone(self._resource())

    def test_non_mineral_slot_is_rejected_without_partial_spawn(self):
        self._insert_slot()
        self.assertEqual(1, refill(self.store))
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM planted_resources WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            )
            db.execute(
                "DELETE FROM planting_growth_outbox WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            )
            db.execute(
                "UPDATE mining_vein_slots SET resource_reference=60,active=FALSE WHERE resource_uid=%s",
                (self.slot["resource_uid"],),
            )
        with self.assertRaisesRegex(ValueError, "non-mineral"):
            refill(self.store)
        self.assertIsNone(self._resource())
        self.assertFalse(self._slot()["active"])

    def test_failed_world_publish_keeps_spawn_outbox_for_retry(self):
        self._insert_slot()
        with self.assertRaisesRegex(RuntimeError, "publish unavailable"):
            self.plantings.mature(
                None,
                publish=lambda _delivery: (_ for _ in ()).throw(
                    RuntimeError("publish unavailable")
                ),
            )
        self.assertTrue(self._slot()["active"])
        self.assertFalse(self._outbox()["published"])
        seen = []
        retry = self.plantings.publish_growth(None, publish=seen.append)
        self.assertEqual(1, len(retry))
        self.assertEqual(1, len(seen))
        self.assertEqual([13135], [opcode for opcode, _ in seen[0]["packets"]])
        self.assertTrue(self._outbox()["published"])

    def test_synthetic_seed_for_mining_resource_is_rejected_without_consumption(self):
        item_reference, action_id = 990_001, 990_002
        synthetic = {
            "item_reference": item_reference,
            "resource_reference": 433,
            "action_id": action_id,
            "profession_id": 73,
            "minimum_level": 0,
            "has_item_criteria": False,
        }
        with patch.dict(SEEDS, {item_reference: synthetic}):
            item = grant(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                reference=item_reference,
                quantity=2,
                container=self.character["inventory_containers"][0]["uid"],
                slot=0,
                allowed_references={item_reference: synthetic},
            )
            body = struct.pack(
                ">iqii",
                action_id,
                item["uid"],
                self.character["x"],
                self.character["y"],
            )
            with self.assertRaisesRegex(
                ValueError, "Mining resources cannot be planted"
            ):
                prepare_plant(
                    self.store,
                    self.account,
                    self.generation,
                    self.character,
                    body,
                    authorize_cell=lambda *_args: self.character["z"],
                )
        inventory = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ]
        self.assertEqual(
            2, next(row["quantity"] for row in inventory if row["uid"] == item["uid"])
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute("SELECT count(*) FROM planted_resources").fetchone()[
                    "count"
                ],
            )

    def test_planting_prepared_before_slot_install_is_rejected_at_commit(self):
        item = grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=4275,
            quantity=2,
            container=self.character["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references=SEEDS,
        )
        ensure_learned(
            self.store, self.account, self.generation, self.character["id"], [72]
        )
        body = struct.pack(
            ">iqii",
            SEEDS[4275]["action_id"],
            item["uid"],
            self.character["x"],
            self.character["y"],
        )
        prepared = prepare_plant(
            self.store,
            self.account,
            self.generation,
            self.character,
            body,
            authorize_cell=lambda *_args: self.character["z"],
        )
        self._insert_slot()
        with self.assertRaisesRegex(ValueError, "reserved for a mineral vein"):
            complete_plant(
                self.store,
                self.account,
                self.generation,
                prepared,
                operation_id="plant-raced-mining-slot",
                stage=2,
                creation_time=123,
                result_prefix=(0, 1),
            )
        inventory = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ]
        self.assertEqual(
            2, next(row["quantity"] for row in inventory if row["uid"] == item["uid"])
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute("SELECT count(*) FROM planted_resources").fetchone()[
                    "count"
                ],
            )
            self.assertEqual(
                0,
                db.execute("SELECT count(*) FROM planting_receipts").fetchone()[
                    "count"
                ],
            )


if __name__ == "__main__":
    unittest.main()
