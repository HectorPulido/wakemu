import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_condition_los import native_condition_los


class NativeConditionLosTests(unittest.TestCase):
    def fight(self):
        source = SimpleNamespace(id=1, position=(0, 0, 0), physical_radius=0)
        target = SimpleNamespace(id=2, position=(3, 4, 5), physical_radius=1, hp=0)
        return SimpleNamespace(
            actors={1: source, 2: target},
            native_effect_areas={7: {}},
            native_qi_visibility_ignored_slots=[9],
        )

    def test_actor_footprint_order_includes_off_play_target_and_cleans_each_ray(self):
        fight = self.fight()
        seen = []

        def ray(fight, properties, source, cell, target):
            seen.append(
                (cell, tuple(fight.native_qi_visibility_ignored_slots), target.id)
            )
            return len(seen) == 3

        with patch(
            "wakfu_server.combat_casting_los.native_casting_los", side_effect=ray
        ):
            self.assertTrue(
                native_condition_los(
                    fight,
                    lambda f, a: None,
                    1,
                    2,
                    (99, 99, 99),
                    actor_property_authority=object(),
                )
            )
        self.assertEqual([row[0] for row in seen], [(2, 3, 5), (2, 4, 5), (2, 5, 5)])
        self.assertEqual([row[1] for row in seen], [(9,), (), ()])
        self.assertEqual(fight.native_qi_visibility_ignored_slots, [])

    def test_qq_target_returns_false_without_ray(self):
        with patch("wakfu_server.combat_casting_los.native_casting_los") as ray:
            self.assertFalse(
                native_condition_los(
                    self.fight(),
                    lambda f, a: None,
                    1,
                    7,
                    (3, 4, 5),
                    actor_property_authority=object(),
                )
            )
        ray.assert_not_called()

    def test_actual_fav_area_is_ehg_with_literal_zero_radius_and_height(self):
        fight = self.fight()
        fight.native_effect_areas[7] = dict(native_area_contract="faZ", cell=[3, 4, 5])
        target = SimpleNamespace(position=(3, 4, 5), native_los_height=0)
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv", return_value=target
        ), patch(
            "wakfu_server.combat_casting_los.native_casting_los", return_value=True
        ) as ray:
            self.assertTrue(
                native_condition_los(
                    fight,
                    lambda f, a: None,
                    1,
                    7,
                    (99, 99, 99),
                    actor_property_authority=object(),
                )
            )
        self.assertEqual(ray.call_args.args[3], (3, 4, 5))
        self.assertEqual(ray.call_args.args[4].native_los_height, 0)

    def test_area_height_is_forwarded_from_registered_source(self):
        fight = self.fight()
        fight.native_effect_areas[7] = dict(native_area_contract="faW", cell=[3, 4, 5])
        target = SimpleNamespace(position=(3, 4, 5), native_los_height=6)
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv", return_value=target
        ), patch(
            "wakfu_server.combat_casting_los.native_casting_los", return_value=True
        ) as ray:
            self.assertTrue(
                native_condition_los(
                    fight,
                    lambda f, a: None,
                    1,
                    7,
                    None,
                    actor_property_authority=object(),
                )
            )
        self.assertIs(ray.call_args.args[4], target)
        self.assertEqual(ray.call_args.args[4].native_los_height, 6)

    def test_actual_cell_is_singleton_and_uses_first_qi_fighter_height(self):
        fight = self.fight()
        registry = SimpleNamespace(
            ordered_U=lambda x, y: (0,), slots=[dict(identity=["actor", 2])]
        )
        with patch(
            "wakfu_server.combat_qi_fight.current_registry", return_value=registry
        ), patch(
            "wakfu_server.combat_casting_los.native_casting_los", return_value=True
        ) as ray:
            self.assertTrue(
                native_condition_los(
                    fight,
                    lambda f, a: SimpleNamespace(targeting={"is_eGj": True}),
                    1,
                    2,
                    (8, 9, 10),
                    actor_property_authority=object(),
                    target_is_cell=True,
                )
            )
        self.assertEqual(ray.call_args.args[3], (8, 9, 10))
        self.assertIs(ray.call_args.args[4], fight.actors[2])
