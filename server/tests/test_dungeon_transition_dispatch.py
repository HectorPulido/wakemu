import ast
import copy
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import Mock


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _dispatcher_nodes():
    module = ast.parse(SERVER_SOURCE.read_text(encoding="utf8"))
    session = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )
    nested = {
        node.name: node
        for node in ast.walk(session)
        if isinstance(node, ast.FunctionDef)
    }
    return module, session, nested


class DungeonTransitionDispatchTests(unittest.TestCase):
    def test_transition_outbox_table_is_checked_after_startup_migrations(self):
        module, _session, _nested = _dispatcher_nodes()
        registrations = [
            node
            for node in ast.walk(module)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            and any(
                isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and "to_regclass('dungeon_transition_outbox')" in arg.value
                for arg in node.args
            )
        ]
        self.assertEqual(len(registrations), 1)
        self.assertTrue(
            any(
                isinstance(node, ast.Name)
                and node.id == "DUNGEON_TRANSITION_OUTBOX_AVAILABLE"
                for node in ast.walk(_nested["deliver_dungeon_transitions"])
            )
        )

    def test_idle_and_loaded_action_path_poll_the_session_owned_worker(self):
        _module, session, nested = _dispatcher_nodes()
        idle_polls = [
            node
            for node in ast.walk(nested["idle"])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "deliver_dungeon_transitions"
        ]
        self.assertTrue(idle_polls)

        action_polls = [
            node
            for node in ast.walk(session)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "deliver_dungeon_transitions"
            and any(
                keyword.arg == "before_action"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            )
        ]
        position_flushes = [
            node
            for node in ast.walk(session)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "flush_positions"
        ]
        self.assertTrue(action_polls)
        self.assertTrue(
            any(node.lineno > action_polls[0].lineno for node in position_flushes)
        )

    def _bootstrap(self, *, prepare, send_packet=None):
        _module, _session, nested = _dispatcher_nodes()
        bootstrap = copy.deepcopy(nested["bootstrap_dungeon_event"])
        # The production callback closes over session state. Replacing its
        # nonlocal declaration with global lets this isolated AST-extracted
        # function execute against an explicit test namespace.
        for node in ast.walk(bootstrap):
            if isinstance(node, ast.Nonlocal):
                node.__class__ = ast.Global
        namespace = {
            "character": {
                "id": 21,
                "map_id": 1086,
                "instance_id": 4,
                "x": 1,
                "y": 2,
                "z": 0,
            }
        }
        calls = []

        def record(name, value=None):
            def invoke(*args, **kwargs):
                calls.append((name, args, kwargs))
                return value

            return invoke

        plan = SimpleNamespace(
            character={
                "id": 21,
                "map_id": 1086,
                "instance_id": 9,
                "x": 10,
                "y": 11,
                "z": 0,
            },
            packets=((101, b"first"), (102, b"second")),
        )
        world = SimpleNamespace(leave=record("world.leave"))
        positions = SimpleNamespace(attach=record("positions.attach"))

        def movement(position):
            calls.append(("movement", (position,), {}))
            return {"position": position}

        namespace.update(
            {
                "dungeon_hydration": SimpleNamespace(
                    prepare_transition=record("prepare", plan)
                    if prepare is None
                    else prepare
                ),
                "STORE": object(),
                "account_id": 7,
                "generation": "gen-3",
                "cancel_crafting": record("cancel_crafting"),
                "WORLD": world,
                "POSITIONS": positions,
                "position": {"x": 1, "y": 2, "z": 0},
                "movement_state": None,
                "Movement": movement,
                "send": record("send") if send_packet is None else send_packet,
                "connection": object(),
                "service": object(),
                "join_world": record("join_world"),
                "mark_static_sync_pending": record("mark_static_sync_pending"),
                "acknowledge_transition": Mock(),
            }
        )
        module = ast.Module(body=[bootstrap], type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, str(SERVER_SOURCE), "exec"), namespace)
        return namespace["bootstrap_dungeon_event"], namespace, calls

    def test_invalid_hydration_plan_fails_before_world_or_position_mutation(self):
        failure = ValueError("destination context unavailable")

        def reject(*_args):
            raise failure

        bootstrap, namespace, calls = self._bootstrap(prepare=reject)
        with self.assertRaisesRegex(ValueError, "destination context unavailable"):
            bootstrap({"event_id": 31})

        self.assertEqual([], calls)
        namespace["acknowledge_transition"].assert_not_called()

    def test_valid_plan_runs_complete_bootstrap_in_order(self):
        bootstrap, namespace, calls = self._bootstrap(prepare=None)

        self.assertIs(True, bootstrap({"event_id": 31}))
        self.assertEqual(
            [
                "prepare",
                "cancel_crafting",
                "world.leave",
                "positions.attach",
                "movement",
                "send",
                "send",
                "join_world",
                "mark_static_sync_pending",
            ],
            [name for name, _args, _kwargs in calls],
        )
        self.assertEqual((101, b"first"), calls[5][1][2:])
        self.assertEqual((102, b"second"), calls[6][1][2:])
        self.assertEqual(9, namespace["character"]["instance_id"])
        self.assertEqual({"x": 10, "y": 11, "z": 0}, namespace["position"])
        namespace["acknowledge_transition"].assert_not_called()

    def test_send_failure_never_completes_bootstrap_or_acknowledges_event(self):
        failure = OSError("socket write failed")
        sends = 0

        def fail_send(*_args):
            nonlocal sends
            sends += 1
            raise failure

        bootstrap, namespace, calls = self._bootstrap(
            prepare=None, send_packet=fail_send
        )
        with self.assertRaisesRegex(OSError, "socket write failed"):
            bootstrap({"event_id": 31})

        self.assertEqual(1, sends)
        self.assertEqual(
            [
                "prepare",
                "cancel_crafting",
                "world.leave",
                "positions.attach",
                "movement",
            ],
            [name for name, _args, _kwargs in calls],
        )
        namespace["acknowledge_transition"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
