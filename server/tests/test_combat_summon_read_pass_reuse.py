"""Focused candidate regression: reuse only the certified count roster view."""
import unittest
from copy import deepcopy
from unittest.mock import patch

from test_combat_ordinary_population_read_pass import OrdinaryPopulationReadPassTests
from wakfu_server import combat_ordinary_events as events_module
from wakfu_server.combat_global_pv_collections import register_global_fighter
from wakfu_server.combat_native_death_status import initialize_fresh_bje_death_status
from wakfu_server.combat_summon_count import registered_summon_counts


class SummonReadPassReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OrdinaryPopulationReadPassTests.setUpClass()

    def setUp(self):
        OrdinaryPopulationReadPassTests.setUp(self)
        fight = self.case.fight
        actor = deepcopy(fight.actors[-7])
        actor.id = -8
        actor.native_controller_id = 7
        actor.native_master_id = 7
        actor.is_summon = True
        actor.native_world_property_counts = {}
        actor.native_world_properties = frozenset()
        actor.native_fight_property_counts = {}
        actor.native_fight_properties = frozenset()
        if hasattr(actor, "native_death_status"):
            del actor.native_death_status
        initialize_fresh_bje_death_status(actor)
        fight.actors[-8] = actor
        register_global_fighter(fight, -8)
        # Only the real GF count branch consumes this registration. The test
        # never requests active spell/target authority for the added summon.
        fight.native_summon_registrations = {
            -8: dict(
                actor_id=-8,
                controller_id=7,
                authority=dict(
                    targeting={"is_eGj": True, "dTE": True},
                    breed_id=5525,
                ),
            )
        }

    def test_count_reuses_phase_roster_but_rechecks_live_summon_facts(self):
        fight = self.case.fight
        views = []

        def observed(*args):
            views.append(args[-1])
            return registered_summon_counts(*args)

        with events_module._phase_read_pass(self.case.events, self.case.inv):
            with patch(
                "wakfu_server.combat_summon_count.registered_summon_counts",
                side_effect=observed,
            ):
                first = self.wrapper(fight, fight.actors[7])
                second = self.wrapper(fight, fight.actors[7])
                self.assertEqual(first.summon_count, 1)
                self.assertEqual(second.summon_count, 1)
                self.assertIs(views[0], views[1])
                # Changing HP does not manufacture native death or hide a summon.
                fight.actors[-8].hp = 0
                self.assertEqual(self.wrapper(fight, fight.actors[7]).summon_count, 1)
                # Controller and property facts are still read on every query.
                fight.actors[-8].native_controller_id = -7
                self.assertFalse(
                    self.wrapper(fight, fight.actors[7]).native_summon_counts_complete
                )
                fight.actors[-8].native_controller_id = 7
                fight.actors[-8].native_fight_properties = frozenset({103})
                self.assertEqual(self.wrapper(fight, fight.actors[7]).summon_count, 0)
                with self.case.events.replay._callback_read_boundary():
                    fight.actors[-8].native_fight_properties = frozenset()
                self.assertEqual(self.wrapper(fight, fight.actors[7]).summon_count, 1)
                self.assertIsNot(views[-1], views[0])

    def test_custom_provider_without_count_projection_keeps_fallback(self):
        ordinary = self.ordinary

        class Custom:
            catalog = ordinary.catalog

            def __call__(self, preview, actor):
                return ordinary(preview, actor)

        self.wrapper.ordinary = Custom()
        views = []

        def observed(*args):
            views.append(args[-1])
            return registered_summon_counts(*args)

        with patch(
            "wakfu_server.combat_summon_count.registered_summon_counts",
            side_effect=observed,
        ):
            for _ in range(2):
                self.assertEqual(
                    self.wrapper(
                        self.case.fight, self.case.fight.actors[7]
                    ).summon_count,
                    1,
                )
        self.assertIsNot(views[0], views[1])
