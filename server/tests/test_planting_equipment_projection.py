"""Inventory computes bounded equipment values; Ecology receives only scalars."""

from contextlib import contextmanager
from datetime import datetime, timezone
import struct
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.planting_equipment_projection import pending_projection
from wakfu_server.ecology.world_bridge import EcologyWorldBridge


class Cursor:
    def __init__(self, *, one=None, rows=()):
        self.one = one
        self.rows = list(rows)

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.rows


class Database:
    def __init__(self, rows, *, valid=True, item=1001):
        self.rows = rows
        self.valid = valid
        self.item = item
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if sql.startswith("SET TRANSACTION"):
            return Cursor()
        if "FROM ecology_planting_intents" in sql:
            return Cursor(rows=self.rows[: params[-1]])
        if "FROM sessions s" in sql:
            return Cursor(one={"owned": 1} if self.valid else None)
        if "FROM inventory_items" in sql:
            return Cursor(one=None if self.item is None else {"reference": self.item})
        raise AssertionError("Unexpected projection SQL")


class Store:
    def __init__(self, db):
        self.db = db
        self.entered = self.exited = 0

    @contextmanager
    def connection(self):
        self.entered += 1
        try:
            yield self.db
        finally:
            self.exited += 1

    def now(self):
        return datetime(2026, 11, 14, tzinfo=timezone.utc)


def intent(number=1, *, map_id=1134):
    return dict(
        id=f"intent-{number}",
        world_epoch="world-epoch",
        account_id=7,
        generation="live-generation",
        character_id=23,
        intent_version=number,
        body=struct.pack(">iqii", 17, 901, -4, 6),
        actor_location={"map_id": map_id, "instance_id": 0, "x": -4, "y": 5, "z": -1},
        profession_id=999,
        inventory={"private": "must not leave Inventory"},
    )


class PlantingEquipmentProjectionTests(unittest.TestCase):
    def setUp(self):
        self.planting = ModuleType("wakfu_server.planting")
        self.planting.SEEDS = {1001: {"profession_id": 64, "action_id": 17}}
        self.planting.decode = Mock(
            return_value={
                "action_id": 17,
                "item_uid": 901,
                "x": -4,
                "y": 6,
                "profession_id": 999,
            }
        )
        self.equipment = ModuleType("wakfu_server.profession_equipment_modifiers")
        self.equipment.modifiers = Mock(return_value={"plant_probability": 125})
        self.modules = patch.dict(
            sys.modules,
            {
                "wakfu_server.planting": self.planting,
                "wakfu_server.profession_equipment_modifiers": self.equipment,
            },
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def project(self, rows=None, **kwargs):
        db = Database([intent()] if rows is None else rows)
        store = Store(db)
        return pending_projection(store, "world-epoch", 1_000_000, **kwargs), store

    def test_owned_seed_selects_canonical_profession_in_one_read_only_snapshot(self):
        rows, store = self.project()
        self.assertEqual(
            rows,
            [
                {
                    "intent_id": "intent-1",
                    "intent_version": 1,
                    "world_epoch": "world-epoch",
                    "account_id": 7,
                    "generation": "live-generation",
                    "character_id": 23,
                    "body_hex": intent()["body"].hex(),
                    "profession_id": 64,
                    "plant_probability": 125,
                }
            ],
        )
        self.assertEqual((store.entered, store.exited), (1, 1))
        self.assertEqual(
            store.db.calls[0][0],
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY",
        )
        sql, params = store.db.calls[1]
        self.assertIn("created_at < to_timestamp(%s / 1000.0)", sql)
        self.assertIn("ORDER BY intent_version LIMIT %s", sql)
        self.assertEqual(params, ("world-epoch", 1_000_000, 4))
        self.assertEqual(store.db.calls[2][1][:3], (7, "live-generation", 23))
        self.assertEqual(store.db.calls[3][1], (901, 23))
        self.equipment.modifiers.assert_called_once_with(store, store.db, 23, 64)
        self.assertTrue(all("FOR UPDATE" not in sql for sql, _ in store.db.calls))

    def test_empty_window_does_not_resolve_seed_or_equipment(self):
        rows, store = self.project([])
        self.assertEqual(rows, [])
        self.assertEqual(len(store.db.calls), 2)
        self.planting.decode.assert_not_called()
        self.equipment.modifiers.assert_not_called()

    def test_stale_owner_or_foreign_seed_never_projects_another_inventory(self):
        for valid, item, reason in (
            (False, 1001, "Invalid inventory session"),
            (True, None, "Seed unavailable or foreign"),
            (True, 9999, "Unknown or mismatched native seed action"),
        ):
            with self.subTest(valid=valid, item=item):
                db = Database([intent()], valid=valid, item=item)
                rows = pending_projection(Store(db), "world-epoch", 1_000_000)
                self.assertEqual(rows[0]["error"], reason)
                self.assertNotIn("plant_probability", rows[0])
        self.equipment.modifiers.assert_not_called()

    def test_seed_action_mismatch_cannot_spoof_profession(self):
        self.planting.decode.return_value["action_id"] = 18
        rows, _ = self.project()
        self.assertIn("mismatched", rows[0]["error"])
        self.assertNotIn("profession_id", rows[0])
        self.equipment.modifiers.assert_not_called()

    def test_only_deterministic_domain_errors_are_bound_to_the_intent(self):
        self.equipment.modifiers.side_effect = [
            ValueError("Ineligible equipment"),
            {"plant_probability": 25},
        ]
        rows, store = self.project([intent(1), intent(2)])
        self.assertEqual(rows[0]["error"], "Ineligible equipment")
        self.assertEqual(rows[0]["profession_id"], 64)
        self.assertEqual(rows[1]["plant_probability"], 25)
        self.assertEqual(self.equipment.modifiers.call_count, 2)
        self.assertEqual(store.entered, 1)
        self.equipment.modifiers.side_effect = OSError("database unavailable")
        with self.assertRaises(OSError):
            self.project()

    def test_invalid_inventory_result_is_rejected_instead_of_coerced(self):
        for amount in (True, 1.5, 1 << 31, -(1 << 31) - 1):
            with self.subTest(amount=amount):
                self.equipment.modifiers.return_value = {"plant_probability": amount}
                rows, _ = self.project()
                self.assertIn("profession bonus", rows[0]["error"])
                self.assertNotIn("plant_probability", rows[0])

    def test_open_garden_filter_runs_after_the_same_reserved_window_limit(self):
        rows, store = self.project(
            [intent(1), intent(2), intent(3), intent(4, map_id=9), intent(5, map_id=9)],
            gardens_only=True,
        )
        self.assertEqual([row["intent_version"] for row in rows], [4])
        self.assertEqual(store.db.calls[1][1][-1], 4)
        self.equipment.modifiers.assert_called_once()

    def test_projection_budget_and_epoch_are_validated_before_reading(self):
        for arguments in (
            ("", 1_000_000, 4),
            ("x", True, 4),
            ("x", 1_000_000, 5),
            ("x", 1_000_000, True),
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                pending_projection(object(), *arguments)


class PlantingProjectionSnapshotTests(unittest.TestCase):
    def bridge(self, *, open_policy, map_id):
        self.world_lock = threading.RLock()
        self.harvest_lock = threading.RLock()
        return EcologyWorldBridge(
            store=object(),
            world=SimpleNamespace(
                ecology_snapshot=lambda: [
                    dict(
                        id=23,
                        account_id=7,
                        map_id=map_id,
                        instance_id=0,
                        x=1,
                        y=2,
                        z=-1,
                    )
                ],
                lock=self.world_lock,
            ),
            groups=SimpleNamespace(),
            harvests=SimpleNamespace(lock=self.harvest_lock, targets={}),
            plantings=SimpleNamespace(growth_seconds=30, open_test_policy=open_policy),
            token="internal-test-token",
            mode="external",
            clock=lambda: 1000.25,
        )

    def test_open_public_world_needs_no_projection_import_or_inventory_read(self):
        bridge = self.bridge(open_policy=True, map_id=1134)
        with patch(
            "wakfu_server.planting_equipment_projection.pending_projection"
        ) as project:
            snapshot = bridge.snapshot()
        project.assert_not_called()
        self.assertNotIn("planting_equipment", snapshot)

    def test_closed_policy_and_open_private_garden_project_without_world_locks(self):
        for open_policy, map_id in ((False, 1134), (True, 9)):
            with self.subTest(open_policy=open_policy, map_id=map_id):
                bridge = self.bridge(open_policy=open_policy, map_id=map_id)
                result = [{"intent_id": "owned-intent", "plant_probability": 10}]

                def project(*args, **kwargs):
                    self.assertFalse(self.world_lock._is_owned())
                    self.assertFalse(self.harvest_lock._is_owned())
                    return result

                with patch(
                    "wakfu_server.planting_equipment_projection.pending_projection",
                    side_effect=project,
                ) as projected:
                    snapshot = bridge.snapshot()
                projected.assert_called_once_with(
                    bridge.store, bridge.epoch, 1_000_250, gardens_only=open_policy
                )
                self.assertEqual(snapshot["planting_equipment"], result)

    def test_catalog_pins_are_validated_scalar_metadata_not_credentials(self):
        bridge = self.bridge(open_policy=True, map_id=1134)
        with patch.dict(
            "os.environ",
            {
                "WAKFU_CATALOG_REVISION": "a" * 64,
                "WAKFU_COMPILED_CATALOG_GENERATION": "b" * 64,
            },
        ):
            snapshot = bridge.snapshot()
        self.assertEqual(snapshot["catalog_revision"], "a" * 64)
        self.assertEqual(snapshot["compiled_catalog_generation"], "b" * 64)
        self.assertNotIn("token", snapshot)
        with patch.dict("os.environ", {"WAKFU_CATALOG_REVISION": "wrong"}):
            with self.assertRaisesRegex(ValueError, "catalog identity"):
                bridge.snapshot()


if __name__ == "__main__":
    unittest.main()
