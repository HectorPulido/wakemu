"""Behavioral tests for the nested local chat command dispatcher."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server.command_search import build_index


SOURCE = Path(__file__).parents[1] / "local_game_server.py"


def dispatcher_harness(*, character=None, fight=None, target_identity=None):
    """Compile the production nested dispatcher with controlled session globals."""
    tree = ast.parse(SOURCE.read_text())
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "execute_test_command"
    )
    factory = ast.FunctionDef(
        name="_make_dispatcher",
        args=ast.arguments(
            posonlyargs=[],
            args=[
                ast.arg(arg="character"),
                ast.arg(arg="position"),
                ast.arg(arg="movement_state"),
                ast.arg(arg="fight"),
                ast.arg(arg="fight_messages"),
                ast.arg(arg="bag_session"),
                ast.arg(arg="ranch_session"),
            ],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[ast.Constant(value=None) for _ in range(7)],
        ),
        body=[
            function,
            ast.Return(value=ast.Name(id="execute_test_command", ctx=ast.Load())),
        ],
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[]))
    sent = []
    mutations = []

    class Wire:
        @staticmethod
        def chat(recipient, message):
            return (recipient["id"], message)

    class World:
        @staticmethod
        def live_identity(*, name):
            return target_identity

    class Profiler:
        @staticmethod
        def profile(_name):
            return lambda function: function

    namespace = {
        "__name__": "_chat_command_routing_harness",
        "account_id": 700,
        "generation": "issuer-generation",
        "connection": object(),
        "service": 1,
        "fight": fight,
        "PROFILER": Profiler(),
        "bag_session": None,
        "STORE": object(),
        "COMBAT_GROUPS": None,
        "COMBAT_TEST": False,
        "WORLD": World(),
        "wire": Wire(),
        "send": lambda connection, service, opcode, body: sent.append((opcode, body)),
        "flush_positions": lambda **scope: mutations.append(("flush", scope)),
        "execute": lambda *args, **kwargs: mutations.append(("execute", args, kwargs)),
        "cancel_crafting": lambda: mutations.append(("cancel_crafting",)),
        "POSITIONS": type("Positions", (), {"attach": lambda *args: None})(),
        "Movement": lambda position: position,
        "owned_native_bootstrap": lambda character: (),
        "join_world": lambda *args: None,
        "mark_static_sync_pending": lambda: None,
        "record": lambda **kwargs: None,
        "MANUAL_CHECKPOINT": None,
        "TEST_CONSOLE": None,
        "sent": sent,
        "mutations": mutations,
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    current = character or {"id": 41, "name": "Self", "map_id": 3, "instance_id": 0}
    namespace["dispatcher"] = namespace["_make_dispatcher"](
        current, {}, None, fight, None, None, None
    )
    return namespace


class ChatCommandRoutingTests(unittest.TestCase):
    def test_chest_depositall_uses_only_own_open_chest_and_publishes_result(self):
        character = {
            "id": 41,
            "name": "Self",
            "account_id": 700,
            "map_id": 9,
            "instance_id": 77,
            "haven_bag": {"owner_id": 77},
        }
        namespace = dispatcher_harness(character=character)
        namespace.update(
            chest_opening="private-open-token",
            combat_session=None,
            ranch_session=None,
        )
        owners = (
            character,
            {"id": 42, "name": "Active hero", "inventory_items": []},
        )
        result_character = dict(character, inventory_items=[])
        chest = {"id": "owned-chest", "revision": 9, "items": []}
        result = {
            "character": result_character,
            "inventory_characters": owners,
            "chest": chest,
            "applied": True,
        }
        refreshed = []
        records = []

        class PrivateSession:
            @staticmethod
            def refresh(previous, current):
                refreshed.append((previous["id"], current["id"]))
                return current

        namespace["active_private_session"] = lambda: PrivateSession()
        namespace["record"] = lambda **event: records.append(event)
        with patch("wakfu_server.command_permissions.authorize_command"), patch(
            "wakfu_server.haven_chest.deposit_all", return_value=result
        ) as deposit_all, patch(
            "wakfu_server.inventory_move.synchronization",
            side_effect=lambda owner: ("inventory", owner["id"]),
        ), patch(
            "wakfu_server.inventory_items.equipment_inventory",
            side_effect=lambda owner: ("equipment", owner["id"]),
        ), patch(
            "wakfu_server.haven_chest_wire.bootstrap",
            side_effect=lambda value: ("chest", value["revision"]),
        ), patch(
            "wakfu_server.haven_chest_wire.action_result",
            return_value=("chest-result", True),
        ):
            output = namespace["dispatcher"]("!chest depositall")

        self.assertEqual(
            "Depósito completado; los objetos equipados y de misión permanecen en el inventario",
            output["message"],
        )
        deposit_all.assert_called_once_with(
            namespace["STORE"],
            700,
            "issuer-generation",
            41,
            opening_token="private-open-token",
            location=character,
            ranch_session=None,
        )
        self.assertEqual([(41, 41)], refreshed)
        self.assertEqual(
            [
                ("inventory", 41),
                ("equipment", 41),
                ("inventory", 42),
                ("equipment", 42),
                ("chest", 9),
                ("chest-result", True),
                (
                    674,
                    (
                        41,
                        "Depósito completado; los objetos equipados y de misión permanecen en el inventario",
                    ),
                ),
            ],
            namespace["sent"],
        )
        self.assertEqual(
            [
                {
                    "event": "account_chest_deposited_all",
                    "actor_id": 41,
                    "applied": True,
                    "revision": 9,
                }
            ],
            records,
        )
        self.assertEqual([], namespace["mutations"])

    def test_chest_depositall_rejects_remote_extra_args_missing_opening_and_fights(
        self,
    ):
        character = {
            "id": 41,
            "name": "Self",
            "account_id": 700,
            "map_id": 9,
            "instance_id": 77,
            "haven_bag": {"owner_id": 77},
        }
        cases = (
            ("!chest depositall @Remote", None, None, "private", 700),
            ("!chest depositall", None, None, None, 700),
            ("!chest depositall", object(), None, "private", 700),
            ("!chest depositall", None, object(), "private", 700),
            ("!chest depositall", None, None, "private", 701),
        )
        for command, fight, combat_session, opening, issuer in cases:
            with self.subTest(
                command=command,
                fight=bool(fight),
                combat=bool(combat_session),
                opening=opening,
                issuer=issuer,
            ):
                namespace = dispatcher_harness(character=character, fight=fight)
                namespace.update(
                    chest_opening=opening,
                    combat_session=combat_session,
                    ranch_session=None,
                )
                with patch("wakfu_server.command_permissions.authorize_command"), patch(
                    "wakfu_server.haven_chest.deposit_all"
                ) as deposit_all:
                    with self.assertRaises(ValueError):
                        namespace["dispatcher"](command, authorized_by=issuer)
                deposit_all.assert_not_called()
                self.assertEqual(1, len(namespace["sent"]))
                self.assertEqual(674, namespace["sent"][0][0])
                self.assertEqual([], namespace["mutations"])

    def test_search_alias_uses_bounded_read_only_results_without_position_flush(self):
        namespace = dispatcher_harness()
        index = build_index(
            [{"reference": i, "name": f"Potion sample {i}"} for i in range(1, 25)],
            [],
        )
        with patch("wakfu_server.command_permissions.authorize_command"), patch(
            "wakfu_server.command_search.native_index", return_value=index
        ):
            result = namespace["dispatcher"]("!search item potion")

        self.assertEqual(
            result["message"].splitlines()[0].split("|")[1].strip(), "24 coincidencias"
        )
        self.assertEqual(
            len(namespace["sent"]), 9
        )  # summary plus one bounded result page
        self.assertTrue(all(opcode == 674 for opcode, _ in namespace["sent"]))
        self.assertEqual(namespace["mutations"], [])

    def test_checkpoint_requests_async_flush_and_status_poll_without_sync_flush(self):
        namespace = dispatcher_harness()
        calls = []

        class Checkpoints:
            @staticmethod
            def request(**kwargs):
                calls.append(("request", kwargs))
                return {"handle": "cp-1", "status": "running"}

            @staticmethod
            def status(handle):
                calls.append(("status", handle))
                return {
                    "handle": handle,
                    "status": "completed",
                    "characters": 2,
                    "elapsed_ms": 5,
                }

        namespace["MANUAL_CHECKPOINT"] = Checkpoints()
        with patch("wakfu_server.command_permissions.authorize_command"):
            requested = namespace["dispatcher"]("!checkpoint")
            polled = namespace["dispatcher"]("!checkpoint cp-1")

        self.assertEqual(requested["checkpoint"]["status"], "running")
        self.assertEqual(calls[0][0], "request")
        self.assertEqual(calls[0][1]["requester"], (41, "issuer-generation"))
        self.assertEqual(calls[1], ("status", "cp-1"))
        self.assertEqual(polled["checkpoint"]["status"], "completed")
        self.assertEqual(namespace["mutations"], [])

    def test_targeted_alias_is_queued_for_target_with_issuer_and_generation_guards(
        self,
    ):
        target = {"id": 88, "name": "Target", "map_id": 4, "instance_id": 0}
        namespace = dispatcher_harness(target_identity=("target-generation", target))
        submitted = []

        class Console:
            @staticmethod
            def submit(character_id, command, **kwargs):
                submitted.append((character_id, command, kwargs))
                return {"handle": "receipt-1"}

        namespace["TEST_CONSOLE"] = Console()
        with patch(
            "wakfu_server.command_permissions.authorize_command"
        ) as authorize, patch(
            "wakfu_server.command_permissions.is_admin", return_value=True
        ):
            result = namespace["dispatcher"]('!monster 5525 1 2 "Target"')

        self.assertEqual(result["handle"], "receipt-1")
        character_id, command, kwargs = submitted[0]
        self.assertEqual((character_id, command), (88, "!mob 5525 1 2"))
        self.assertEqual(kwargs["requester_account_id"], 700)
        self.assertEqual(kwargs["delegated_by"], 700)
        self.assertEqual(kwargs["expected_generation"], "target-generation")
        self.assertIsNone(kwargs.get("executor"))
        self.assertEqual(namespace["mutations"], [])
        kwargs["authorize"]()
        self.assertEqual(authorize.call_count, 2)
        self.assertEqual(authorize.call_args.args[1:], (700, "!mob 5525 1 2"))

    def test_self_target_alias_is_rejected_in_fight_before_flush_or_execution(self):
        character = {"id": 41, "name": "Self", "map_id": 3, "instance_id": 0}
        namespace = dispatcher_harness(
            character=character,
            fight=object(),
            target_identity=("issuer-generation", character),
        )
        with patch("wakfu_server.command_permissions.authorize_command"), patch(
            "wakfu_server.command_permissions.is_admin", return_value=True
        ):
            with self.assertRaisesRegex(ValueError, "Termina el combate"):
                namespace["dispatcher"]("!monster 5525 1 1 @Self")

        self.assertEqual(namespace["mutations"], [])


if __name__ == "__main__":
    unittest.main()
