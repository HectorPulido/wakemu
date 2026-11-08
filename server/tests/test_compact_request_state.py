"""Real request summary and World producer callbacks without starting World."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from wakfu_server.request_diagnostics import RequestTrace, state_summary


class CompactRequestStateTests(unittest.TestCase):
    def test_default_optin_and_failure_capture_preserve_state_without_enumeration(self):
        class NoInventoryWalk(list):
            def __iter__(self):
                raise AssertionError("Routine inventory walk")

            def __getitem__(self, key):
                raise AssertionError("Routine inventory slice")

        class NoActorWalk(dict):
            def values(self):
                raise AssertionError("Routine actor walk")

        actor = SimpleNamespace(
            id=1,
            team=0,
            controlled=True,
            position=[1, 2, 0],
            hp=10,
            ap=6,
            mp=3,
            effect_stats={4: 6},
            state_ledger=SimpleNamespace(
                entries=[SimpleNamespace(uid=3, reference=42, level=2)]
            ),
        )
        fight = SimpleNamespace(
            id=440,
            phase="active",
            turn_id=225,
            current=actor,
            actors=NoActorWalk({1: actor}),
        )
        runtime = SimpleNamespace(awaiting_ack=225, action_id=1989, pending=[b"x"])
        character = dict(
            id=1,
            inventory_items=NoInventoryWalk(
                [dict(uid=7, reference=8, quantity=1, container=0, slot=2)]
            ),
            builds={},
        )
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        call = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "RequestTrace"
        )
        callbacks = {
            k.arg: k.value
            for k in call.keywords
            if k.arg in ("snapshot", "failure_snapshot")
        }
        namespace = dict(
            character=character,
            fight=fight,
            fight_messages=runtime,
            opcode=13510,
            REQUEST_STATE_DETAIL=False,
            state_summary=state_summary,
        )

        def callback(name):
            return eval(
                compile(ast.Expression(callbacks[name]), "<World producer>", "eval"),
                namespace,
            )

        rows = []
        trace = RequestTrace(
            sink=lambda **row: rows.append(row),
            opcode=13510,
            service="world",
            connection_id="fixture",
            snapshot=callback("snapshot"),
            failure_snapshot=callback("failure_snapshot"),
        )
        trace.finish()
        before = rows[0]["state_before"]
        self.assertEqual(
            before["fight"],
            dict(
                id=440,
                phase="active",
                turn_id=225,
                current_actor=1,
                winner=None,
                actor_total=1,
                awaiting_ack=225,
                action_id=1989,
                pending_packets=1,
            ),
        )
        self.assertEqual(before["inventory_units"], 1)
        self.assertNotIn("inventory", before)
        self.assertNotIn("actors", before["fight"])
        self.assertEqual(rows[-1]["state_before"], rows[-1]["state_after"])
        self.assertEqual(rows[-1]["status"], "completed")
        self.assertIn("elapsed_ms", rows[-1])

        character["inventory_items"] = list.__getitem__(
            character["inventory_items"], slice(None)
        )
        fight.actors = dict(fight.actors)
        original = deepcopy((character, vars(actor), vars(runtime)))
        namespace["REQUEST_STATE_DETAIL"] = True
        rows.clear()
        trace = RequestTrace(
            sink=lambda **row: rows.append(row),
            opcode=13510,
            service="world",
            connection_id="fixture",
            snapshot=callback("snapshot"),
            failure_snapshot=callback("failure_snapshot"),
        )
        trace.finish()
        self.assertEqual(
            rows[0]["state_before"], state_summary(character, fight, runtime)
        )
        self.assertEqual(rows[-1]["state_after"], rows[0]["state_before"])
        rows[0]["state_before"]["fight"]["actors"][0]["states"][0]["level"] = 999
        self.assertEqual(actor.state_ledger.entries[0].level, 2)
        self.assertEqual((character, vars(actor), vars(runtime)), original)

        namespace["REQUEST_STATE_DETAIL"] = False
        for status, rejected in (
            ("failed", False),
            ("exception", False),
            ("unexpected_error", False),
            ("invalid_request", False),
            ("disconnected", False),
            (None, True),
        ):
            with self.subTest(status=status, rejected=rejected):
                rows.clear()
                trace = RequestTrace(
                    sink=lambda **row: rows.append(row),
                    opcode=13510,
                    service="world",
                    connection_id="fixture",
                    snapshot=callback("snapshot"),
                    failure_snapshot=callback("failure_snapshot"),
                )
                if rejected:
                    trace.rejection("action_rejected", "bad input")
                trace.finish(status=status)
                self.assertNotIn("actors", rows[-1]["state_before"]["fight"])
                self.assertEqual(
                    rows[-1]["state_after"], state_summary(character, fight, runtime)
                )
                self.assertEqual(rows[-1]["status"], "rejected" if rejected else status)
        self.assertEqual((character, vars(actor), vars(runtime)), original)


if __name__ == "__main__":
    unittest.main()
