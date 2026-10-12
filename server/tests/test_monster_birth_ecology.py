import threading
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from postgres_case import PostgresCase
from psycopg.errors import RaiseException
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import owned_instance
from wakfu_server.monster_maturation import attempt as mature_attempt
from wakfu_server.monster_birth_ecology import activate
from wakfu_server import monster_birth_ecology
from wakfu_server.planting_cells import cells
from wakfu_server.planting_runtime import Plantings
from wakfu_server.combat_monster_world import spawn_group


class MonsterBirthEcologyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.native_wish = dict(family_id=316, minimum=1, maximum=128)
        self.native_catalog = {
            "territories": {
                "79001": dict(
                    map_id=1134, plant_wishes=[], monster_wishes=[self.native_wish]
                )
            }
        }
        native = patch(
            "wakfu_server.ecology_equilibrium.catalog", return_value=self.native_catalog
        )
        native.start()
        self.addCleanup(native.stop)
        self.groups = PersistentGroups(self.store)
        self.map_id = 1134
        self.instance_id = 17
        self.region_id = 79001
        points = []
        for (x, y), entries in cells(self.map_id).items():
            for entry in entries:
                if entry["region_id"] == self.region_id:
                    points.append((x, y, entry["z"]))
        self.points = list(dict.fromkeys(points))
        self.assertGreater(len(self.points), 3)
        self._next = 0

    def _new_birth(
        self,
        suffix,
        *,
        point=None,
        monster_id=None,
        group_id=None,
        resource_uid=None,
        relocate_owner=False,
    ):
        account = self.store.register(f"birth-{suffix}", "test-password")["id"]
        character = self.store.create_character(account, f"Birth {suffix}")
        if relocate_owner:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=1200,instance_id=9,x=1,y=2,z=0 WHERE id=%s",
                    (character["id"],),
                )
        if point is None:
            point = self.points[self._next % len(self.points)]
            self._next += 1
        x, y, z = point
        monster_id = -800_000 - self._next if monster_id is None else monster_id
        group_id = 880_000 + self._next if group_id is None else group_id
        resource_uid = 890_000 + self._next if resource_uid is None else resource_uid
        member = owned_instance(
            4724,
            119,
            monster_id,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=x,
            y=y,
            z=z,
        )
        resource = {
            "resource_uid": resource_uid,
            "map_id": self.map_id,
            "instance_id": self.instance_id,
            "x": x,
            "y": y,
            "z": z,
            "resource_reference": 326,
            "stage": 1,
            "creation_time": 1_700_000_000_000,
        }
        group = {"key": [self.map_id, self.instance_id, group_id], "members": [member]}
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planting_receipts(operation_id,character_id,item_uid,request,resource,success,probability) "
                "VALUES(%s,%s,1,%s,%s,TRUE,1)",
                (
                    f"birth-receipt-{suffix}",
                    character["id"],
                    Jsonb({}),
                    Jsonb(resource),
                ),
            )
            db.execute(
                "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(%s,%s,%s)",
                (resource_uid, Jsonb(resource), Jsonb(group)),
            )
        return {
            "account_id": account,
            "character_id": character["id"],
            "resource_uid": resource_uid,
            "group": group,
            "member": member,
            "resource": resource,
        }

    def _ecology(self, character_id):
        with self.store.connection() as db:
            return db.execute(
                "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
                (character_id,),
            ).fetchone()

    def test_birth_registers_group_and_ecology_in_callers_transaction_once(self):
        birth = self._new_birth("atomic")
        with self.store.connection() as db, db.transaction():
            first = activate(db, self.groups, birth["resource_uid"])
            self.assertEqual("applied", first["reason"])
            self.assertFalse(first["duplicate"])
            self.assertIsInstance(first["information"], str)
            self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
            self.assertEqual(len(first["packets"]), 1)
            # A retry in the same transaction sees the group/receipt and cannot
            # award a second increment.
            replay = activate(db, self.groups, birth["resource_uid"])
            self.assertTrue(replay["duplicate"])
            self.assertIsNone(replay.get("information"))
            self.assertEqual(1, len(replay["packets"]))
            self.assertEqual(db.info.transaction_status, TransactionStatus.INTRANS)
        self.assertEqual(
            {"ecology_value": 25, "ecology_revision": 1},
            dict(self._ecology(birth["character_id"])),
        )
        self.assertEqual(1, len(self.groups.snapshot(self.map_id, self.instance_id)))
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) FROM personal_ecology_receipts WHERE character_id=%s",
                    (birth["character_id"],),
                ).fetchone()["count"],
            )

    def test_ecology_sql_failure_rolls_back_group_and_member_registration(self):
        birth = self._new_birth("rollback")
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_birth_ecology() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'forced birth ecology failure'; END $$"
            )
            db.execute(
                "CREATE TRIGGER reject_birth_ecology BEFORE INSERT ON personal_ecology_receipts "
                "FOR EACH ROW EXECUTE FUNCTION reject_birth_ecology()"
            )
        group_key = tuple(birth["group"]["key"])
        with self.assertRaises(RaiseException):
            with self.store.connection() as db, db.transaction():
                activate(db, self.groups, birth["resource_uid"])
        self.assertFalse(any(row["key"] == group_key for row in self.groups.snapshot()))
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM combat_group_members WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
                    (self.map_id, self.instance_id, birth["member"]["id"]),
                ).fetchone()
            )
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0},
            dict(self._ecology(birth["character_id"])),
        )

    def test_member_identity_conflict_rolls_back_parent_birth_group(self):
        birth = self._new_birth("member-conflict")
        original_key = (self.map_id, self.instance_id, birth["group"]["key"][2] + 1)
        self.groups.register(*original_key, [birth["member"]])
        attempted_key = tuple(birth["group"]["key"])
        with self.assertRaisesRegex(ValueError, "identity already exists"):
            with self.store.connection() as db, db.transaction():
                activate(db, self.groups, birth["resource_uid"])
        self.assertFalse(
            any(row["key"] == attempted_key for row in self.groups.snapshot())
        )
        self.assertTrue(
            any(row["key"] == original_key for row in self.groups.snapshot())
        )
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0},
            dict(self._ecology(birth["character_id"])),
        )

    def test_unknown_surface_activates_birth_without_ecology_reward(self):
        outside = (2_000_000, 2_000_000, 0)
        birth = self._new_birth("unknown-surface", point=outside)
        with self.store.connection() as db, db.transaction():
            result = activate(db, self.groups, birth["resource_uid"])
        self.assertEqual("native_region_unavailable", result["reason"])
        self.assertEqual([], result["packets"])
        self.assertIsNone(result["information"])
        self.assertTrue(
            any(
                row["key"] == tuple(birth["group"]["key"])
                for row in self.groups.snapshot()
            )
        )
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0},
            dict(self._ecology(birth["character_id"])),
        )
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) FROM personal_ecology_receipts WHERE character_id=%s",
                    (birth["character_id"],),
                ).fetchone()["count"],
            )

    def test_unrelated_unassigned_native_monster_does_not_suppress_birth_affinity(self):
        birth = self._new_birth("outside")
        outside = owned_instance(
            4724,
            119,
            -799999,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=2_000_000,
            y=2_000_000,
            z=0,
        )
        self.groups.register(self.map_id, self.instance_id, 879999, [outside])
        native_surface = monster_birth_ecology.surface

        def surface(map_id, x, y, z):
            if (x, y, z) == (2_000_000, 2_000_000, 0):
                return {"region_id": -1}
            return native_surface(map_id, x, y, z)

        with patch.object(monster_birth_ecology, "surface", side_effect=surface):
            with self.store.connection() as db, db.transaction():
                result = activate(db, self.groups, birth["resource_uid"])
        self.assertEqual("applied", result["reason"])
        self.assertEqual(1, len(result["packets"]))
        self.assertEqual(1, self._ecology(birth["character_id"])["ecology_revision"])

    def test_offline_or_relocated_owner_still_receives_persistent_birth_credit(self):
        birth = self._new_birth("offline-relocated", relocate_owner=True)
        with self.store.connection() as db, db.transaction():
            result = activate(db, self.groups, birth["resource_uid"])
        self.assertEqual(birth["character_id"], result["character_id"])
        self.assertEqual("applied", result["reason"])
        self.assertEqual(1, len(result["packets"]))
        self.assertEqual(result["packets"][0][0], 13574)
        self.assertIsInstance(result["information"], str)
        self.assertIn("población", result["information"])
        self.assertEqual(
            {"ecology_value": 25, "ecology_revision": 1},
            dict(self._ecology(birth["character_id"])),
        )

    def test_missing_event_for_failed_or_unknown_seed_does_not_create_group(self):
        account = self.store.register("birth-failed", "test-password")["id"]
        character = self.store.create_character(account, "Failed Seed")
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planting_receipts(operation_id,character_id,item_uid,request,resource,success,probability) "
                "VALUES('failed-seed-event',%s,1,%s,NULL,FALSE,0)",
                (character["id"], Jsonb({})),
            )
        with self.assertRaisesRegex(ValueError, "event is missing"):
            with self.store.connection() as db, db.transaction():
                activate(db, self.groups, 999_888)
        self.assertEqual([], self.groups.snapshot())
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0},
            dict(self._ecology(character["id"])),
        )

    def test_existing_legacy_group_is_not_awarded_retroactively(self):
        birth = self._new_birth("legacy")
        group_key = tuple(birth["group"]["key"])
        self.groups.register(*group_key, birth["group"]["members"])
        with self.store.connection() as db, db.transaction():
            result = activate(db, self.groups, birth["resource_uid"])
        self.assertTrue(result["duplicate"])
        self.assertEqual("already_activated", result["reason"])
        self.assertEqual([], result["packets"])
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0},
            dict(self._ecology(birth["character_id"])),
        )

    def test_concurrent_births_serialize_at_family_population_limit(self):
        self.native_wish.update(minimum=0, maximum=0)
        births = [self._new_birth("race-a"), self._new_birth("race-b")]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO ecology_family_limits(map_id,region_id,kind,family_id,minimum,maximum,source) "
                "VALUES(%s,%s,'monster',316,0,0,'local')",
                (self.map_id, self.region_id),
            )
        barrier = threading.Barrier(2)

        def activate_birth(birth):
            barrier.wait(timeout=10)
            with self.store.connection() as db, db.transaction():
                return activate(db, self.groups, birth["resource_uid"])

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(activate_birth, births))
        self.assertEqual({"applied"}, {result["reason"] for result in results})
        values = sorted(
            self._ecology(birth["character_id"])["ecology_value"] for birth in births
        )
        self.assertEqual([-25, -25], values)
        with self.store.connection() as db:
            before_counts = sorted(
                row["evidence"]["before_population"]
                for row in db.execute(
                    "SELECT evidence FROM personal_ecology_receipts WHERE operation LIKE 'monster-birth:%'"
                )
            )
        self.assertEqual([0, 1], before_counts)

    def test_birth_population_snapshot_serializes_with_cross_region_group_move(self):
        self.native_wish.update(minimum=0, maximum=0)
        birth = self._new_birth("move-race")
        source = self.points[0]
        other_region_point = next(
            (x, y, entry["z"])
            for (x, y), entries in cells(self.map_id).items()
            for entry in entries
            if entry["region_id"] != self.region_id
        )
        moving_member = owned_instance(
            4724,
            119,
            -910_001,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=source[0],
            y=source[1],
            z=source[2],
        )
        moving_key = (self.map_id, self.instance_id, 910_001)
        self.groups.register(*moving_key, [moving_member])
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO ecology_family_limits(map_id,region_id,kind,family_id,minimum,maximum,source) "
                "VALUES(%s,%s,'monster',316,0,0,'local')",
                (self.map_id, self.region_id),
            )
        barrier = threading.Barrier(2)

        def move_out():
            barrier.wait(timeout=10)
            moved = dict(
                moving_member,
                x=other_region_point[0],
                y=other_region_point[1],
                z=other_region_point[2],
            )
            return self.groups.move_members(moving_key, [moving_member], [moved])

        def activate_birth():
            barrier.wait(timeout=10)
            with self.store.connection() as db, db.transaction():
                return activate(db, self.groups, birth["resource_uid"])

        with ThreadPoolExecutor(max_workers=2) as pool:
            move_future = pool.submit(move_out)
            birth_future = pool.submit(activate_birth)
            self.assertTrue(move_future.result(timeout=20))
            result = birth_future.result(timeout=20)
        self.assertEqual("applied", result["reason"])
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT evidence,requested_delta FROM personal_ecology_receipts WHERE character_id=%s",
                (birth["character_id"],),
            ).fetchone()
        evidence = receipt["evidence"]
        before = evidence["before_population"]
        self.assertIn(before, (0, 1))
        expected_delta = 25 if before == 0 else -25
        self.assertEqual(expected_delta, receipt["requested_delta"])
        self.assertEqual(
            expected_delta, self._ecology(birth["character_id"])["ecology_value"]
        )
        self.assertEqual(before + 1, evidence["after_population"])

    def test_conflicting_existing_group_identity_rejects_birth_without_reward(self):
        birth = self._new_birth("group-conflict")
        key = tuple(birth["group"]["key"])
        replacement = owned_instance(
            4724,
            119,
            birth["member"]["id"] - 1,
            map_id=self.map_id,
            instance_id=self.instance_id,
            x=birth["member"]["x"],
            y=birth["member"]["y"],
            z=birth["member"]["z"],
        )
        self.groups.register(*key, [replacement])
        with self.assertRaisesRegex(ValueError, "identity disagrees"):
            with self.store.connection() as db, db.transaction():
                activate(db, self.groups, birth["resource_uid"])
        self.assertEqual(
            {"ecology_value": 0, "ecology_revision": 0},
            dict(self._ecology(birth["character_id"])),
        )

    def test_failed_emit_retry_publishes_latest_moved_matured_and_appended_roster(self):
        birth = self._new_birth("latest-roster")
        runtime = Plantings(self.store)

        def fail_emit(_delivery):
            raise ConnectionError("peer unavailable")

        with self.assertRaises(ConnectionError):
            runtime.publish_growth(self.groups, publish=fail_emit)
        key = tuple(birth["group"]["key"])
        current = self.groups.snapshot(*key[:2])[0]["members"]
        self.assertEqual([birth["member"]["id"]], [member["id"] for member in current])

        moved_point = next(
            point
            for point in self.points
            if point != tuple(birth["member"][name] for name in ("x", "y", "z"))
        )
        moved = dict(current[0], x=moved_point[0], y=moved_point[1], z=moved_point[2])
        self.assertTrue(self.groups.move_members(key, current, [moved]))
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_maturation_timers(map_id,instance_id,monster_id,reference,remaining_ms,due,cycle) "
                "VALUES(%s,%s,%s,%s,0,TRUE,1)",
                (*key[:2], moved["id"], moved["ref"]),
            )
        grown = mature_attempt(
            self.store,
            dict(
                map_id=key[0],
                instance_id=key[1],
                monster_id=moved["id"],
                cycle=1,
                group_id=key[2],
                reference=moved["ref"],
            ),
            present=True,
            draw=0,
        )
        self.assertIsNotNone(grown["to_reference"])
        after_growth = self.groups.snapshot(*key[:2])[0]["members"]
        self.assertNotEqual(moved["ref"], after_growth[0]["ref"])

        append_point = next(
            point
            for point in self.points
            if point[:2] != (after_growth[0]["x"], after_growth[0]["y"])
        )
        appended = owned_instance(
            4726,
            113,
            moved["id"] - 1,
            map_id=key[0],
            instance_id=key[1],
            x=append_point[0],
            y=append_point[1],
            z=append_point[2],
        )
        latest = [after_growth[0], appended]
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET members=%s,revision=revision+1 WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                (Jsonb(latest), *key),
            )
            db.execute(
                "INSERT INTO combat_group_members(map_id,instance_id,monster_id,group_id) VALUES(%s,%s,%s,%s)",
                (*key[:2], appended["id"], key[2]),
            )

        deliveries = []
        result = runtime.publish_growth(self.groups, publish=deliveries.append)
        self.assertEqual(1, len(result))
        self.assertEqual(1, len(deliveries))
        delivery = deliveries[0]
        self.assertEqual(latest, delivery["ecology"]["members"])
        self.assertEqual("available", delivery["ecology"]["status"])
        self.assertEqual([12782, 12608], [packet[0] for packet in delivery["packets"]])
        self.assertEqual(
            spawn_group(latest, group_id=key[2]), delivery["packets"][1][1]
        )
        with self.store.connection() as db:
            self.assertTrue(
                db.execute(
                    "SELECT published FROM planting_growth_outbox WHERE resource_uid=%s",
                    (birth["resource_uid"],),
                ).fetchone()["published"]
            )

    def test_retry_never_respawns_fighting_or_defeated_group_or_reawards_ecology(self):
        runtime = Plantings(self.store)
        for status in ("fighting", "defeated"):
            with self.subTest(status=status):
                birth = self._new_birth(f"retry-{status}")
                with self.store.connection() as db, db.transaction():
                    activate(db, self.groups, birth["resource_uid"])
                with self.store.connection() as db:
                    fight_id = db.execute(
                        "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                    ).fetchone()["id"]
                key = tuple(birth["group"]["key"])
                lease, _ = self.groups.claim(key, f"generation-{status}", fight_id)
                if status == "defeated":
                    self.assertTrue(self.groups.finish(lease, defeated=True))

                deliveries = []
                runtime.publish_growth(self.groups, publish=deliveries.append)
                matching = [
                    d for d in deliveries if d["resource_uid"] == birth["resource_uid"]
                ]
                self.assertEqual(1, len(matching))
                self.assertEqual(status, matching[0]["ecology"]["status"])
                self.assertEqual(
                    [12782], [packet[0] for packet in matching[0]["packets"]]
                )
                expected_value = 25 if status == "fighting" else 0
                self.assertEqual(
                    {"ecology_value": expected_value, "ecology_revision": 1},
                    dict(self._ecology(birth["character_id"])),
                )
