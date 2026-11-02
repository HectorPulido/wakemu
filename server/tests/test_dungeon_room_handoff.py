"""Victory is durable while next-room hydration recovers independently."""
from contextlib import contextmanager
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock, patch

from psycopg.errors import LockNotAvailable, UndefinedTable
from wakfu_server import dungeon_room_handoff, dungeon_runtime


class TransactionFixture:
    def __init__(self, *, completed=False):
        self.progress = dict(
            current_room=2, status="completed" if completed else "active", revision=7
        )
        self.encounter = dict(
            status="victory",
            encounter_scope="main",
            result_revision=7,
            result=dict(victory=True, completed=completed, current_room=2, revision=7),
        )
        self.groups = []
        self.rewards = ["earned"]

    def execute(self, sql, args):
        if sql.startswith("SELECT current_room"):
            return Mock(fetchone=lambda: self.progress)
        if sql.startswith("SELECT status"):
            return Mock(fetchone=lambda: self.encounter)
        if sql.startswith("UPDATE dungeon_room_encounters"):
            self.encounter["result"]["room_hydration"] = json.loads(args[0])
            return Mock()
        raise AssertionError(sql)

    @contextmanager
    def transaction(self):
        saved = deepcopy(self.groups)
        try:
            yield
        except Exception:
            self.groups[:] = saved
            raise


class RoomHandoffTests(unittest.TestCase):
    def prepare(self, db, *, now=100):
        return dungeon_room_handoff.prepare(
            db,
            "groups",
            instance_id=31,
            fight_id=91,
            map_id=10,
            geometry_provider=lambda map_id: dict(map_id=map_id),
            now=now,
        )

    def test_failed_spawn_preserves_victory_and_retries_once_after_backoff(self):
        for error in (
            ValueError("Missing published terrain"),
            LockNotAvailable("busy"),
        ):
            with self.subTest(error=type(error).__name__):
                db = TransactionFixture()

                def fail(*args):
                    db.groups.append("partial")
                    raise error

                with patch.object(
                    dungeon_runtime, "ensure_current_room", side_effect=fail
                ) as hydrate:
                    first = self.prepare(db)
                    self.assertFalse(first["ready"])
                    self.assertEqual(first["next_retry"], 102)
                    self.assertEqual(db.groups, [])
                    self.assertEqual(db.rewards, ["earned"])
                    self.assertTrue(db.encounter["result"]["victory"])
                    self.assertEqual(db.progress["current_room"], 2)
                    self.assertEqual(self.prepare(db, now=101)["state"], "deferred")
                    hydrate.assert_called_once()
                with patch.object(
                    dungeon_runtime,
                    "ensure_current_room",
                    side_effect=lambda *args: db.groups.append("complete"),
                ) as hydrate:
                    self.assertTrue(self.prepare(db, now=102)["ready"])
                    self.assertTrue(self.prepare(db, now=103)["replay"])
                    hydrate.assert_called_once()
                self.assertEqual(db.groups, ["complete"])
                self.assertEqual(
                    db.encounter["result"]["room_hydration"]["attempts"], 2
                )

    def test_completed_main_run_does_not_require_retired_final_geometry(self):
        db = TransactionFixture(completed=True)
        with patch.object(dungeon_runtime, "ensure_current_room") as hydrate:
            result = dungeon_room_handoff.prepare(
                db,
                "groups",
                instance_id=31,
                fight_id=91,
                map_id=10,
                geometry_provider=Mock(
                    side_effect=AssertionError("Unnecessary geometry")
                ),
                now=100,
            )
        self.assertTrue(result["ready"])
        hydrate.assert_called_once_with(db, "groups", 31, None)

    def test_obsolete_or_nonmain_receipt_cannot_hydrate_or_publish(self):
        for mutation in (
            {"result_revision": 6},
            {"status": "defeat"},
            {"encounter_scope": "optional"},
        ):
            db = TransactionFixture()
            db.encounter.update(mutation)
            with patch.object(dungeon_runtime, "ensure_current_room") as hydrate:
                self.assertEqual(self.prepare(db), dict(state="obsolete", ready=False))
                hydrate.assert_not_called()
            self.assertNotIn("room_hydration", db.encounter["result"])

    def test_unrelated_database_error_is_not_disguised_as_recovery(self):
        db = TransactionFixture()
        with patch.object(
            dungeon_runtime,
            "ensure_current_room",
            side_effect=UndefinedTable("broken schema"),
        ):
            with self.assertRaises(UndefinedTable):
                self.prepare(db)
        self.assertNotIn("room_hydration", db.encounter["result"])

    def test_repeated_geometry_failure_requests_safe_exit_but_contention_does_not(self):
        for error in (
            ValueError("Missing published terrain"),
            LockNotAvailable("busy"),
        ):
            db = TransactionFixture()
            with patch.object(
                dungeon_runtime, "ensure_current_room", side_effect=error
            ):
                for now in (100, 102, 106):
                    result = self.prepare(db, now=now)
                self.assertEqual(
                    result["recovery_required"], isinstance(error, ValueError)
                )
                deferred = self.prepare(db, now=107)
                self.assertEqual(
                    deferred["recovery_required"], result["recovery_required"]
                )
            self.assertTrue(db.encounter["result"]["victory"])

    def test_completed_runtime_skips_main_spawn_but_preserves_postboss_nodes(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = dict(
            current_room=2, status="completed"
        )
        from wakfu_server import dungeon_postboss_nodes, dungeon_resource_obstacles

        for postboss in (False, True):
            topology = dict(asset_map_id=10)
            if postboss:
                topology["entry_path_policy"] = {"fixture": True}
            config = dict(topology=topology)
            with patch.object(
                dungeon_runtime, "configuration_for_instance", return_value=({}, config)
            ), patch.object(
                dungeon_postboss_nodes, "ensure_groups", return_value="nodes"
            ) as nodes, patch.object(
                dungeon_resource_obstacles, "ensure"
            ) as obstacles:
                result = dungeon_runtime.ensure_current_room(db, "groups", 31, None)
                self.assertEqual(result, "nodes" if postboss else None)
                self.assertEqual(nodes.call_count, int(postboss))
                obstacles.assert_not_called()


if __name__ == "__main__":
    unittest.main()
