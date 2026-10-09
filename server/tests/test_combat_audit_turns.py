import importlib.util
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest

spec = importlib.util.spec_from_file_location(
    "combat_audit_turns",
    Path(__file__).resolve().parents[1] / "tools/combat_audit_turns.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AuditTurnRoutingTests(unittest.TestCase):
    def test_real_boundary_arguments_and_ack_for_player_and_npc(self):
        for controlled in (True, False):
            calls = []
            actor = SimpleNamespace(
                id=7 if controlled else -7,
                owner_id=3,
                controlled=controlled,
                turn_count=4,
            )
            runtime = SimpleNamespace(
                fight=SimpleNamespace(current=actor, turn_id=9), awaiting_ack=9
            )

            def end(*args):
                calls.append(("end", args))
                return ["end"]

            def ack(body):
                calls.append(("ack", body))
                runtime.awaiting_ack = None
                return ["ack"]

            runtime.end_turn = (
                end if controlled else lambda *args: self.fail("NPC client end")
            )
            runtime.end_server_turn = (
                end if not controlled else lambda *args: self.fail("PC server end")
            )
            runtime.acknowledge_turn = ack
            self.assertEqual(module.advance_actual_turn(runtime), ["end", "ack"])
            self.assertEqual(
                calls,
                [
                    ("end", (3, 7, 4) if controlled else (-7, 9)),
                    ("ack", struct.pack(">i", 9)),
                ],
            )
            self.assertIsNone(runtime.awaiting_ack)
