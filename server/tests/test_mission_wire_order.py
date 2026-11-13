"""Mission activation emits native order only with safe reset evidence."""
import struct
import unittest
from wakfu_server.achievements import wire


def state(**overrides):
    value = dict(
        running=[], completed=[], tracking=[], objectives=[], variables={}, recent=[]
    )
    value.update(overrides)
    return value


def definition(identity, objective, variable=None):
    return {
        "d": identity,
        "cjJ": [
            {
                "d": objective,
                "ckf": []
                if variable is None
                else [{"d": variable + 1000, "ckn": [variable]}],
            }
        ],
    }


class MissionWireOrderTests(unittest.TestCase):
    def test_interleaves_reset_activation_and_tracking_for_multiple_missions(self):
        before = state(objectives=[900], variables={"70": 4})
        after = state(
            running=[10, 20], tracking=[10, 20], objectives=[900], variables={"70": 4}
        )
        definitions = {10: definition(10, 101, 11), 20: definition(20, 201, 21)}
        packets = wire.changes(7, before, after, [], [], 1, definitions=definitions)
        self.assertEqual(
            [(op, struct.unpack(">i", body[8:12])[0]) for op, body in packets],
            [
                (13205, 10),
                (13312, 10),
                (13371, 10),
                (13205, 20),
                (13312, 20),
                (13371, 20),
            ],
        )

    def test_avoids_reset_for_existing_objective_variable_or_prior_cycle(self):
        definitions = {10: definition(10, 101, 11)}
        for before in (
            state(objectives=[101]),
            state(variables={"11": 1}),
            state(recent=[{"id": 10, "date_ms": 1}]),
            state(completed=[10]),
        ):
            after = state(
                running=[10],
                tracking=[10],
                objectives=before["objectives"],
                variables=before["variables"],
            )
            packets = wire.changes(7, before, after, [], [], 1, definitions=definitions)
            self.assertNotIn(13205, [op for op, _ in packets])

    def test_unknown_definition_never_resets(self):
        packets = wire.changes(
            7, state(objectives=[55]), state(running=[10], tracking=[10]), [], [], 1
        )
        self.assertEqual([op for op, _ in packets], [13312, 13371])

    def test_objective_refreshes_only_its_stably_followed_running_mission(self):
        before = state(running=[10, 20], tracking=[10, 20])
        after = state(running=[10, 20], tracking=[10, 20], objectives=[101])
        definitions = {10: definition(10, 101), 20: definition(20, 201)}
        packets = wire.changes(7, before, after, [101], [], 1, definitions=definitions)
        self.assertEqual([op for op, _ in packets], [13832, 13371, 13371])
        self.assertEqual(
            [struct.unpack(">qiB", body) for op, body in packets if op == 13371],
            [(7, 10, 0), (7, 10, 1)],
        )
        self.assertEqual(after["tracking"], [10, 20])

    def test_counter_updates_refresh_only_mapped_followed_mission(self):
        before = state(running=[10, 20], tracking=[10, 20], variables={"11": 0})
        after = state(running=[10, 20], tracking=[10, 20], variables={"11": 1})
        definitions = {10: definition(10, 101, 11), 20: definition(20, 201, 21)}
        packets = wire.changes(7, before, after, [], [], 1, definitions=definitions)
        self.assertEqual([op for op, _ in packets], [13295, 13371, 13371])
        self.assertEqual(
            [struct.unpack(">qiB", body) for op, body in packets if op == 13371],
            [(7, 10, 0), (7, 10, 1)],
        )
        self.assertEqual(after["tracking"], [10, 20])

    def test_no_refresh_for_untracked_completed_unknown_or_over_capacity(self):
        definitions = {10: definition(10, 101)}
        cases = [
            (state(running=[10]), state(running=[10], objectives=[101])),
            (
                state(running=[10], tracking=[10]),
                state(completed=[10], tracking=[10], objectives=[101]),
            ),
            (
                state(running=[10], tracking=[10]),
                state(running=[10], tracking=[10], objectives=[101]),
            ),
            (
                state(running=[10], tracking=[10, 20, 30, 40, 50]),
                state(running=[10], tracking=[10, 20, 30, 40, 50], objectives=[101]),
            ),
        ]
        for index, (before, after) in enumerate(cases):
            with self.subTest(index=index):
                mappings = {} if index == 2 else definitions
                packets = wire.changes(
                    7, before, after, [101], [], 1, definitions=mappings
                )
                self.assertEqual([op for op, _ in packets], [13832])


if __name__ == "__main__":
    unittest.main()
