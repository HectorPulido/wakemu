import unittest
from types import SimpleNamespace
from wakfu_server.combat_captured_scaling import (
    MAIN_CHARACTERISTICS,
    SECONDARY_CHARACTERISTICS,
    scale_captured_characteristics,
    scaled_characteristic,
)


class CapturedScalingTests(unittest.TestCase):
    def test_descriptor_pa_on_preserves_raw_operand_before_native_fan(self):
        from wakfu_server.combat_hp_raw import (
            SOURCE,
            install_fresh_hp_operand,
            hp_raw_current,
        )
        from wakfu_server.combat_captured_profiles import (
            NativeCapturedDescriptor,
            initialize_captured_descriptor,
        )
        from wakfu_server.characters.captured_roster import CapturedCreature
        from wakfu_server.combat_actor_snapshot import native_actor_catalog

        fight, actor = self.fixture()
        install_fresh_hp_operand(
            actor, dict(producer=SOURCE, actor_id=actor.id, raw_current=80)
        )
        descriptor = NativeCapturedDescriptor(
            CapturedCreature(0, 4, "Tofu"), 7, 200, actor.id, 1, {}
        )
        initialize_captured_descriptor(
            actor, descriptor, definitions=native_actor_catalog()["characteristics"]
        )
        self.assertEqual((actor.hp, hp_raw_current(actor)), (1, 1))
        scale_captured_characteristics(fight, actor, 1, 1)
        self.assertEqual((actor.hp, hp_raw_current(actor)), (1, 1))

    def test_original_fan_current_reduction_and_raw_maximum(self):
        for factor, expected in (
            (0, (0, 0)),
            (0.5, (40, 50)),
            (1, (80, 100)),
            (1.5, (40, 150)),
        ):
            self.assertEqual(scaled_characteristic(80, 100, factor), expected)

    def test_signed_current_preserves_original_abs_reduction(self):
        self.assertEqual(scaled_characteristic(-80, 100, 0.5), (-120, 50))

    def test_unknown_factor_is_not_inferred(self):
        with self.assertRaises(ValueError):
            scaled_characteristic(80, 100, None)

    def fixture(self):
        from wakfu_server.combat_actor_snapshot import native_actor_catalog

        definitions = native_actor_catalog()["characteristics"]
        stats = MAIN_CHARACTERISTICS + SECONDARY_CHARACTERISTICS
        actor = SimpleNamespace(
            id=7,
            hp=80,
            max_hp=100,
            native_summon_source={
                "native_relation_source": "big.new_bje.fdt_initial_registration"
            },
            effect_stats={s: 80 for s in stats},
            effect_base_maxima={s: 100 for s in stats},
            effect_base_minima={s: definitions[str(s)]["minimum"] for s in stats},
            effect_minima={s: definitions[str(s)]["minimum"] for s in stats},
            effect_maxima={s: 100 for s in stats},
            effect_percentages={s: 0 for s in stats},
            effect_frozen=frozenset(),
        )
        return SimpleNamespace(actors={7: actor}), actor

    def test_full_map_scaling_preserves_two_distinct_native_groups(self):
        fight, actor = self.fixture()
        scale_captured_characteristics(fight, actor, 0.5, 1)
        self.assertEqual((actor.hp, actor.max_hp), (40, 50))
        self.assertEqual(actor.effect_stats[92], 40)
        self.assertEqual(actor.effect_base_maxima[92], 50)
        self.assertEqual(actor.effect_stats[35], 80)
        self.assertEqual(actor.effect_base_maxima[35], 100)

    def test_missing_pa_rejects_before_mutating_any_group(self):
        fight, actor = self.fixture()
        del actor.effect_stats[35]
        with self.assertRaises(ValueError):
            scale_captured_characteristics(fight, actor, 0.5, 0.5)
        self.assertEqual((actor.hp, actor.max_hp), (80, 100))
