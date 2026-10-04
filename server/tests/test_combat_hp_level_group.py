import unittest
from wakfu_server.combat_hp_level_group import hp_group_override


def effect(count=11, mode=2, base=0, growth=1, rounding=1):
    values = [0, 0, 1, 0, 1, 0, 1, 1, base, growth, mode, rounding][:count]
    return dict(effect_class=1047, parameters=[n for v in values for n in (v, 0)])


class HPGroupTests(unittest.TestCase):
    def calculate(self, e, **kw):
        data = dict(
            current_hp=60, maximum_hp=100, current_virtual_hp=20, maximum_virtual_hp=50
        )
        data.update(kw)
        return hp_group_override(e, 1, **data, return_native_override=True)

    def test_native_probe_hp_plus_virtual_modes(self):
        self.assertEqual(
            [self.calculate(effect(mode=m)) for m in range(5)], [80, 150, 53, 46, 70]
        )

    def test_divisor_variant_and_native_negative_floor(self):
        self.assertEqual(self.calculate(effect(count=9, base=3)), 26)
        self.assertEqual(self.calculate(effect(count=9, base=-3)), -27)
        self.assertEqual(self.calculate(effect(count=9, base=0)), 80)

    def test_native_rounding_and_previous_level_sentinel(self):
        self.assertEqual(
            [
                self.calculate(effect(count=12, base=0.6, growth=0, rounding=r))
                for r in (1, 2, 3, 999)
            ],
            [1, 0, 1, 1],
        )
        e = effect(base=-1, growth=0)
        self.assertEqual(
            hp_group_override(
                e,
                20,
                current_hp=60,
                maximum_hp=100,
                current_virtual_hp=0,
                maximum_virtual_hp=0,
            ),
            20,
        )

    def test_unknown_snapshots_and_native_zero_division_reject(self):
        with self.assertRaises(ValueError):
            self.calculate(effect(), current_virtual_hp=None)
        with self.assertRaisesRegex(ValueError, "zero"):
            self.calculate(effect(), maximum_hp=0, maximum_virtual_hp=0)

    def test_integer_percent_uses_java_overflow_and_truncation(self):
        self.assertEqual(
            self.calculate(effect(mode=2), current_hp=-1, current_virtual_hp=0), 0
        )
        self.assertEqual(
            self.calculate(effect(mode=4), current_hp=2147483647, current_virtual_hp=1),
            -2147483520,
        )

    def test_current_native_hp_snapshot_changes_after_authoritative_damage(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_hp_level_group import runtime_group_level

        actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True, max_hp=100)
        enemy = Actor(8, 1, (1, 0, 0), 100, 6, 3, 1, 1)
        actor.effect_stats = {1: 60, 92: 20}
        actor.effect_maxima = {1: 100, 92: 50}
        fight = Fight(
            123,
            [actor, enemy],
            {actor.position, enemy.position},
            {0: {actor.position}, 1: {enemy.position}},
        )
        fight.ready(3)
        native = effect()
        native["native_execution_mode"] = 0
        values = dict(parameters=[0, 0, 1, 0, 1, 0, 1, 1, 0, 1, 2])
        invocation = EffectInvocation(416616, 1, 7, 7, actor.position)
        self.assertEqual(
            runtime_group_level(native, values, invocation, fight.actors), 53
        )
        fight.apply_effect_damage(8, 7, 20)
        self.assertEqual(
            runtime_group_level(native, values, invocation, fight.actors), 40
        )
