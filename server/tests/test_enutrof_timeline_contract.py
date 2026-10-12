"""Native Drheller placement in the timeline is independent of initiative."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_summon import fresh_summon_insertion, summon_specification
from wakfu_server.combat_turns import initial_order


class EnutrofTimelineContractTests(unittest.TestCase):
    def test_native_drheller_profiles_insert_before_owner_without_resorting(self):
        # Actual 307 children37093/255226-255229 specify caster anchor2,
        # offset0. Tc.a inserts at that slot and preserves the current actor.
        for profile in range(1380, 1385):
            with self.subTest(profile=profile):
                order = initial_order(
                    1,
                    [
                        dict(id=7, team=0, initiative=10, effective_level=200),
                        dict(id=-7, team=1, initiative=5, effective_level=200),
                    ],
                )
                self.assertEqual(order, [7, -7])
                fight = SimpleNamespace(
                    phase="active",
                    order=order,
                    turn_index=0,
                    actors={7: object(), -7: object()},
                )
                spec = summon_specification(
                    {"effect_class": 307},
                    {"parameters": [profile, -2, 0, -1, -1, 2, 0]},
                    evaluation_level=200,
                    container_present=True,
                    caster_level=200,
                    caster_team=0,
                    caster_direction=0,
                    native_minimum_level=1,
                )
                actual, index = fresh_summon_insertion(
                    fight,
                    spec,
                    caster_id=7,
                    actor_id=28,
                )
                self.assertEqual(actual, [28, 7, -7])
                self.assertEqual(actual[index], 7)
                self.assertEqual(fight.order, [7, -7])


if __name__ == "__main__":
    unittest.main()
