import random
import unittest
from wakfu_server.combat_force_characteristic import (
    forced_parameters,
    forced_transition,
)


class ForcedCharacteristicTests(unittest.TestCase):
    def test_original_fzb_differs_from_expandability_for_wp_and_hp(self):
        from wakfu_server.combat_character_copy_metadata import (
            native_copy_characteristics,
        )

        definitions = native_copy_characteristics()["fresh_characteristics"]
        self.assertTrue(definitions["4"]["expandable"])
        self.assertFalse(definitions["4"]["over_max_current"])
        self.assertTrue(definitions["1"]["over_max_current"])
        common = dict(
            value=5,
            set_maximum=False,
            current=1,
            raw=2,
            maximum=2,
            minimum=0,
            raw_min=0,
            percent=0,
            low=0,
            high=20,
        )
        self.assertEqual(
            forced_transition(
                **common, over_max_current=definitions["4"]["over_max_current"]
            ),
            (2, 2, 2),
        )
        self.assertEqual(
            forced_transition(
                **common, over_max_current=definitions["1"]["over_max_current"]
            ),
            (5, 2, 2),
        )

    def test_ordinary_wp_assignment_uses_effective_bound_after_maximum_loss(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_force_characteristic import (
            NativeForcedCharacteristicHandler,
        )
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 0, 1, 3, True)
        other = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 0, 1)
        fight = Fight(
            8, [actor, other], {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        fight.ready(3)
        for name, value in (
            ("effect_stats", 1),
            ("effect_maxima", 2),
            ("effect_minima", 0),
            ("effect_base_maxima", 2),
            ("effect_base_minima", 0),
            ("effect_percentages", 0),
        ):
            setattr(actor, name, {4: value})
        actor.effect_frozen = frozenset()
        packets = []
        handler = NativeForcedCharacteristicHandler(
            fight,
            packets,
            {"effects": {"952": {"runner": "eYO", "fixed_stat_id": 4}}},
            action_id=1,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(True, True, None, False, None),
            rng=random.Random(1),
        )
        self.assertTrue(
            handler(
                {"effect_class": 952, "parameters": [5.0, 0.0]},
                [],
                EffectInvocation(413083, 200, actor.id, actor.id, actor.position),
            )
        )
        self.assertEqual((actor.effect_stats[4], actor.effect_maxima[4]), (2, 2))
        self.assertFalse(hasattr(actor, "wp"))
        self.assertEqual(len(packets), 1)

    def test_parameters_native_copy_flags_and_percentage(self):
        rng = random.Random(1)
        self.assertEqual(
            forced_parameters([], 20, caster_current=6, target_maximum=20, rng=rng),
            (6, False, False),
        )
        self.assertEqual(
            forced_parameters(
                [50, 0, 1, 0, 1, 0], 20, caster_current=6, target_maximum=20, rng=rng
            ),
            (10, True, True),
        )
        with self.assertRaises(ValueError):
            forced_parameters([1], 20, caster_current=6, target_maximum=20, rng=rng)

    def test_native_setter_bounds_and_raw_maximum_percentage(self):
        args = dict(
            current=2,
            raw=6,
            maximum=6,
            minimum=0,
            raw_min=0,
            percent=0,
            low=0,
            high=6,
            over_max_current=False,
        )
        for amount, flag, expected in (
            (4, False, (4, 6, 6)),
            (9, False, (6, 6, 6)),
            (-3, False, (0, 6, 6)),
            (9, True, (6, 9, 6)),
            (0, True, (0, 0, 0)),
        ):
            self.assertEqual(
                forced_transition(value=amount, set_maximum=flag, **args), expected
            )
        args.update(percent=50, high=100, maximum=9)
        self.assertEqual(
            forced_transition(value=4, set_maximum=True, **args), (4, 4, 6)
        )

    def test_owned_setter_packet_and_removal_does_not_revert(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_force_characteristic import (
            NativeForcedCharacteristicHandler,
            remove_forced_characteristic,
        )
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.wire import proto_fields

        actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 0, 1, 3, True)
        other = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 0, 1)
        fight = Fight(
            8, [actor, other], {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        fight.ready(3)
        actor.effect_stats = {4: 2}
        actor.effect_maxima = {4: 6}
        actor.effect_minima = {4: 0}
        actor.effect_base_maxima = {4: 6}
        actor.effect_base_minima = {4: 0}
        actor.effect_percentages = {4: 0}
        actor.effect_frozen = frozenset()
        packets = []
        handler = NativeForcedCharacteristicHandler(
            fight,
            packets,
            {"effects": {"952": {"runner": "eYO", "fixed_stat_id": 4}}},
            action_id=1,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
            rng=random.Random(1),
        )
        from dataclasses import replace
        from wakfu_server.combat_runner_callbacks import runner_value_scope

        observed = []
        with runner_value_scope(
            lambda inv, value: observed.append(
                (value, actor.effect_stats[4], len(packets))
            )
        ) as token:
            handler(
                {"effect_class": 952, "parameters": [4, 0, 1, 0]},
                [],
                replace(
                    EffectInvocation(1, 1, 7, 7, (0, 0, 0)), native_value_scope=token
                ),
            )
        self.assertEqual(observed, [(4, 4, 1)])  # aSg4, not current delta2.
        self.assertEqual((actor.effect_stats[4], actor.effect_maxima[4]), (4, 4))
        fields = dict(
            proto_fields(bytes.fromhex(fight.owned_stat_effects[101]["payload"]))
        )
        additional = dict(proto_fields(fields[66]))
        self.assertEqual((additional[136], additional[144]), (1, 0))
        remove_forced_characteristic(handler, 101)
        self.assertEqual((actor.effect_stats[4], actor.effect_maxima[4]), (4, 4))
        self.assertEqual([p[0] for p in packets], [13497, 13560])
        self.assertNotIn(101, fight.owned_stat_effects)
