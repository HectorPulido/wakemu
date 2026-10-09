import unittest
from types import SimpleNamespace
import test_combat_maximum_resource as fixture
from wakfu_server.combat_maximum_resource import NativePercentageHPHandler
from wakfu_server.combat_stat_handler import NativeStatHandler


class PercentageHPTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.MaximumResourceTests()
        self.f.setUp()
        a = self.f.actor
        a.max_hp = 100
        a.hp = 60
        a.effect_stats[1] = 60
        a.effect_maxima[1] = 100
        a.effect_base_maxima[1] = 100
        a.effect_minima[1] = 0
        a.effect_base_minima[1] = 0
        a.effect_percentages[1] = 0
        self.handler = NativePercentageHPHandler(
            self.f.fight,
            self.f.packets,
            action_id=1,
            allocate_uid=self.f.handler.allocate_uid,
            context=self.f.handler.context,
        )

    def apply(self, parameters=None):
        return self.handler(
            dict(
                effect_class=986,
                parameters=[-30.0, 0.0] if parameters is None else parameters,
            ),
            {},
            self.f.invocation,
        )

    def remove(self):
        NativeStatHandler(
            self.f.fight,
            self.f.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        ).remove(101)

    def test_native_sacrier353198_hp_and_default_no_restore(self):
        self.apply()
        a = self.f.actor
        self.assertEqual((a.hp, a.max_hp, a.effect_percentages[1]), (30, 70, -30))
        self.remove()
        self.assertEqual((a.hp, a.max_hp, a.effect_percentages[1]), (30, 100, 0))

    def test_leaves_one_when_loss_exceeds_hp(self):
        a = self.f.actor
        a.hp = 20
        a.effect_stats[1] = 20
        self.apply()
        self.assertEqual(a.hp, 1)

    def test_equal_loss_can_kill_and_is_recorded(self):
        a = self.f.actor
        a.hp = 30
        a.effect_stats[1] = 30
        with self.f.fight.effect_resolution():
            self.apply()
        self.assertEqual(a.hp, 0)
        self.assertTrue(any(e["kind"] == "death" for e in self.f.fight.events))

    def test_registered_percentage_death_delivers_original_runner_before_settlement(
        self,
    ):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            global_fighter_guards,
        )
        from wakfu_server.combat_ordinary_death import registered_ordinary_death

        actor = self.f.actor
        actor.hp = actor.effect_stats[1] = 30
        initialize_global_pv_collections(self.f.fight, tuple(self.f.fight.actors))
        observed = []

        def death(identity, **source):
            self.assertEqual(identity, actor.id)
            self.assertTrue(registered_ordinary_death(self.f.fight, actor))
            self.assertEqual(
                global_fighter_guards(self.f.fight, identity),
                dict(baF=False, baG=True, baK=False),
            )
            self.assertEqual(self.f.fight.phase, "active")
            self.assertIs(source["invocation"], self.f.invocation)
            self.assertEqual(
                (source["effect"]["effect_class"], source["uid"], source["value"]),
                (986, 101, -30),
            )
            observed.append(identity)

        self.handler.event_lifecycle = SimpleNamespace(death=death)
        self.apply()
        self.assertEqual(observed, [actor.id])

    def test_equal_loss_registers_owned_off_play_and_distinct_corpse_source(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            global_fighter_guards,
        )
        from wakfu_server.combat_ordinary_death import registered_ordinary_death

        fight = self.f.fight
        initialize_global_pv_collections(fight, tuple(fight.actors))
        actor = self.f.actor
        actor.hp = actor.effect_stats[1] = 30
        with fight.effect_resolution():
            self.apply()
        self.assertEqual(
            global_fighter_guards(fight, actor.id), dict(baF=False, baG=True, baK=False)
        )
        self.assertTrue(registered_ordinary_death(fight, actor))
        death = next(
            i
            for i, event in enumerate(fight.events)
            if event["kind"] == "death" and event["actor_id"] == actor.id
        )
        self.assertEqual(fight.events[death - 1]["kind"], "percentage_hp_update")
        self.assertEqual(fight.events[death - 1]["effect_class"], 986)

    def test_current_flags_and_native_removal_uses_new_maximum_delta(self):
        a = self.f.actor
        a.hp = 80
        a.effect_stats[1] = 80
        self.apply([-30.0, 0.0, 1.0, 0.0, 1.0, 0.0])
        self.assertEqual(a.hp, 50)
        self.remove()
        self.assertEqual((a.hp, a.max_hp), (20, 100))
