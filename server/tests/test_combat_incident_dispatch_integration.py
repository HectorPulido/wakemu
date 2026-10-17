"""Inspect dispatcher capture boundaries without booting the world service."""
import ast
from contextlib import nullcontext
from pathlib import Path
import types
import unittest
from unittest.mock import MagicMock, patch


SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


def dispatcher_function(name):
    tree = ast.parse(SOURCE.read_text())
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


class IncidentDispatchIntegrationTests(unittest.TestCase):
    def helper(self, **overrides):
        namespace = dict(
            os=__import__("os"),
            nullcontext=nullcontext,
            combat_session=types.SimpleNamespace(account_id=3),
            COMBAT_TEST_CRITICAL_BRANCH="auto",
            TEST_MONSTERS_BY_ID={-7: {"id": -7}},
            record=lambda **fields: None,
        )
        namespace.update(overrides)
        tree = ast.Module(
            body=[dispatcher_function("shared_action_incident")], type_ignores=[]
        )
        exec(compile(ast.fix_missing_locations(tree), str(SOURCE), "exec"), namespace)
        return namespace["shared_action_incident"]

    def test_disabled_capture_never_imports_capture_or_builds_evidence(self):
        helper = self.helper()
        with patch.dict("os.environ", {}, clear=True):
            # Invalid source/session evidence must not be inspected disabled.
            with helper(
                object(), "player_spell", b"request", None, None, None, None
            ) as incident:
                self.assertIsNone(incident)

    def test_enabled_capture_preserves_exact_inputs_and_unqualified_recipe(self):
        calls = []
        module = types.ModuleType("wakfu_server.combat_incident_capture")
        module.incident_enabled = lambda: True
        module.incident_scope = lambda *args, **kwargs: calls.append(
            (args, kwargs)
        ) or nullcontext("capture")
        source = {"id": 7, "account_id": 3, "map_id": 1134}
        characters, decks = {7: source}, {7: b"deck"}
        runtime = types.SimpleNamespace(
            fight=types.SimpleNamespace(
                actors={
                    7: types.SimpleNamespace(owner_id=3),
                    -7: types.SimpleNamespace(owner_id=None),
                }
            )
        )
        with patch.dict(
            "os.environ", {"WAKFU_COMBAT_INCIDENT_DIR": "/private/incidents"}
        ), patch.dict("sys.modules", {module.__name__: module}):
            with self.helper()(
                runtime, "player_spell", b"request", source, decks[7], characters, decks
            ) as incident:
                self.assertEqual(incident, "capture")
        args, kwargs = calls[0]
        self.assertIs(args[0], runtime)
        self.assertEqual(
            args[1],
            dict(type="player_spell", body=b"request", owner_id=3, critical=None),
        )
        self.assertEqual(args[2]["authority_recipe"], "observed-live-server-v1")
        self.assertIs(args[2]["character"], source)
        self.assertIs(args[2]["player_characters"], characters)
        self.assertIs(args[2]["deck_blobs"], decks)
        self.assertEqual(kwargs["recipients"], (3,))
        self.assertEqual(
            args[2]["recipient_evidence"],
            "intended-participant-accounts-not-confirmed-routing",
        )

    def test_enabled_diagnostic_setup_failure_does_not_replace_gameplay(self):
        module = types.ModuleType("wakfu_server.combat_incident_capture")
        module.incident_enabled = lambda: True
        module.incident_scope = lambda *args, **kwargs: self.fail(
            "Incomplete evidence reached capture"
        )
        with patch.dict(
            "os.environ", {"WAKFU_COMBAT_INCIDENT_DIR": "/private/incidents"}
        ), patch.dict("sys.modules", {module.__name__: module}):
            with self.helper()(
                object(), "player_spell", b"request", {}, None, {}, {}
            ) as incident:
                self.assertIsNone(incident)

    def test_end_turn_capture_does_not_add_source_reads(self):
        source = {"id": 7, "account_id": 3, "map_id": 1134}
        sessions = types.SimpleNamespace(
            player_sources=MagicMock(return_value=({7: source}, {7: b"deck"}))
        )
        session = types.SimpleNamespace(account_id=3, character_id=7, map_id=1134)
        runtime = types.SimpleNamespace(
            fight=types.SimpleNamespace(actors={7: types.SimpleNamespace(owner_id=3)})
        )
        helper = self.helper(COMBAT_SESSIONS=sessions, combat_session=session)
        with patch.dict("os.environ", {}, clear=True):
            with helper(
                runtime,
                "end_turn",
                b"request",
                None,
                None,
                None,
                None,
                actor_id=7,
                turn_id=2,
            ):
                pass
        sessions.player_sources.assert_not_called()
        calls = []
        module = types.ModuleType("wakfu_server.combat_incident_capture")
        module.incident_enabled = lambda: True
        module.incident_scope = (
            lambda *args, **kwargs: calls.append((args, kwargs)) or nullcontext()
        )
        with patch.dict(
            "os.environ", {"WAKFU_COMBAT_INCIDENT_DIR": "/private/incidents"}
        ), patch.dict("sys.modules", {module.__name__: module}):
            with helper(
                runtime,
                "end_turn",
                b"request",
                None,
                None,
                None,
                None,
                actor_id=7,
                turn_id=2,
            ):
                pass
            with helper(
                runtime, "move", b"move", source, b"deck", {7: source}, {7: b"deck"}
            ):
                pass
        sessions.player_sources.assert_not_called()
        self.assertEqual(
            calls[0][0][1], dict(type="end_turn", owner_id=3, actor_id=7, turn_id=2)
        )
        self.assertEqual(calls[0][0][2]["client_request_body"], b"request")
        self.assertNotIn("character", calls[0][0][2])
        self.assertNotIn("player_characters", calls[0][0][2])
        self.assertEqual(calls[1][0][1], dict(type="move", owner_id=3, body=b"move"))

    def test_end_turn_operation_preserves_original_arguments_packets_and_error(self):
        runtime = types.SimpleNamespace(
            end_turn=MagicMock(return_value=[(123, b"packet")])
        )
        candidate = object()
        namespace = dict(
            shared_action_incident=lambda *args, **kwargs: nullcontext(),
            combat_session=types.SimpleNamespace(account_id=3),
            actor_id=7,
            actor_turn=2,
            body=b"request",
            Transition=lambda *args: args,
        )
        tree = ast.Module(
            body=[dispatcher_function("shared_end_turn")], type_ignores=[]
        )
        exec(compile(ast.fix_missing_locations(tree), str(SOURCE), "exec"), namespace)
        operation = namespace["shared_end_turn"]
        self.assertEqual(
            operation(candidate, runtime), (candidate, runtime, ((123, b"packet"),))
        )
        runtime.end_turn.assert_called_once_with(3, 7, 2)
        error = ValueError("original end-turn rejection")
        runtime.end_turn.side_effect = error
        with self.assertRaises(ValueError) as raised:
            operation(candidate, runtime)
        self.assertIs(raised.exception, error)

    def test_shared_operations_capture_complete_packet_batch_before_transition(self):
        for name in ("shared_cast", "shared_weapon"):
            with self.subTest(name=name):
                function = dispatcher_function(name)
                scope = next(
                    node
                    for node in ast.walk(function)
                    if isinstance(node, ast.With)
                    and isinstance(node.items[0].context_expr, ast.Call)
                    and isinstance(node.items[0].context_expr.func, ast.Name)
                    and node.items[0].context_expr.func.id == "shared_action_incident"
                )
                calls = [node for node in ast.walk(scope) if isinstance(node, ast.Call)]
                prepare = next(
                    node
                    for node in calls
                    if isinstance(node.func, ast.Name)
                    and node.func.id
                    in ("prepare_server_spell", "prepare_server_weapon")
                )
                commit = next(
                    node
                    for node in calls
                    if isinstance(node.func, ast.Name)
                    and node.func.id == "commit_spell_transaction"
                )
                observe = next(
                    node
                    for node in calls
                    if isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "incident"
                    and node.func.attr == "packets"
                )
                transition = next(
                    node
                    for node in calls
                    if isinstance(node.func, ast.Name) and node.func.id == "Transition"
                )
                self.assertLess(prepare.lineno, commit.lineno)
                self.assertLess(commit.lineno, observe.lineno)
                self.assertLess(observe.lineno, transition.lineno)
                self.assertEqual(ast.unparse(observe.args[0]), "packets")
                self.assertEqual(ast.unparse(transition.args[-1]), "tuple(packets)")

    def test_movement_and_end_turn_capture_original_delivery_before_transition(self):
        for name, operation_name in (
            ("shared_move", "apply_client"),
            ("shared_end_turn", "end_turn"),
        ):
            with self.subTest(name=name):
                function = dispatcher_function(name)
                scope = next(
                    node for node in ast.walk(function) if isinstance(node, ast.With)
                )
                calls = [node for node in ast.walk(scope) if isinstance(node, ast.Call)]
                operation = next(
                    node
                    for node in calls
                    if (
                        isinstance(node.func, ast.Name)
                        and node.func.id == operation_name
                        or isinstance(node.func, ast.Attribute)
                        and node.func.attr == operation_name
                    )
                )
                observe = next(
                    node
                    for node in calls
                    if isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "incident"
                    and node.func.attr == "packets"
                )
                transition = next(
                    node
                    for node in calls
                    if isinstance(node.func, ast.Name) and node.func.id == "Transition"
                )
                self.assertLess(operation.lineno, observe.lineno)
                self.assertLess(observe.lineno, transition.lineno)
                self.assertEqual(ast.unparse(observe.args[0]), "packets")
                self.assertEqual(ast.unparse(transition.args[-1]), "tuple(packets)")


if __name__ == "__main__":
    unittest.main()
