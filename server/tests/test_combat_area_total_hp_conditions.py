"""Native faV total-HP authority, absence and criterion regression tests."""
import unittest

from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_range_conditions import total_hp_percent


class NativeAreaTotalHpTests(unittest.TestCase):
    def test_actual_faw_absent_hp_and_hp_owning_constructors(self):
        from wakfu_server.combat_area_total_hp_conditions import area_total_hp_snapshot
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        import test_combat_fake_fighter_area as fixture_module

        fixture = fixture_module.NativeFakeFighterAreaTests()
        fight, creator, _, _ = fixture.create()
        self.assertTrue(
            creator(
                {"effect_class": 339},
                {"parameters": [1035]},
                EffectInvocation(100, 1, 7, None, (2, 3, 0)),
            )
        )
        self.assertEqual(
            area_total_hp_snapshot(fight, 901),
            ({}, {}, frozenset({"HP", "VIRTUAL_HP"})),
        )

        fight, creator, _, _ = fixture.create()
        creator.fake_fighter_hp_enabled = True
        self.assertTrue(
            creator(
                {"effect_class": 339},
                {"parameters": [1688, 200]},
                EffectInvocation(323843, 200, 7, None, (2, 3, 0)),
            )
        )
        current, maxima, absent = area_total_hp_snapshot(fight, 901)
        self.assertEqual(set(current), {"HP"})
        self.assertEqual(set(maxima), {"HP"})
        self.assertGreater(maxima["HP"], 0)
        self.assertEqual(absent, frozenset({"VIRTUAL_HP"}))

    def test_actual_fbd_current_hp_retired_qi_and_total_hp_criterion(self):
        from types import SimpleNamespace
        from wakfu_server.combat_area_total_hp_conditions import area_total_hp_snapshot
        from wakfu_server.combat_effect_area import remove_owned_hour_area
        from wakfu_server.combat_state_managers import selected_area_pv_scope
        from wakfu_server.combat_wall_area import update_wall_hp
        from test_native_hp_area_completion import NativeHpAreaDeathTests

        fight, _fake, wall, _events = NativeHpAreaDeathTests().fixture()
        fight.native_retired_area_managers = {}
        uid = wall["uid"]
        current, maxima, absent = area_total_hp_snapshot(fight, uid)
        self.assertEqual(current["HP"], wall["native_wall_hp_current"])
        self.assertEqual(absent, frozenset({"VIRTUAL_HP"}))
        hp_context = ConditionContext(
            {
                "target": ConditionActor(
                    characteristics=current,
                    characteristic_maxima=maxima,
                    total_hp_absent_characteristics=absent,
                )
            }
        )
        self.assertTrue(
            evaluate_condition('GetTotalHpInPercent("target") >= 65', hp_context)
        )

        update_wall_hp(wall, wall["native_wall_constructor"], 0)
        self.assertEqual(area_total_hp_snapshot(fight, uid)[0], {"HP": 0})
        with selected_area_pv_scope(fight, (uid,)):
            removed = remove_owned_hour_area(
                fight, uid, callbacks=SimpleNamespace(removed=lambda _row: None)
            )
            self.assertEqual(removed, (wall,))
            current, maxima, absent = area_total_hp_snapshot(fight, uid)
            self.assertEqual(current, {"HP": 0})
            self.assertGreater(maxima["HP"], 0)
            self.assertEqual(absent, frozenset({"VIRTUAL_HP"}))

    def test_actual_trap_and_plain_area_have_only_source_proven_absence(self):
        from wakfu_server.combat_area_total_hp_conditions import area_total_hp_snapshot
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        import test_combat_fake_fighter_area as fixture_module

        fixture = fixture_module.NativeFakeFighterAreaTests()
        trap_references = [
            int(ref)
            for ref, definition in native_effect_areas().items()
            if definition.get("type") == "TRAP"
        ]
        self.assertTrue(trap_references)
        for reference, expected in ((trap_references[0], "fbc"), (823, None)):
            fight, creator, _, _ = fixture.create()
            family = 339 if expected == "fbc" else 315
            self.assertTrue(
                creator(
                    {"effect_class": family},
                    {"parameters": [reference]},
                    EffectInvocation(100, 1, 7, None, (2, 3, 0)),
                )
            )
            row = fight.native_effect_areas[901]
            if expected is not None:
                self.assertEqual(row["native_area_contract"], expected)
            else:
                self.assertNotIn(row["native_area_contract"], {"faW", "fbd", "fbc"})
            self.assertEqual(
                area_total_hp_snapshot(fight, 901),
                ({}, {}, frozenset({"HP", "VIRTUAL_HP"})),
            )

    def test_unknown_or_tampered_native_area_never_becomes_absence(self):
        from wakfu_server.combat_area_total_hp_conditions import area_total_hp_snapshot
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        import test_combat_fake_fighter_area as fixture_module

        fixture = fixture_module.NativeFakeFighterAreaTests()
        fight, creator, _, _ = fixture.create()
        self.assertTrue(
            creator(
                {"effect_class": 339},
                {"parameters": [1035]},
                EffectInvocation(100, 1, 7, None, (2, 3, 0)),
            )
        )
        with self.assertRaises(ValueError):
            area_total_hp_snapshot(fight, 999999)
        row = fight.native_effect_areas[901]
        row["native_faw_constructor"]["characteristic_ids"] = (1, 97)
        with self.assertRaises(ValueError):
            area_total_hp_snapshot(fight, 901)

    def test_missing_actor_hp_stays_strict_and_java_float_int_edges_are_preserved(self):
        missing = ConditionContext({"target": ConditionActor()})
        with self.assertRaises(UnknownCondition):
            evaluate_condition('GetTotalHpInPercent("target") >= 0', missing)
        absent = ConditionContext(
            {
                "target": ConditionActor(
                    characteristics={},
                    characteristic_maxima={},
                    total_hp_absent_characteristics=frozenset({"HP", "VIRTUAL_HP"}),
                )
            }
        )
        self.assertTrue(
            evaluate_condition('GetTotalHpInPercent("target") == 0', absent)
        )
        self.assertEqual(
            total_hp_percent({"HP": 1, "VIRTUAL_HP": 0}, {"HP": 3, "VIRTUAL_HP": 0}),
            33.333335876464844,
        )
        self.assertEqual(
            total_hp_percent({"HP": 0, "VIRTUAL_HP": 0}, {"HP": 0, "VIRTUAL_HP": 0}),
            0.0,
        )
        self.assertGreater(
            total_hp_percent(
                {"HP": 2147483647, "VIRTUAL_HP": 1},
                {"HP": 2147483647, "VIRTUAL_HP": 1000000},
            ),
            100.0,
        )  # Both Java int sums wrap negative before float32 division.
        with self.assertRaises(ValueError):
            total_hp_percent({"HP": True, "VIRTUAL_HP": 0}, {"HP": 1, "VIRTUAL_HP": 0})
        with self.assertRaises(ValueError):
            total_hp_percent(
                {"HP": 1, "VIRTUAL_HP": 0},
                {"HP": 1, "VIRTUAL_HP": 0},
                known_absent=frozenset({"HP"}),
            )


if __name__ == "__main__":
    unittest.main()
