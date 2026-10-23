"""Current world-member health cannot fall back past an explicit dead value."""
from copy import deepcopy
import unittest

from wakfu_server.monsters import owned_instance
from wakfu_server.objectives import environmental_monster_destroy as destroy


class EnvironmentalDestroyHealthTests(unittest.TestCase):
    def test_native_living_member_preserves_explicit_health_and_rejects_dead_or_untyped_values(
        self,
    ):
        member = owned_instance(
            2253, 1, -990001, map_id=327, instance_id=0, x=0, y=0, z=0
        )
        before = deepcopy(member)
        self.assertEqual(member["hp"], 35)
        self.assertEqual(destroy._living_member(member), 35)
        for hp in (0, -1, False, True, None, 1.0, "35"):
            with self.subTest(explicit_hp=hp), self.assertRaisesRegex(
                ValueError, "living durable world member"
            ):
                destroy._living_member(dict(member, hp=hp, stats={"HP": 35}))
        self.assertEqual(
            destroy._living_member(dict(member, hp=7, stats={"HP": 35})), 7
        )
        self.assertEqual(destroy._living_member(dict(stats={"HP": 35})), 35)
        self.assertEqual(member, before)
        for stats in ({"HP": 0}, {"HP": -1}, {"HP": True}, {"HP": None}, {}, None):
            with self.subTest(legacy_stats=stats), self.assertRaises(ValueError):
                destroy._living_member(dict(stats=stats))
