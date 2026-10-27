"""Run actual socket helpers without starting the world service."""
import ast
import copy
import threading
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.combat_shared import Transition

SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def helper(name, namespace):
    module = ast.parse(SERVER.read_text())
    session = next(
        n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "session"
    )
    node = copy.deepcopy(
        next(
            n
            for n in ast.walk(session)
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
    )
    node.decorator_list = []
    for child in ast.walk(node):
        if hasattr(child, "body") and isinstance(child.body, list):
            child.body = [
                ast.Global(names=n.names) if isinstance(n, ast.Nonlocal) else n
                for n in child.body
            ]
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(SERVER), "exec"), namespace)
    return namespace[name]


class RiftDispatchTests(unittest.TestCase):
    def _checkpoint(self):
        store, checkpoints = Mock(), Mock()
        store.current_character_session.return_value = True
        checkpoints.save.return_value = 8
        function = helper(
            "checkpoint_accepted_rift", {"STORE": store, "CHECKPOINTS": checkpoints}
        )
        owner = SimpleNamespace(account_id=2, generation="current", character_id=3)
        shared = SimpleNamespace(participants={2: owner}, checkpoint_revision=7)
        candidate, runtime = object(), object()
        transition = Transition(candidate, runtime, ((123, b"owned"),))
        return function, shared, transition, store, checkpoints

    def test_accepted_wave_checkpoint_uses_canonical_revision_and_current_lease(self):
        function, shared, transition, store, checkpoints = self._checkpoint()
        with patch(
            "wakfu_server.rift_dispatch_combat.finish_accepted_action",
            return_value=transition,
        ):
            self.assertIs(
                function(shared, transition.fight, transition.runtime, ()), transition
            )
        checkpoints.save.assert_called_once_with(
            2,
            "current",
            transition.fight,
            expected_revision=7,
            runtime=transition.runtime,
        )
        self.assertEqual(shared.checkpoint_revision, 8)

    def test_failed_checkpoint_preserves_revision_and_returns_no_public_batch(self):
        function, shared, transition, store, checkpoints = self._checkpoint()
        checkpoints.save.side_effect = ValueError("rollback")
        with patch(
            "wakfu_server.rift_dispatch_combat.finish_accepted_action",
            return_value=transition,
        ):
            with self.assertRaisesRegex(ValueError, "rollback"):
                function(shared, transition.fight, transition.runtime, ())
        self.assertEqual(shared.checkpoint_revision, 7)

    def test_replaced_participant_cannot_write_rift_checkpoint(self):
        function, shared, transition, store, checkpoints = self._checkpoint()
        store.current_character_session.return_value = False
        with patch(
            "wakfu_server.rift_dispatch_combat.finish_accepted_action",
            return_value=transition,
        ):
            with self.assertRaisesRegex(ValueError, "current participant"):
                function(shared, transition.fight, transition.runtime, ())
        checkpoints.save.assert_not_called()

    def test_nonrift_start_does_not_query_database(self):
        store = Mock()
        function = helper(
            "prepare_rift_start", {"STORE": store, "character": {"instance_id": 0}}
        )
        self.assertIsNone(function(b"invalid"))
        store.connection.assert_not_called()

    def test_native_start_authority_rejection_keeps_socket_handler_alive(self):
        store = Mock()
        store.connection = lambda: nullcontext(Mock())
        record = Mock()
        function = helper(
            "prepare_rift_start",
            {
                "STORE": store,
                "character": {"instance_id": (1 << 58) + 1, "id": 3},
                "account_id": 2,
                "generation": "current",
                "record": record,
            },
        )
        with patch(
            "wakfu_server.rift_entry_adapter.authorize_start",
            side_effect=ValueError("wrong source"),
        ):
            self.assertIsNone(function(b"invalid"))
        self.assertEqual(record.call_args.kwargs["event"], "rift_start_rejected")

    def _start_hydration(self, *, pending=None, visible_generation="current"):
        instance_id = (1 << 58) + 1
        rows = [
            {
                "id": 3,
                "account_id": 2,
                "generation": "current",
                "selected_character_id": 3,
            }
        ]
        db, store, record = Mock(), Mock(), Mock()
        db.execute.return_value.fetchall.return_value = rows
        store.connection = lambda: nullcontext(db)
        run = {"members": [3], "instance_id": instance_id}
        world = SimpleNamespace(
            lock=threading.RLock(),
            players={
                3: (
                    visible_generation,
                    None,
                    {"map_id": 1314, "instance_id": instance_id},
                ),
            },
            location=lambda value: (value["map_id"], value["instance_id"]),
        )
        function = helper(
            "prepare_rift_start",
            {
                "STORE": store,
                "WORLD": world,
                "account_id": 2,
                "generation": "current",
                "character": {"id": 3, "map_id": 1314, "instance_id": instance_id},
                "record": record,
            },
        )
        with patch(
            "wakfu_server.rift_entry_adapter.authorize_start", return_value=run
        ), patch("wakfu_server.rift_transition_delivery.pending", return_value=pending):
            return function(b"native"), run, record

    def test_pending_map_hydration_prevents_starting_before_map_bootstrap(self):
        result, run, record = self._start_hydration(pending={"map_id": 1314})
        self.assertIsNone(result)
        self.assertIn("load the interior", record.call_args.kwargs["reason"])

    def test_replaced_visible_world_generation_blocks_start(self):
        result, run, record = self._start_hydration(visible_generation="old-session")
        self.assertIsNone(result)
        self.assertIn("finish loading", record.call_args.kwargs["reason"])

    def test_current_hydrated_world_member_can_start(self):
        result, run, record = self._start_hydration()
        self.assertIs(result, run)
        record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
