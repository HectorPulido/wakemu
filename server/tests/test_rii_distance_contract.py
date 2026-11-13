import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_distance_contract as distance


class DistanceContractTests(unittest.TestCase):
    def setUp(self):
        self.owner = SimpleNamespace(position=(0, 0, 0))
        self.target = SimpleNamespace(position=(1, 0, 0))
        self.fight = SimpleNamespace(
            actors={7: self.owner, -9: self.target},
            rii_distance_lesson_contract={"owner": 7, "target": -9, "hits": 0},
        )

    def hit(self, **overrides):
        values = {
            "source_id": 7,
            "target_id": -9,
            "effect_reference": distance.DAMAGE_EFFECT,
            "damage": 400,
        }
        values.update(overrides)
        return distance.hit(self.fight, **values)

    def test_four_alternating_zones_and_bounded_damage(self):
        for target_x in (1, 3, 2, 4):
            self.target.position = (target_x, 0, 0)
            self.assertEqual(self.hit(), 25)
        self.assertTrue(distance.qualified(self.fight))
        self.assertEqual(self.hit(), 0)

    def test_wrong_hit_cannot_damage_or_progress(self):
        self.assertEqual(self.hit(source_id=8), 0)
        self.assertEqual(self.hit(effect_reference=1), 0)
        self.assertEqual(self.hit(damage=0), 0)
        self.target.position = (3, 0, 0)
        self.assertEqual(self.hit(), 0)
        self.assertEqual(self.fight.rii_distance_lesson_contract["hits"], 0)
        self.assertIsNone(self.hit(target_id=-10))

    def test_unbound_combat_is_untouched_and_missing_actor_fails(self):
        self.fight.rii_distance_lesson_contract = None
        self.assertIsNone(self.hit())
        self.fight.rii_distance_lesson_contract = {"owner": 7, "target": -9, "hits": 0}
        del self.fight.actors[-9]
        with self.assertRaises(ValueError):
            self.hit()

    def test_initialization_installs_only_distance_grant_once(self):
        from wakfu_server import rii_lesson_grants

        self.fight.phase = "active"
        self.fight.allocate_effect_uid = Mock()
        self.owner.team, self.target.team = 0, 1
        packets = []
        with patch.object(rii_lesson_grants, "install", return_value=[17]) as install:
            self.assertTrue(distance.initialize(self.fight, packets, action_id=10))
            self.assertEqual(
                self.fight.rii_distance_lesson_contract["grant_uids"], [17]
            )
            self.assertEqual(install.call_args.kwargs["lesson"], "distance")
            with self.assertRaises(ValueError):
                distance.initialize(self.fight, packets, action_id=10)


if __name__ == "__main__":
    unittest.main()
