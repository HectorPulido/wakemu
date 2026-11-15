import unittest
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import rii_training_arena as arena


class FakeDB:
    def __init__(self, store):
        self.store = store
        self.row = None

    def execute(self, query, args=()):
        if "FROM combat_fight_participants" in query:
            self.row = {"fight": 1} if self.store.fighting else None
        elif query.startswith("SELECT * FROM rii_training_transits"):
            self.row = (
                self.store.transit
                if self.store.transit and self.store.transit["character_id"] == args[0]
                else None
            )
        elif query.startswith("SELECT 1 FROM rii_training_transits"):
            self.row = (
                self.store.transit
                if self.store.transit
                and (
                    self.store.transit["account_id"],
                    self.store.transit["character_id"],
                )
                == tuple(args)
                else None
            )
        elif query.startswith("SELECT source_x,source_y,source_z,floor_x"):
            self.row = [self.store.transit] if self.store.transit else []
        elif query.startswith("INSERT INTO rii_training_transits"):
            character, account, world, instance, x, y, z, fx, fy, fz, objective = args
            self.store.transit = dict(
                character_id=character,
                account_id=account,
                source_map=world,
                source_instance=instance,
                source_x=x,
                source_y=y,
                source_z=z,
                floor_x=fx,
                floor_y=fy,
                floor_z=fz,
                lesson_objective=objective,
                setup_failed=True,
            )
        elif query.startswith("UPDATE rii_training_transits SET setup_failed"):
            if self.store.transit:
                self.store.transit["setup_failed"] = "SET setup_failed=true" in query
            self.row = self.store.transit
        elif query.startswith("DELETE FROM rii_training_transits"):
            self.store.transit = None
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.row


class FakeStore:
    def __init__(self):
        self.current = dict(
            id=7, account_id=3, map_id=1388, instance_id=0, x=1, y=-19, z=3
        )
        self.transit = None
        self.fighting = False
        self.fail = False

    @contextmanager
    def connection(self):
        old = deepcopy((self.current, self.transit))
        try:
            yield FakeDB(self)
        except Exception:
            self.current, self.transit = old
            raise

    def lock_character(self, db, account, generation, character, selected=True):
        if (account, generation, character) != (3, "session", 7):
            raise ValueError("Not owner")

    def character(self, account, character, db):
        return deepcopy(self.current)

    def transition_map_in_transaction(
        self, db, account, generation, character, source, destination
    ):
        if self.fail:
            raise ValueError("Injected failure")
        self.current.update(destination)
        return deepcopy(self.current)


class RiiTrainingTransitTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.original = deepcopy(self.store.current)
        geometry = SimpleNamespace(cells={(0, -16, 0)})
        self.geometry = patch(
            "wakfu_server.combat_geometry.published_geometry", return_value=geometry
        )
        self.geometry.start()
        self.addCleanup(self.geometry.stop)

    def test_only_raised_or_pending_training_requires_a_transit(self):
        floor = dict(self.original, z=0)
        raised = dict(self.original, z=3)
        self.assertFalse(arena.requires_transit(floor, has_pending=False))
        self.assertTrue(arena.requires_transit(raised, has_pending=False))
        self.assertTrue(arena.requires_transit(floor, has_pending=True))
        with self.assertRaisesRegex(ValueError, "public Rii dojo"):
            arena.requires_transit(dict(floor, map_id=1385), has_pending=False)

    def test_foreign_receipt_reserves_only_private_floor(self):
        # Another player may share this public source. Their durable private
        # floor remains reserved, so this lesson must choose the next cell.
        self.store.transit = {
            "character_id": 99,
            "account_id": 88,
            "source_map": 1388,
            "source_instance": 0,
            "source_x": self.original["x"],
            "source_y": self.original["y"],
            "source_z": self.original["z"],
            "floor_x": 0,
            "floor_y": -16,
            "floor_z": 0,
            "lesson_objective": 10609,
            "setup_failed": False,
        }
        self.geometry.stop()
        geometry = SimpleNamespace(cells={(0, -16, 0), (1, -16, 0)})
        self.geometry = patch(
            "wakfu_server.combat_geometry.published_geometry", return_value=geometry
        )
        self.geometry.start()
        self.addCleanup(self.geometry.stop)

        moved = self.enter()

        self.assertEqual((moved["x"], moved["y"], moved["z"]), (1, -16, 0))
        self.assertEqual(self.store.transit["source_x"], self.original["x"])
        self.assertEqual(self.store.transit["character_id"], 7)

    def test_return_occupancy_allows_players_but_still_blocks_public_monsters(self):
        peer = dict(self.original, id=99)
        monster_group = {"members": [{"x": 2, "y": -16, "z": 0}]}

        entry_occupied = arena.occupied_positions(
            [self.original, peer], [monster_group], self.original["id"]
        )
        return_occupied = arena.occupied_positions(
            [self.original, peer], [monster_group], self.original["id"], returning=True
        )

        self.assertIn((1388, 0, peer["x"], peer["y"], peer["z"]), entry_occupied)
        self.assertNotIn((1388, 0, peer["x"], peer["y"], peer["z"]), return_occupied)
        self.assertIn((1388, 0, 2, -16, 0), entry_occupied)
        self.assertIn((1388, 0, 2, -16, 0), return_occupied)

    def enter(self):
        return arena.enter(
            self.store,
            3,
            "session",
            self.original,
            10608,
            available=lambda position: True,
        )

    def test_owned_transit_and_durable_return_after_reconnection(self):
        self.assertEqual(self.enter()["z"], 0)
        self.assertEqual(self.store.transit["source_z"], 3)
        # The state is read from storage, not a connection-local return marker.
        self.store.current.update(x=2, y=-10)
        self.assertEqual(
            arena.return_to_source(
                self.store,
                3,
                "session",
                deepcopy(self.store.current),
                available=lambda position: True,
            ),
            self.original,
        )
        self.assertIsNone(self.store.transit)
        self.assertIsNone(
            arena.return_to_source(
                self.store,
                3,
                "session",
                deepcopy(self.store.current),
                available=lambda position: True,
            )
        )

    def test_failure_rolls_back_receipt_and_busy_fight_prevents_move(self):
        self.store.fail = True
        with self.assertRaises(ValueError):
            self.enter()
        self.assertIsNone(self.store.transit)
        self.assertEqual(self.store.current, self.original)
        self.store.fail = False
        self.store.fighting = True
        with self.assertRaises(ValueError):
            self.enter()
        self.assertIsNone(self.store.transit)

    def test_no_forced_return_after_player_leaves_and_occupied_source_waits(self):
        self.enter()
        self.assertIsNone(
            arena.return_to_source(
                self.store,
                3,
                "session",
                deepcopy(self.store.current),
                available=lambda position: False,
            )
        )
        self.assertIsNotNone(self.store.transit)
        self.store.current.update(map_id=527, x=0, y=32, z=0)
        self.assertIsNone(
            arena.return_to_source(
                self.store,
                3,
                "session",
                deepcopy(self.store.current),
                available=lambda position: True,
                only_completed=True,
            )
        )
        self.assertIsNone(self.store.transit)
        self.assertEqual(self.store.current["map_id"], 527)

    def test_login_recovery_does_not_cancel_an_unfinished_lesson(self):
        floor = self.enter()
        with self.store.connection() as db:
            arena.mark_setup_ready_in_transaction(
                db, dict(floor, _rii_training_objective=10608), 10608
            )
        with patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value={"objectives": []},
        ):
            self.assertIsNone(
                arena.return_to_source(
                    self.store,
                    3,
                    "session",
                    deepcopy(self.store.current),
                    available=lambda position: True,
                    only_completed=True,
                )
            )
        self.assertIsNotNone(self.store.transit)
        with patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value={"objectives": [10608]},
        ):
            self.assertEqual(
                arena.return_to_source(
                    self.store,
                    3,
                    "session",
                    deepcopy(self.store.current),
                    available=lambda position: True,
                    only_completed=True,
                ),
                self.original,
            )

    def test_failed_setup_publishes_actual_floor_when_return_is_deferred(self):
        events = []
        floor = {"x": 1, "y": -16, "z": 0}
        with self.assertRaisesRegex(ValueError, "could not be prepared"):
            arena.stage(
                lambda: floor,
                lambda moved: None,
                lambda moved: None,
                lambda moved: events.append(("floor", moved)),
                lambda moved: events.append(("source", moved)),
                lambda moved: events.append(("failed", moved)),
                lambda moved: False,
            )
        self.assertEqual(events, [("failed", floor), ("floor", floor)])

    def test_failed_setup_reattaches_returned_source_without_floor_bootstrap(self):
        events = []
        with self.assertRaisesRegex(ValueError, "could not be prepared"):
            arena.stage(
                lambda: arena.FLOOR,
                lambda moved: None,
                lambda moved: self.original,
                lambda moved: events.append(("floor", moved)),
                lambda moved: events.append(("source", moved)),
                lambda moved: events.append(("failed", moved)),
                lambda moved: False,
            )
        self.assertEqual(events, [("failed", arena.FLOOR), ("source", self.original)])

    def test_failed_setup_returns_on_reconnect_without_completed_objective(self):
        floor = self.enter()
        arena.mark_setup_failed(self.store, 3, "session", floor)
        self.assertTrue(self.store.transit["setup_failed"])
        with patch(
            "wakfu_server.achievements.storage.load_locked",
            side_effect=AssertionError("failed setup must not need quest state"),
        ):
            returned = arena.return_to_source(
                self.store,
                3,
                "session",
                floor,
                available=lambda position: True,
                only_completed=True,
            )
        self.assertEqual(returned, self.original)

    def test_failed_marker_still_attempts_return_and_preserves_setup_error(self):
        floor = self.enter()
        events = []

        def fail_marker(_moved):
            raise RuntimeError("injected marker failure")

        with self.assertRaisesRegex(ValueError, "could not be prepared") as caught:
            arena.stage(
                lambda: floor,
                lambda moved: None,
                lambda moved: events.append("return") or None,
                lambda moved: events.append("floor"),
                lambda moved: events.append("source"),
                fail_marker,
                lambda moved: False,
            )
        self.assertEqual(events, ["return", "floor"])
        self.assertTrue(self.store.transit["setup_failed"])
        self.assertTrue(
            any("marker failed" in note for note in caught.exception.__notes__)
        )
        with patch(
            "wakfu_server.achievements.storage.load_locked",
            side_effect=AssertionError("incomplete state must recover"),
        ):
            self.assertEqual(
                arena.return_to_source(
                    self.store,
                    3,
                    "session",
                    floor,
                    available=lambda position: True,
                    only_completed=True,
                ),
                self.original,
            )

    def test_successful_setup_publishes_committed_encounter(self):
        events = []
        result = arena.stage(
            lambda: arena.FLOOR,
            lambda moved: (12608, b"group"),
            lambda moved: events.append("return"),
            lambda moved: events.append("floor"),
            lambda moved: events.append("source"),
            lambda moved: events.append("failed"),
            lambda moved: False,
        )
        self.assertEqual(result, (12608, b"group"))
        self.assertEqual(events, ["floor"])

    def test_ambiguous_producer_commit_preserves_ready_group_on_floor(self):
        events = []

        def lost_commit(_moved):
            raise RuntimeError("connection lost after commit")

        with self.assertRaisesRegex(RuntimeError, "connection lost"):
            arena.stage(
                lambda: arena.FLOOR,
                lost_commit,
                lambda moved: events.append("return"),
                lambda moved: events.append("floor"),
                lambda moved: events.append("source"),
                lambda moved: events.append("failed"),
                lambda moved: True,
            )
        self.assertEqual(events, ["floor"])


if __name__ == "__main__":
    unittest.main()
