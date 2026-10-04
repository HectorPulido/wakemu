import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_maximum_resource import NativeMaximumResourceHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state_timing import StateTimer
from wakfu_server.combat_timed_expiration import prepare_timed_expiration


class MaximumResourceTests(unittest.TestCase):
    def setUp(self):
        actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        self.fight = Fight(
            8,
            [actor, npc],
            {actor.position, npc.position},
            {0: {actor.position}, 1: {npc.position}},
        )
        self.fight.ready(3)
        self.actor = actor
        actor.effect_stats = {2: 6, 3: 3, 4: 6}
        actor.effect_maxima = {2: 6, 3: 3, 4: 6}
        actor.effect_minima = {2: 0, 3: 0, 4: 0}
        actor.effect_base_minima = dict(actor.effect_minima)
        actor.effect_base_maxima = dict(actor.effect_maxima)
        actor.effect_percentages = {2: 0, 3: 0, 4: 0}
        actor.effect_frozen = frozenset()
        self.packets = []
        self.uid = 100

        def allocate():
            self.uid += 1
            return self.uid

        self.handler = NativeMaximumResourceHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *a: StatExecutionContext(
                True, True, None, True, None, StateTimer(7, 2, "start")
            ),
        )
        self.invocation = EffectInvocation(999, 1, 7, 7, (0, 0, 0))

    def apply(self, kind=41, amount=1, apply=1, remove=1, flags=()):
        return self.handler(
            dict(
                effect_class=kind,
                parameters=[amount, 0.0, apply, 0.0, remove, 0.0],
                native_effect_flags=list(flags),
            ),
            [],
            self.invocation,
        )

    def test_mp_boost_and_expiration(self):
        self.assertTrue(self.apply())
        self.assertEqual((self.actor.mp, self.actor.max_mp), (4, 4))
        preview, packets = prepare_timed_expiration(
            self.fight,
            actor_id=7,
            round_number=2,
            phase="start",
            action_id=2,
            registry={"effects": {}},
        )
        self.assertEqual((preview.actors[7].mp, preview.actors[7].max_mp), (3, 3))
        self.assertEqual(self.actor.mp, 4)
        self.assertEqual([op for op, _ in packets], [13560])

    def test_native_cap_and_flag17(self):
        self.apply(amount=20)
        self.assertEqual((self.actor.mp, self.actor.max_mp), (8, 8))
        self.assertEqual(self.fight.owned_stat_effects[101]["actual"], 5)
        self.apply(amount=2, flags=[17])
        self.assertEqual((self.actor.mp, self.actor.max_mp), (10, 10))

    def test_apply_current_false_and_removal(self):
        self.apply(kind=31, amount=2, apply=0, remove=0)
        self.assertEqual((self.actor.ap, self.actor.max_ap), (6, 8))
        NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        ).remove(101)
        self.assertEqual((self.actor.ap, self.actor.max_ap), (6, 6))

    def test_wp_updates_snapshot_and_inconsistent_percent_rejects(self):
        self.apply(kind=191, amount=3)
        self.assertEqual(
            (self.actor.effect_stats[4], self.actor.effect_maxima[4]), (9, 9)
        )
        self.actor.effect_percentages[3] = 50
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.apply()
        self.assertEqual(self.uid, 101)

    def test_percent_raw_cap_and_overlapping_removal(self):
        self.actor.effect_percentages[3] = 50
        self.actor.mp = 4
        self.actor.max_mp = 4
        self.actor.effect_stats[3] = 4
        self.actor.effect_maxima[3] = 4
        self.apply(amount=1)
        self.assertEqual(
            (self.actor.mp, self.actor.max_mp, self.actor.effect_base_maxima[3]),
            (6, 6, 4),
        )
        self.apply(amount=1)
        self.assertEqual(
            (self.actor.mp, self.actor.max_mp, self.actor.effect_base_maxima[3]),
            (7, 7, 5),
        )
        remover = NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        )
        remover.remove(101)
        self.assertEqual(
            (self.actor.mp, self.actor.max_mp, self.actor.effect_base_maxima[3]),
            (5, 6, 4),
        )
        remover.remove(102)
        self.assertEqual(
            (self.actor.mp, self.actor.max_mp, self.actor.effect_base_maxima[3]),
            (4, 4, 3),
        )

    def test_native_percentage_integer_math(self):
        from wakfu_server.combat_maximum_resource import effective_maximum

        self.assertEqual(effective_maximum(3, 50, 0, 2147483647), 4)
        self.assertEqual(effective_maximum(3, -50, 0, 2147483647), 2)
        self.assertEqual(effective_maximum(2147483647, 100, 0, 2147483647), 2147483646)
