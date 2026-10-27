"""Native commits must not be spent on repeated movement destinations."""
import time
import unittest
from unittest.mock import patch

from test_jondo_bridge import Oracle, Runtime, Transport, reply, request_fixture
from wakfu_ai.bridge import jondo_entry


class MovingOracle(Oracle):
    def commit(self, action, **kwargs):
        packets = super().commit(action, **kwargs)
        if action["type"] == "move":
            self.runtime.fight.current.position = tuple(action["path"][-1])
        elif action["type"] == "portal_travel":
            self.runtime.fight.current.position = tuple(action["destination"])
        return packets


class JondoMovementProgressTests(unittest.TestCase):
    def drive(self, actions):
        runtime = Runtime()
        runtime.fight.current.position = (0, 0, 0)
        oracle = MovingOracle(runtime)
        transport = Transport(
            lambda request, count: reply(
                request,
                actions[min(count - 1, len(actions) - 1)],
                [dict(type="end_turn")],
            )
        )
        with patch.object(jondo_entry, "build_snapshot", request_fixture):
            deliveries = list(
                jondo_entry.run_prepared_turn(
                    runtime,
                    oracle,
                    object(),
                    transport,
                    deadline=time.monotonic() + 5,
                    max_actions=8,
                )
            )
        return oracle, deliveries

    def test_return_without_cast_is_rejected_before_spending_native_resources(self):
        for back in (
            dict(type="move", path=[[0, 0, 0]]),
            dict(type="portal_travel", destination=[0, 0, 0]),
        ):
            with self.subTest(back=back):
                oracle, deliveries = self.drive(
                    [dict(type="move", path=[[1, 0, 0]]), back, dict(type="end_turn")]
                )
                self.assertEqual(
                    [row["type"] for row in oracle.calls], ["move", "end_turn"]
                )
                self.assertEqual(oracle.runtime.fight.current.position, (1, 0, 0))
                self.assertIn(
                    "revisits", deliveries[-1][1]["rejectedActions"][0]["detail"]
                )

    def test_cast_allows_attack_then_return_through_previous_portal_destination(self):
        oracle, _ = self.drive(
            [
                dict(type="move", path=[[1, 0, 0]]),
                dict(type="cast", spellId=7, level=1, target=[2, 0, 0]),
                dict(type="portal_travel", destination=[0, 0, 0]),
                dict(type="end_turn"),
            ]
        )
        self.assertEqual(
            [row["type"] for row in oracle.calls],
            ["move", "cast", "portal_travel", "end_turn"],
        )
        self.assertEqual(oracle.runtime.fight.current.position, (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
