import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_ready import prepare_ready


class ReadyTests(unittest.TestCase):
    def fight(self):
        cells = {(0, 0, 0), (1, 0, 0)}
        return Fight(
            7,
            [
                Actor(100, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
            ],
            cells,
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )

    def run_ready(self, fight, callback):
        return prepare_ready(
            fight,
            1,
            True,
            initialize=callback,
            stats_serializer=lambda actor: b"base",
            effects_serializer=lambda: b"\0\0",
        )

    def test_failure_after_mutation_does_not_commit_readiness_or_effects(self):
        fight = self.fight()

        def fail(preview, action):
            preview.actors[100].hp = 1
            raise ValueError("unsupported mandatory innate")

        with self.assertRaises(ValueError):
            self.run_ready(fight, fail)
        self.assertEqual(
            (fight.phase, fight.ready_owners, fight.actors[100].hp),
            ("placement", set(), 60),
        )

    def test_initialization_follows_action_before_first_turn_and_duplicate_is_noop(
        self,
    ):
        fight = self.fight()
        calls = []

        def initialize(preview, action):
            calls.append(action)
            preview.native_class_initializations = {100: {"breed": 8}}
            return preview, ((12613, b"innate"),)

        preview, messages, packets = self.run_ready(fight, initialize)
        ops = [op for op, _ in packets]
        self.assertLess(ops.index(13912), ops.index(12514))
        self.assertEqual(
            ops[ops.index(12514) + 1 : ops.index(13477)], [12613, 13420, 12873]
        )
        self.assertEqual(
            (fight.phase, preview.phase, calls), ("placement", "active", [1])
        )
        same, no_messages, no_packets = self.run_ready(preview, initialize)
        self.assertIs(same, preview)
        self.assertIsNone(no_messages)
        self.assertEqual((no_packets, calls), ((), [1]))
        self.assertGreater(messages.action_id, 1)
