"""Shared-combat join admission at native placement/team boundaries."""

import struct
import unittest

from wakfu_server.combat.combat_shared import Registry, Session
from wakfu_server.combat_state import Actor, Fight


class SharedCombatJoinCapacityTests(unittest.TestCase):
    def setUp(self):
        self.starter = Session(1, 10, "starter", 1134, 0)
        self.joiner = Session(2, 20, "joiner", 1134, 0)
        self.live = {self.starter, self.joiner}
        self.registry = Registry(lambda session: session in self.live)
        self.fight = Fight(
            99,
            [
                Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (3, 0, 0), 20, 4, 2, 1, 1),
            ],
            {(0, 0, 0), (1, 0, 0), (3, 0, 0)},
            # Team 0 is already at its exact capacity; team 1 is separate.
            {0: {(0, 0, 0)}, 1: {(3, 0, 0)}},
        )
        self.shared = self.registry.register(self.fight, self.starter)

    def _join(self, actor=None, persist_member=None):
        actor = actor or Actor(20, 0, (1, 0, 0), 55, 6, 3, 90, 1, 2, True)
        return self.registry.join(
            self.joiner,
            struct.pack(">qB", 10, 0),
            actor,
            actor_payload=lambda *_: (b"native-stats", b"native-effects"),
            bootstrap_packets=lambda *_: [(12847, b"owned-placement")],
            persist_member=persist_member,
        )

    def test_join_rejects_when_target_team_has_no_free_native_placement_cell(self):
        persisted = []
        sequence_before = self.shared.sequence

        with self.assertRaisesRegex(ValueError, "placement capacity exhausted"):
            self._join(persist_member=lambda *_: persisted.append(True))

        self.assertEqual(
            persisted, [], "admission failure must precede membership persistence"
        )
        self.assertEqual(set(self.shared.fight.actors), {10, -200})
        self.assertEqual(set(self.shared.participants), {1})
        self.assertNotIn(20, self.registry.by_character)
        self.assertEqual(self.shared.sequence, sequence_before)

    def test_join_cannot_choose_an_opposing_team_with_the_native_request(self):
        wrong_team = Actor(20, 1, (1, 0, 0), 55, 6, 3, 90, 1, 2, True)

        with self.assertRaisesRegex(ValueError, "ownership/team invalid"):
            self._join(wrong_team)

        self.assertEqual(set(self.shared.fight.actors), {10, -200})
        self.assertEqual(set(self.shared.participants), {1})
        self.assertNotIn(20, self.registry.by_character)


if __name__ == "__main__":
    unittest.main()
