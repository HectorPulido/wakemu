import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import rii_native_initial_states


class RiiNativeInitialStateTests(unittest.TestCase):
    def test_only_owned_native_los_contract_installs_original_states_in_order(self):
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(team=0), -2: SimpleNamespace(team=1)},
            rii_los_lesson_contract={
                "owner": 7,
                "target": -2,
                "native_los_areas": True,
            },
        )
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        apply = unittest.mock.Mock()
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.rift_native_gameplay": SimpleNamespace(
                    apply_native_carrier=apply
                )
            },
        ):
            self.assertTrue(rii_native_initial_states.install(dispatcher))
            self.assertEqual(
                [c.kwargs for c in apply.call_args_list],
                [
                    {
                        "actor_id": -2,
                        "reference": 8005,
                        "grade": 1,
                        "caster_id": -2,
                    },
                    {
                        "actor_id": 7,
                        "reference": 8003,
                        "grade": 1,
                        "caster_id": -2,
                    },
                ],
            )

    def test_ordinary_and_legacy_encounters_remain_untouched(self):
        fight = SimpleNamespace(
            actors={}, rii_los_lesson_contract={"owner": 7, "target": -2}
        )
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        apply = unittest.mock.Mock()
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.rift_native_gameplay": SimpleNamespace(
                    apply_native_carrier=apply
                )
            },
        ):
            self.assertFalse(rii_native_initial_states.install(dispatcher))
            apply.assert_not_called()

    def test_invalid_participants_rejected(self):
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(team=0), -2: SimpleNamespace(team=0)},
            rii_los_lesson_contract={
                "owner": 7,
                "target": -2,
                "native_los_areas": True,
            },
        )
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.rift_native_gameplay": SimpleNamespace(
                    apply_native_carrier=unittest.mock.Mock()
                )
            },
        ):
            with self.assertRaises(ValueError):
                rii_native_initial_states.install(dispatcher)

    def test_orientation_sack_receives_the_captured_floor_mark_carrier(self):
        fight = SimpleNamespace(
            actors={293: SimpleNamespace(team=0), -2: SimpleNamespace(team=1)},
            rii_orientation_contract={"owner": 7, "target": -2},
        )
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        apply = unittest.mock.Mock()
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.rift_native_gameplay": SimpleNamespace(
                    apply_native_carrier=apply
                )
            },
        ):
            self.assertTrue(rii_native_initial_states.install(dispatcher))
            self.assertEqual(
                [c.kwargs for c in apply.call_args_list],
                [{"actor_id": -2, "reference": 7884, "grade": 1}],
            )

    def test_distance_sack_receives_its_captured_floor_mark_carrier(self):
        fight = SimpleNamespace(
            actors={293: SimpleNamespace(team=0), -2: SimpleNamespace(team=1)},
            rii_distance_lesson_contract={
                "owner": 293,
                "target": -2,
                "hits": 0,
                "initialized": None,
            },
        )
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        apply = unittest.mock.Mock()
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.rift_native_gameplay": SimpleNamespace(
                    apply_native_carrier=apply
                )
            },
        ):
            self.assertTrue(rii_native_initial_states.install(dispatcher))
            self.assertEqual(
                [c.kwargs for c in apply.call_args_list],
                [
                    {
                        "actor_id": -2,
                        "reference": 7922,
                        "grade": 1,
                        "caster_id": -2,
                    },
                    {
                        "actor_id": 293,
                        "reference": 8003,
                        "grade": 1,
                        "caster_id": -2,
                    },
                ],
            )

    def test_orientation_carrier_matches_the_captured_family_330_sprites(self):
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        definition = native_catalog.load(DATA_ROOT / "combat-state-definitions.json")
        orientation = definition["states"]["7884"]["levels"][0]["effects"]
        distance = definition["states"]["7922"]["levels"][0]["effects"]
        self.assertIn(353144, orientation)
        self.assertIn(353150, orientation)
        self.assertIn(353152, orientation)
        self.assertIn(361144, orientation)
        self.assertIn(357586, distance)
        self.assertIn(361199, distance)

    def test_native_lesson_installs_the_original_target_then_owner_carriers(self):
        lessons = (
            ("rii_element_lesson_contract", 8004, [-2]),
            ("rii_distance_lesson_contract", 7922, [-2]),
            ("rii_los_lesson_contract", 8005, [-2]),
            ("rii_area_lesson_contract", 8007, [-2, -3, -4, -5]),
            ("rii_movement_lesson_contract", 8011, [-2]),
            ("rii_states_lesson_contract", 8012, [-2]),
        )
        for attribute, state, targets in lessons:
            with self.subTest(lesson=attribute):
                actors = {7: SimpleNamespace(team=0, position=(1, -12, 0))}
                actors.update(
                    {
                        target: SimpleNamespace(
                            team=1,
                            position=(
                                (0, -12, 0)
                                if attribute == "rii_area_lesson_contract"
                                and index == 0
                                else (index + 1, -12, 0)
                            ),
                        )
                        for index, target in enumerate(targets)
                    }
                )
                contract = {"owner": 7, "native_lesson": False}
                if attribute == "rii_area_lesson_contract":
                    contract["targets"] = targets
                else:
                    contract["target"] = targets[0]
                if attribute == "rii_los_lesson_contract":
                    contract["native_los_areas"] = True
                fight = SimpleNamespace(actors=actors, **{attribute: contract})
                dispatcher = SimpleNamespace(
                    native_retention=SimpleNamespace(fight=fight)
                )
                apply = unittest.mock.Mock()
                with patch.dict(
                    sys.modules,
                    {
                        "wakfu_server.rift_native_gameplay": SimpleNamespace(
                            apply_native_carrier=apply
                        )
                    },
                ):
                    self.assertTrue(rii_native_initial_states.install(dispatcher))
                source = targets[0]
                self.assertEqual(
                    [call.kwargs for call in apply.call_args_list],
                    [
                        *(
                            {
                                "actor_id": target,
                                "reference": state,
                                "grade": 1,
                                "caster_id": source,
                            }
                            for target in targets
                        ),
                        {
                            "actor_id": 7,
                            "reference": 8003,
                            "grade": 1,
                            "caster_id": source,
                        },
                    ],
                )
                self.assertTrue(contract["native_lesson"])
                self.assertTrue(contract["initialized"])

    def test_native_area_progress_waits_for_resolved_damage_to_every_sack(self):
        from wakfu_server.achievements.rii_native_initial_states import observe_damage

        contract = {"native_lesson": True, "owner": 7, "targets": [-2, -3, -4, -5]}
        fight = SimpleNamespace(rii_area_lesson_contract=contract)
        observe_damage(fight, -2, 25)
        observe_damage(fight, -3, 25)
        observe_damage(fight, -4, 25)
        self.assertEqual(contract["hits"], 0)
        observe_damage(fight, -5, 24)
        self.assertEqual(contract["hits"], 0)
        observe_damage(fight, -5, 1)
        self.assertEqual(contract["hits"], 1)
        observe_damage(fight, -6, 100)
        observe_damage(fight, -5, 0)
        self.assertEqual(contract["hits"], 1)


if __name__ == "__main__":
    unittest.main()
