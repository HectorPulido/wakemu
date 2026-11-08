"""Execute the connected player's actual callback through the real Registry."""
import ast
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from test_combat_native_action_ids import NativeActionIdTests
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server import combat_native_action_ids as delivery


def callback(session):
    source = Path(__file__).with_name("candidate") / "local_game_server.py"
    if not source.exists():
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
    tree = ast.parse(source.read_text())
    nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "shared_end_turn"
    ]
    if len(nodes) != 1:
        raise AssertionError("Shared end-turn callback is not unique")
    namespace = dict(
        combat_session=session,
        actor_id=100,
        actor_turn=1,
        body=struct.pack(">qh", 100, 1),
        Transition=Transition,
        shared_action_incident=lambda *args, **kwargs: nullcontext(),
    )
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace
    )
    return namespace["shared_end_turn"]


def fixture():
    runtime = NativeActionIdTests().runtime()
    session = Session(1, 100, "player-endturn", 1134, 0)
    registry = Registry(lambda current: current == session)
    shared = registry.register(runtime.fight, session, runtime=runtime)
    return registry, shared, session


def state(shared):
    return (
        source_snapshot(shared.fight),
        shared.sequence,
        deepcopy(vars(shared.ack)),
        shared.runtime.native_action_id,
        shared.runtime.awaiting_ack,
        tuple(shared.runtime.pending),
        {
            key: tuple((batch.sequence, batch.packets) for batch in rows)
            for key, rows in shared.outboxes.items()
        },
    )


class PlayerEndTurnCoalescingTests(unittest.TestCase):
    @patch("wakfu_server.combat_runtime_messages.wall_time", new=lambda _: 1700000000.0)
    def test_real_shared_callback_equivalence_rollback_and_custom_fallback(self):
        original = RuntimeMessages.__deepcopy__
        results = []
        counts = []
        for enabled in (False, True):
            registry, shared, session = fixture()
            operation = callback(session)
            copies = []

            def clone(value, memo):
                copies.append(True)
                return original(value, memo)

            scope = (
                nullcontext()
                if enabled
                else patch.object(
                    delivery, "owned_native_delivery", new=lambda *_: nullcontext()
                )
            )
            with scope, patch.object(RuntimeMessages, "__deepcopy__", new=clone):
                sequence = registry.execute(91, session, 100, operation)
            counts.append(len(copies))
            before_ack = state(shared)
            released = registry.acknowledge(
                91,
                session,
                struct.pack(">i", 1),
                lambda fight, runtime, body: runtime.acknowledge_turn(body),
            )
            results.append((sequence, before_ack, released, state(shared)))
            self.assertNotIn("_native_delivery_depth", vars(shared.runtime))
            self.assertNotIn("_area_atomic_depth", vars(shared.runtime))
            self.assertIsNone(delivery._OWNED_DELIVERY.get())
        self.assertEqual(results[0], results[1])
        self.assertEqual(counts[0], counts[1] + 1)

        registry, shared, session = fixture()
        shared.runtime.native_action_id = delivery.MAX_NATIVE_ACTION_ID
        before = state(shared)
        original_fight, original_runtime = shared.fight, shared.runtime
        with self.assertRaisesRegex(ValueError, "exhausted"):
            registry.execute(91, session, 100, callback(session))
        self.assertEqual(state(shared), before)
        self.assertIs(shared.fight, original_fight)
        self.assertIs(shared.runtime, original_runtime)
        self.assertIsNone(delivery._OWNED_DELIVERY.get())

        registry, shared, session = fixture()
        shared.runtime.clock = lambda: 0.0
        copies = []
        with patch.object(RuntimeMessages, "__deepcopy__", new=clone):
            registry.execute(91, session, 100, callback(session))
        self.assertEqual(len(copies), counts[0])

        registry, shared, session = fixture()

        def reject(fight, **kwargs):
            fight.actors[100].hp -= 1
            raise ValueError("provider rejection after mutation")

        shared.runtime.turn_end_provider = reject
        before = state(shared)
        with self.assertRaisesRegex(ValueError, "provider rejection after mutation"):
            registry.execute(91, session, 100, callback(session))
        self.assertEqual(state(shared), before)
        self.assertIsNone(delivery._OWNED_DELIVERY.get())
