import unittest
from wakfu_server.achievements import recurring_missions as m


class RecurringMissionTest(unittest.TestCase):
    def setUp(self):
        self.definition = {
            "d": 1215,
            "aqb": False,
            "cjT": 1000,
            "cjU": 86400,
            "cjJ": [{"d": 2176}],
            "cjK": [{"d": 2006, "aeV": 6, "ckl": [445000]}],
        }
        self.state = {
            "running": [999],
            "completed": [123],
            "objectives": [1234],
            "tracking": [999],
            "completion_dates": {"123": 10},
            "recent": [],
            "variables": {},
        }

    def test_cycle_accept_completion_replay_and_reset(self):
        state, cycle, applied = m.begin(
            self.state,
            self.definition,
            now_ms=1000,
            previous_cycle=None,
            policy="fixed_native_anchor_v1",
        )
        self.assertTrue(applied)
        self.assertEqual(cycle, 0)
        self.assertIn(1215, state["tracking"])
        same, _, applied = m.begin(
            state,
            self.definition,
            now_ms=2000,
            previous_cycle=0,
            policy="fixed_native_anchor_v1",
        )
        self.assertFalse(applied)
        self.assertEqual(same, state)
        done, rewards, changed = m.finish(
            state,
            self.definition,
            2176,
            now_ms=2000,
            accepted_cycle=0,
            policy="fixed_native_anchor_v1",
        )
        self.assertTrue(changed)
        self.assertEqual(rewards[0]["d"], 2006)
        self.assertIn(1215, done["completed"])
        replay, rewards, changed = m.finish(
            done,
            self.definition,
            2176,
            now_ms=2000,
            accepted_cycle=0,
            policy="fixed_native_anchor_v1",
        )
        self.assertFalse(changed)
        self.assertFalse(rewards)
        self.assertEqual(replay, done)
        next_state, cycle, applied = m.begin(
            done,
            self.definition,
            now_ms=86401000,
            previous_cycle=0,
            policy="fixed_native_anchor_v1",
        )
        self.assertTrue(applied)
        self.assertEqual(cycle, 1)
        self.assertNotIn(2176, next_state["objectives"])
        self.assertIn(1234, next_state["objectives"])
        self.assertIn(123, next_state["completed"])
        self.assertIn(1215, next_state["running"])

    def test_replayed_partial_objective_is_not_applied_twice(self):
        self.definition["cjJ"].append({"d": 2177})
        state, _, _ = m.begin(
            self.state,
            self.definition,
            now_ms=1000,
            previous_cycle=None,
            policy="fixed_native_anchor_v1",
        )
        state, rewards, changed = m.finish(
            state,
            self.definition,
            2176,
            now_ms=2000,
            accepted_cycle=0,
            policy="fixed_native_anchor_v1",
        )
        self.assertTrue(changed)
        self.assertEqual(rewards, [])
        replay, rewards, changed = m.finish(
            state,
            self.definition,
            2176,
            now_ms=2000,
            accepted_cycle=0,
            policy="fixed_native_anchor_v1",
        )
        self.assertFalse(changed)
        self.assertEqual(rewards, [])
        self.assertEqual(replay, state)

    def test_invalid_cycle_does_not_advance(self):
        state, _, _ = m.begin(
            self.state,
            self.definition,
            now_ms=1000,
            previous_cycle=None,
            policy="fixed_native_anchor_v1",
        )
        with self.assertRaises(ValueError):
            m.finish(
                state,
                self.definition,
                2176,
                now_ms=86401000,
                accepted_cycle=0,
                policy="fixed_native_anchor_v1",
            )
        with self.assertRaises(ValueError):
            m.finish(
                state,
                self.definition,
                1234,
                now_ms=2000,
                accepted_cycle=0,
                policy="fixed_native_anchor_v1",
            )
        self.assertNotIn(2176, state["objectives"])
        with self.assertRaises(ValueError):
            m.cycle_index(self.definition, 999, policy="fixed_native_anchor_v1")
        with self.assertRaises(ValueError):
            m.cycle_index(self.definition, 1000, policy="unknown")


if __name__ == "__main__":
    unittest.main()
