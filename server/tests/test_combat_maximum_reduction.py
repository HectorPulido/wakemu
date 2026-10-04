import unittest
import test_combat_maximum_resource as fixture
from wakfu_server.combat_maximum_resource import NativeMaximumReductionHandler
from wakfu_server.combat_stat_handler import NativeStatHandler
from wakfu_server.combat_timed_expiration import prepare_timed_expiration


class MaximumReductionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.MaximumResourceTests()
        self.f.setUp()
        self.handler = NativeMaximumReductionHandler(
            self.f.fight,
            self.f.packets,
            action_id=1,
            allocate_uid=self.f.handler.allocate_uid,
            context=self.f.handler.context,
        )

    def apply(self, kind=57, parameters=None):
        return self.handler(
            dict(
                effect_class=kind,
                parameters=[1.0, 0.0] if parameters is None else parameters,
            ),
            {},
            self.f.invocation,
        )

    def test_actual_uginak_one_mp_definition_and_expiration(self):
        self.assertTrue(self.apply())  # Native340104 family57 amount1.
        a = self.f.actor
        self.assertEqual((a.mp, a.max_mp, a.effect_base_minima[3]), (2, 2, -1))
        p, packets = prepare_timed_expiration(
            self.f.fight,
            actor_id=7,
            round_number=2,
            phase="start",
            action_id=2,
            registry={"effects": {}},
        )
        self.assertEqual(
            (p.actors[7].mp, p.actors[7].max_mp, p.actors[7].effect_base_minima[3]),
            (3, 3, 0),
        )
        self.assertEqual([op for op, _ in packets], [13560])

    def test_actual_sacrier_two_wp_and_remove_requested(self):
        self.apply(kind=192, parameters=[2.0, 0.0])  # Native353800 family192 amount2.
        a = self.f.actor
        self.assertEqual(
            (a.effect_stats[4], a.effect_maxima[4], a.effect_base_minima[4]), (4, 4, -2)
        )
        remover = NativeStatHandler(
            self.f.fight,
            self.f.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        )
        remover.remove(101)
        self.assertEqual(
            (a.effect_stats[4], a.effect_maxima[4], a.effect_base_minima[4]), (6, 6, 0)
        )

    def test_steal_all_is_current_and_no_restore_flag(self):
        self.f.actor.mp = 2
        self.f.actor.effect_stats[3] = 2
        self.apply(parameters=[-2.0, 0.0, 100.0, 0.0, 0.0, 0.0])
        self.assertEqual((self.f.actor.mp, self.f.actor.max_mp), (0, 1))
        NativeStatHandler(
            self.f.fight,
            self.f.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        ).remove(101)
        self.assertEqual((self.f.actor.mp, self.f.actor.max_mp), (0, 3))

    def test_chance_not_guessed_or_mutated(self):
        with self.assertRaisesRegex(ValueError, "chance RNG"):
            self.apply(parameters=[1.0, 0.0, 50.0, 0.0])
        self.assertEqual((self.f.uid, self.f.actor.mp, self.f.packets), (100, 3, []))
        self.handler.probability = lambda *a: False
        self.assertFalse(self.apply(parameters=[1.0, 0.0, 0.0, 0.0]))
        self.assertEqual((self.f.uid, self.f.actor.mp, self.f.packets), (100, 3, []))

    def test_percentage_restoration_follows_requested_native_value(self):
        a = self.f.actor
        a.effect_percentages[3] = 50
        a.effect_stats[3] = 4
        a.effect_maxima[3] = 4
        a.mp = 4
        a.max_mp = 4
        self.apply(parameters=[2.0, 0.0])
        self.assertEqual((a.mp, a.max_mp, a.effect_base_maxima[3]), (1, 1, 1))
        NativeStatHandler(
            self.f.fight,
            self.f.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        ).remove(101)
        self.assertEqual((a.mp, a.max_mp, a.effect_base_maxima[3]), (3, 4, 3))
