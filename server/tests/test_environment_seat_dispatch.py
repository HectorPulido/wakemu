"""Run production seat, cancellation, and logout branches with isolated fakes."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import environment_seats


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def _session_tree():
    tree = ast.parse(SERVER.read_text(encoding="utf-8"), filename=str(SERVER))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )


def _if(predicate):
    return next(
        node
        for node in ast.walk(_session_tree())
        if isinstance(node, ast.If) and predicate(ast.unparse(node.test))
    )


def _exec_branch(branch, namespace, values):
    branch = deepcopy(branch)
    branch.orelse = []
    # The actual dispatcher continues its outer packet loop. This harness
    # substitutes a break to leave its one-branch loop after that path runs.
    for node in ast.walk(branch):
        if isinstance(node, ast.Continue):
            node.__class__ = ast.Break
    names = list(values)
    function = ast.FunctionDef(
        name="dispatch_branch",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg=name) for name in names],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=[
            ast.While(test=ast.Constant(True), body=[branch, ast.Break()], orelse=[]),
            ast.Return(
                ast.Dict(
                    keys=[ast.Constant(name) for name in names],
                    values=[ast.Name(name, ast.Load()) for name in names],
                )
            ),
        ],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    exec(compile(module, str(SERVER), "exec"), namespace)
    return namespace["dispatch_branch"](**values)


def _helpers(namespace, initial_seat=None):
    session = _session_tree()
    functions = {
        node.name: node
        for node in session.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"cancel_environment", "publish_environment_scene"}
    }
    parent = ast.FunctionDef(
        name="make_helpers",
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=None,
            defaults=[],
        ),
        body=[
            ast.Assign(
                [ast.Name("environment_ticket", ast.Store())], ast.Constant(None)
            ),
            ast.Assign(
                [ast.Name("environment_seat", ast.Store())],
                ast.Name("_initial_seat", ast.Load()),
            ),
            ast.Assign(
                [ast.Name("environment_scene_identity", ast.Store())],
                ast.Constant(None),
            ),
            ast.Assign(
                [ast.Name("environment_scene_states", ast.Store())], ast.Dict([], [])
            ),
            ast.Assign(
                [ast.Name("last_environment_refresh", ast.Store())], ast.Constant(0.0)
            ),
            deepcopy(functions["cancel_environment"]),
            deepcopy(functions["publish_environment_scene"]),
            ast.FunctionDef(
                name="state",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[],
                ),
                body=[
                    ast.Return(
                        ast.Tuple(
                            [ast.Name("environment_seat", ast.Load())], ast.Load()
                        )
                    )
                ],
                decorator_list=[],
            ),
            ast.Return(
                ast.Dict(
                    keys=[
                        ast.Constant("cancel"),
                        ast.Constant("publish"),
                        ast.Constant("state"),
                    ],
                    values=[
                        ast.Name("cancel_environment", ast.Load()),
                        ast.Name("publish_environment_scene", ast.Load()),
                        ast.Name("state", ast.Load()),
                    ],
                )
            ),
        ],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[parent], type_ignores=[]))
    namespace["_initial_seat"] = initial_seat
    exec(compile(module, str(SERVER), "exec"), namespace)
    return namespace["make_helpers"]()


class EnvironmentSeatDispatchTests(unittest.TestCase):
    def setUp(self):
        self.actor = {
            "id": 41,
            "map_id": 1134,
            "instance_id": 0,
            "x": 4,
            "y": 5,
            "z": 0,
            "appearance": {"sex": 0, "clothIndex": 0},
        }
        self.stool = {"id": 9001, "type": "Stool", "x": 4, "y": 5, "z": 0}
        self.events = []
        self.namespace = {
            "STORE": object(),
            "account_id": 7,
            "generation": "g1",
            "character": self.actor,
            "connection": object(),
            "service": "world",
            "loaded": True,
            "fight": None,
            "combat_session": None,
            "spectator_session": None,
            "bag_session": None,
            "flora_ticket": None,
            "environment_ticket": None,
            "world_static": SimpleNamespace(objects=lambda map_id: [self.stool]),
            "struct": struct,
            "time": SimpleNamespace(monotonic=lambda: 10.0),
            "send": lambda connection, service, opcode, body: self.events.append(
                ("send", opcode, body)
            ),
            "environment_blocked": lambda **kwargs: False,
        }
        self.helpers = _helpers(self.namespace)
        self.namespace["publish_environment_scene"] = self.helpers["publish"]
        self.namespace["cancel_environment"] = self.helpers["cancel"]

    def _scene_packets(self, actor_id):
        return (environment_seats.occupancy(self.stool["id"], actor_id),)

    def _run_stool(self, action, seat_before=None):
        body = struct.pack(">qHH", self.stool["id"], action, 0)
        result = {
            "character_id": self.actor["id"],
            "object_id": self.stool["id"],
            "packets": [
                (
                    13579,
                    struct.pack(
                        ">Bhqq",
                        1 if action == 6 else 3,
                        16,
                        self.stool["id"],
                        self.actor["id"],
                    ),
                )
            ],
        }
        occupied = {"object_id": self.stool["id"], "character_id": self.actor["id"]}
        self.namespace["STORE"] = object()
        branch = _if(lambda text: text == "stool is not None")
        values = {
            "stool": self.stool,
            "stool_id": self.stool["id"],
            "stool_action": action,
            "body": body,
            "character": self.actor,
            "environment_seat": seat_before,
            "environment_ticket": None,
            "environment_blocked": self.namespace["environment_blocked"],
            "STORE": self.namespace["STORE"],
            "account_id": 7,
            "generation": "g1",
            "connection": self.namespace["connection"],
            "service": "world",
        }
        real_publish = self.helpers["publish"]
        self.namespace["publish_environment_scene"] = real_publish
        with patch.object(environment_seats, "sit", return_value=result) as sit, patch(
            "wakfu_server.environment_seat_animations.supported", return_value=True
        ), patch(
            "wakfu_server.environment_interactions.snapshots", return_value=()
        ), patch.object(
            environment_seats,
            "snapshots",
            return_value=self._scene_packets(self.actor["id"] if action == 6 else 0),
        ):
            state = _exec_branch(branch, self.namespace, values)
        sit.assert_called_once()
        return state

    def test_owner_packets_and_peer_scene_updates_follow_claim_and_release(self):
        claimed = self._run_stool(6)
        self.assertEqual(claimed["environment_seat"]["character_id"], self.actor["id"])
        self.assertEqual(self.events[0][1], 13579)
        self.assertEqual(
            self.events[1],
            (
                "send",
                12344,
                environment_seats.occupancy(self.stool["id"], self.actor["id"])[1],
            ),
        )

        self.events.clear()
        released = self._run_stool(
            7,
            seat_before={
                "object_id": self.stool["id"],
                "character_id": self.actor["id"],
            },
        )
        self.assertIsNone(released["environment_seat"])
        self.assertEqual(self.events[0][1], 13579)
        self.assertEqual(
            self.events[1],
            ("send", 12344, environment_seats.occupancy(self.stool["id"], 0)[1]),
        )

    def test_actual_cancel_helper_retains_lease_on_sql_error_then_publishes_release(
        self,
    ):
        marker = {"object_id": self.stool["id"], "character_id": self.actor["id"]}
        helpers = _helpers(self.namespace, marker)
        self.namespace["publish_environment_scene"] = helpers["publish"]
        self.namespace["cancel_environment"] = helpers["cancel"]
        release_events = []

        def release(*args):
            release_events.append("release")
            if len(release_events) == 1:
                raise OSError("temporary database disconnect")
            return {"packets": [(12088, b"leave")], "scene_packets": []}

        with patch(
            "wakfu_server.environment_seats.release", side_effect=release
        ), patch(
            "wakfu_server.environment_interactions.snapshots", return_value=()
        ), patch.object(
            environment_seats, "snapshots", return_value=self._scene_packets(0)
        ):
            with self.assertRaisesRegex(OSError, "temporary database"):
                helpers["cancel"](publish=False)
            self.assertIs(helpers["state"]()[0], marker)
            helpers["cancel"](publish=True)

        self.assertEqual(release_events, ["release", "release"])
        self.assertIsNone(helpers["state"]()[0])
        self.assertEqual(self.events[-2], ("send", 12088, b"leave"))
        self.assertEqual(self.events[-1][1], 12344)

    def test_movement_hero_and_combat_paths_cancel_seats_and_logout_uses_retry_barrier(
        self,
    ):
        cancel_calls = []
        marker = {"object_id": self.stool["id"], "character_id": self.actor["id"]}
        branch = _if(
            lambda text: text.startswith(
                "(environment_ticket is not None or environment_seat is not None) and opcode in"
            )
        )
        for opcode in (13331, 13686, 12219, 12006):
            values = {
                "environment_ticket": None,
                "environment_seat": marker,
                "opcode": opcode,
                "cancel_environment": lambda: cancel_calls.append(opcode),
            }
            _exec_branch(branch, self.namespace, values)
        self.assertEqual(cancel_calls, [13331, 13686, 12219, 12006])

        combat = _if(lambda text: text.startswith("environment_seat is not None and ("))
        values = {
            "environment_seat": marker,
            "fight": object(),
            "combat_session": None,
            "spectator_session": None,
            "cancel_environment": lambda: cancel_calls.append("combat"),
        }
        _exec_branch(combat, self.namespace, values)
        self.assertEqual(cancel_calls[-1], "combat")

        # The logout branch invokes the production cancellation callback inside
        # the existing retry_step barrier. A transient SQL error leaves the
        # marker intact, then the retry succeeds and clears it.
        logout = _if(
            lambda text: text
            == "service == 'world' and (environment_ticket is not None or environment_seat is not None)"
        )
        helpers = _helpers(self.namespace, marker)
        self.namespace["publish_environment_scene"] = helpers["publish"]
        self.namespace["cancel_environment"] = helpers["cancel"]
        attempts = []

        def release(*args):
            attempts.append(1)
            if len(attempts) == 1:
                raise OSError("temporary SQL disconnect")
            return {"packets": [], "scene_packets": []}

        def logout_barrier(stage, operation):
            self.assertEqual(stage, "environment_occupation")
            from wakfu_server.session_cleanup import retry_step

            return retry_step(
                operation,
                retry_errors=(OSError,),
                failed=lambda error: None,
                renew=lambda: None,
                wait=lambda seconds: None,
            )

        with patch(
            "wakfu_server.environment_seats.release", side_effect=release
        ), patch(
            "wakfu_server.environment_interactions.snapshots", return_value=()
        ), patch.object(
            environment_seats, "snapshots", return_value=self._scene_packets(0)
        ):
            _exec_branch(
                logout,
                self.namespace,
                {
                    "service": "world",
                    "environment_ticket": None,
                    "environment_seat": marker,
                    "logout_barrier": logout_barrier,
                    "cancel_environment": helpers["cancel"],
                },
            )
        self.assertEqual(len(attempts), 2)
        self.assertIsNone(helpers["state"]()[0])


if __name__ == "__main__":
    unittest.main()
