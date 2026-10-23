"""Run actual World flora closures without importing its network/bootstrap loop."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import resource_collect
from wakfu_server.planting_location import owned_character
from wakfu_server.world import World


class WorldFloraOccupationDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).parents[1] / "local_game_server.py"
        cls.tree = ast.parse(cls.path.read_text())

    def driver(self, namespace, state):
        definitions = {
            name: next(
                n
                for n in ast.walk(self.tree)
                if isinstance(n, ast.FunctionDef) and n.name == name
            )
            for name in ("cancel_flora", "complete_flora_occupation")
        }
        polling = [
            n
            for n in ast.walk(self.tree)
            if isinstance(n, ast.If)
            and "flora_retry_body is not None" in ast.unparse(n.test)
            and any(
                isinstance(c, ast.Call)
                and isinstance(c.func, ast.Name)
                and c.func.id == "complete_flora_occupation"
                for c in ast.walk(n)
            )
        ]
        self.assertEqual(len(polling), 1)
        wrapper = ast.parse(
            """
def make(state):
    character = state['character']
    flora_ticket = state['ticket']
    flora_retry_body = None
"""
        ).body[0]
        wrapper.body.extend(
            deepcopy(definitions[name])
            for name in ("cancel_flora", "complete_flora_occupation")
        )
        poll = ast.FunctionDef(
            name="poll",
            args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=[deepcopy(polling[0])],
            decorator_list=[],
        )
        wrapper.body.append(poll)
        wrapper.body.extend(
            ast.parse(
                """
def snapshot():
    return dict(character=character, ticket=flora_ticket, retry=flora_retry_body)
return complete_flora_occupation, cancel_flora, poll, snapshot
"""
            ).body
        )
        module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
        exec(compile(module, str(self.path), "exec"), namespace)
        return namespace["make"](state)

    def test_actual_world_completion_retries_early_once_uses_buffered_origin_and_cancels_pending(
        self,
    ):
        start = datetime(2026, 10, 22, tzinfo=timezone.utc)
        clock = [start]
        stored = dict(
            id=7, account_id=8, map_id=1134, instance_id=0, x=0, y=0, z=0, direction=0
        )
        live = dict(stored, x=9)
        buffered = dict(stored, x=11, direction=2)
        world = World(lambda _: b"", lambda _: b"", lambda *_: True)
        world.join("owned-generation", object(), live)
        world.emit_location = Mock()
        positions = SimpleNamespace(merge=Mock(return_value=buffered))
        saved = dict(stored, inventory_items=[dict(uid=100)])
        store = SimpleNamespace(
            now=lambda: clock[0], character=Mock(return_value=saved)
        )
        sent = []
        namespace = dict(
            STORE=store,
            WORLD=world,
            POSITIONS=positions,
            PLANTINGS=SimpleNamespace(publisher_lock=RLock()),
            owned_planting_character=owned_character,
            fight=None,
            account_id=8,
            generation="owned-generation",
            connection=object(),
            service=object(),
            active_private_session=lambda: None,
            cancel_environment=Mock(),
            record=Mock(),
            send=lambda *args: sent.append(args[-2:]),
            send_native_planting_bonus=Mock(),
            wire=SimpleNamespace(chat=lambda *_: b"rejected"),
        )
        ticket = dict(
            token="owned-ticket",
            character_id=7,
            completes_at=start + timedelta(seconds=5),
        )
        attempts = []

        def complete(backend, current_ticket, body, *, location_context):
            actual = location_context(stored)
            self.assertEqual((actual["x"], actual["direction"]), (11, 2))
            self.assertEqual(current_ticket, ticket)
            attempts.append(body)
            if backend.now() < current_ticket["completes_at"]:
                raise resource_collect.HarvestNotReady(current_ticket["completes_at"])
            return dict(
                applied=True,
                world_packets=[(12782, b"world")],
                packets=[(13613, b"earned")],
                map_id=1134,
                instance_id=0,
                outcome=dict(ecology={}),
            )

        with patch.object(
            resource_collect, "complete", side_effect=complete
        ), patch.object(
            resource_collect, "acknowledge_publication"
        ) as acknowledge, patch.object(
            resource_collect, "cancel"
        ) as cancel:
            run, stop, poll, snapshot = self.driver(
                namespace, dict(character=stored, ticket=ticket)
            )
            body = b"\x02\x00\x03"
            run(body)
            self.assertEqual(snapshot()["ticket"], ticket)
            self.assertEqual(snapshot()["retry"], body)
            self.assertEqual(sent, [])
            acknowledge.assert_not_called()
            cancel.assert_not_called()
            poll()
            self.assertEqual(attempts, [body])
            clock[0] = ticket["completes_at"]
            poll()
            self.assertEqual(attempts, [body, body])
            self.assertIsNone(snapshot()["ticket"])
            self.assertIsNone(snapshot()["retry"])
            self.assertEqual(snapshot()["character"], saved)
            self.assertEqual(sent, [(13613, b"earned")])
            world.emit_location.assert_called_once_with(1134, 0, 12782, b"world")
            acknowledge.assert_called_once()
            store.character.assert_called_once_with(8, 7)
            poll()
            self.assertEqual(attempts, [body, body])
            # Movement cancellation clears both retained fields, so a later
            # idle poll cannot commit an operation the server already cancelled.
            clock[0] = start
            run, stop, poll, snapshot = self.driver(
                namespace, dict(character=stored, ticket=ticket)
            )
            run(body)
            stop()
            self.assertIsNone(snapshot()["ticket"])
            self.assertIsNone(snapshot()["retry"])
            cancel.assert_called_once_with(store, ticket)
            clock[0] = ticket["completes_at"]
            before = len(attempts)
            poll()
            self.assertEqual(len(attempts), before)
            run, stop, poll, snapshot = self.driver(
                namespace, dict(character=stored, ticket=ticket)
            )
            with patch.object(
                resource_collect,
                "complete",
                side_effect=ValueError("invalid owned operation"),
            ):
                run(body)
            self.assertIsNone(snapshot()["ticket"])
            self.assertIsNone(snapshot()["retry"])
            self.assertEqual(cancel.call_count, 2)
            self.assertEqual(sent[-1], (674, b"rejected"))
            poll()
            self.assertEqual(len(attempts), before)
        # All three real source call sites must carry the same owned context,
        # not reload stale SQL coordinates between prepare/reserve/complete.
        opening = [
            n
            for n in ast.walk(self.tree)
            if isinstance(n, ast.If) and "opcode == 12995" in ast.unparse(n.test)
        ]
        self.assertEqual(len(opening), 1)
        calls = [
            n
            for n in ast.walk(opening[0])
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in ("prepare", "reserve")
            and any(k.arg == "location_context" for k in n.keywords)
        ]
        self.assertEqual({n.func.id for n in calls}, {"prepare", "reserve"})
        complete_fn = next(
            n
            for n in ast.walk(self.tree)
            if isinstance(n, ast.FunctionDef) and n.name == "complete_flora_occupation"
        )
        calls.extend(
            n
            for n in ast.walk(complete_fn)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "complete"
        )
        self.assertEqual(len(calls), 3)
        for call in calls:
            expression = next(
                k.value for k in call.keywords if k.arg == "location_context"
            )
            callback = eval(
                compile(
                    ast.Expression(body=deepcopy(expression)), str(self.path), "eval"
                ),
                namespace,
            )
            self.assertEqual(callback(stored)["x"], 11)
        positions.merge.assert_called_with(8, "owned-generation", stored)

    def test_validated_hero_handoff_closes_dialogue_before_switch_and_cannot_survive_aba(
        self,
    ):
        from test_npc_world import NpcWorldTests
        from wakfu_server.maps import npc_world

        fixture = NpcWorldTests()
        fixture.setUp()
        current = dict(fixture.character)
        dialogue, _ = npc_world.begin(
            lambda: current,
            lambda: [fixture.row],
            fixture.row["actor_id"],
            515,
            fixture.native,
        )
        handoff = next(
            n
            for n in ast.walk(self.tree)
            if isinstance(n, ast.If)
            and ast.unparse(n.test) == "opcode == 12006 and loaded"
        )
        transaction = next(n for n in handoff.body if isinstance(n, ast.Try))
        closing = [
            n
            for n in transaction.body
            if isinstance(n, ast.If)
            and ast.unparse(n.test) == "npc_dialogue_session is not None"
        ]
        self.assertEqual(len(closing), 1)
        switch = next(
            n
            for n in ast.walk(transaction)
            if isinstance(n, ast.Call) and ast.unparse(n.func) == "heroes.switch_main"
        )
        self.assertLess(closing[0].lineno, switch.lineno)
        namespace = dict(npc_dialogue_session=dialogue)
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=[deepcopy(closing[0])], type_ignores=[])
                ),
                str(self.path),
                "exec",
            ),
            namespace,
        )
        self.assertIsNone(namespace["npc_dialogue_session"])
        current["id"] += 1
        current["id"] -= 1
        # Returning to the same owner cannot resurrect a previously offered
        # choice: this executes the actual source close, not only tuple checks.
        self.assertIsNone(dialogue.node_id)
        with self.assertRaises(ValueError):
            dialogue.choose(6274, 14075)
