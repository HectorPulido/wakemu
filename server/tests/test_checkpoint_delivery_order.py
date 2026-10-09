"""Committed combat delivery and information precede asynchronous capture."""
import ast
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
import time
import unittest


class CheckpointDeliveryOrderTests(unittest.TestCase):
    def invoke(self, *, terminal=False):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        checkpoint = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "checkpoint_fight"
        )
        events = []
        gated_pending = [(123, b"next-turn-awaits-ACK")]
        runtime = SimpleNamespace(pending=gated_pending)
        recipients = {
            1: SimpleNamespace(account_id=1, character_id=6, generation="own"),
            2: SimpleNamespace(account_id=2, character_id=7, generation="other"),
        }
        shared = SimpleNamespace(
            checkpoint_terminal=False,
            lock=RLock(),
            participants=recipients,
            connected={1, 2},
            runtime=runtime,
        )

        def submit(*args, **kwargs):
            self.assertEqual(runtime.pending, [(123, b"next-turn-awaits-ACK")])
            events.append("capture-submit")
            return dict(sequence=1, terminal=False)

        namespace = dict(
            fight=SimpleNamespace(id=53),
            account_id=1,
            generation="own",
            combat_session=object(),
            connection=object(),
            service="world",
            time=time,
            COMBAT_SESSIONS=SimpleNamespace(
                registry=SimpleNamespace(lookup=lambda _: shared)
            ),
            CHECKPOINT_WRITER=SimpleNamespace(
                terminal_pending=lambda _: terminal, submit=submit
            ),
            drain_shared_combat=lambda: events.append("combat-and-spectator-delivery"),
            send=lambda *args: events.append("own-notice"),
            WORLD=SimpleNamespace(send_to=lambda *args: events.append("other-notice")),
            record=lambda **kwargs: None,
        )
        wrapper = ast.parse(
            "def make():\n    checkpoint_revision = checkpoint_id = checkpoint_local_shared = None\n    checkpoint_terminal = False\n"
        ).body[0]
        wrapper.body.extend(
            [
                checkpoint,
                ast.Return(value=ast.Name(id="checkpoint_fight", ctx=ast.Load())),
            ]
        )
        module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
        exec(compile(module, "<checkpoint-delivery>", "exec"), namespace)
        namespace["make"]()()
        return events

    def test_all_connected_notices_follow_combat_delivery_before_submit(self):
        self.assertEqual(
            self.invoke(),
            [
                "combat-and-spectator-delivery",
                "own-notice",
                "other-notice",
                "capture-submit",
            ],
        )

    def test_terminal_replay_does_not_emit_notice_or_deliver(self):
        self.assertEqual(self.invoke(terminal=True), [])
