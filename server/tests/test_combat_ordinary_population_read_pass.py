"""Common roster reuse ends at every existing native callback boundary."""
import unittest
from copy import copy

import test_combat_ordinary_events as fixture
from wakfu_server import combat_ordinary_events as events_module
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_summon import RegisteredSummonAuthority


class OrdinaryPopulationReadPassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.OrdinaryHealingEventTests.setUpClass()

    def setUp(self):
        self.case = fixture.OrdinaryHealingEventTests()
        self.case.setUp()
        self.ordinary = self.case.adapter.actor_authority
        self.wrapper = RegisteredSummonAuthority(self.ordinary)
        self.case.adapter.actor_authority = self.wrapper
        initialize_global_pv_collections(self.case.fight, tuple(self.case.fight.actors))

    def view(self):
        return self.wrapper._ordinary_view(
            self.case.fight, _pure_callback=self.ordinary
        )

    def test_adjacent_roster_reads_reuse_then_callback_revalidates_source(self):
        case = self.case
        with events_module._phase_read_pass(case.events, case.inv):
            view = self.view()
            population = self.ordinary._creation_population(view)
            for _ in range(20):
                self.assertIs(self.view(), view)
                self.assertIs(self.ordinary._creation_population(view), population)
            self.assertEqual(list(view.actors), list(case.fight.actors))
            with case.events.replay._callback_read_boundary():
                self.ordinary.monsters[-99] = dict(id=-99, ref=5525)
            fresh = self.view()
            self.assertIsNot(fresh, view)
            with self.assertRaisesRegex(ValueError, "roster changed"):
                self.ordinary._creation_population(fresh)
            with case.events.replay._callback_read_boundary():
                del self.ordinary.monsters[-99]
            self.assertIsNot(
                self.ordinary._creation_population(self.view()), population
            )
        self.assertIsNone(events_module._ordinary_phase_facts(case.fight))

    def test_custom_callback_keeps_private_roster_and_invalidates_common_facts(self):
        case = self.case
        with events_module._phase_read_pass(case.events, case.inv):
            before = self.view()
            self.ordinary._creation_population(before)

            def custom(view):
                self.assertIsNone(events_module._ordinary_phase_facts(case.fight))
                view.actors.clear()

            self.wrapper._call_ordinary(case.fight, custom)
            self.assertEqual(set(case.fight.actors), {7, -7})
            self.assertIsNot(self.view(), before)
            self.assertEqual(set(self.view().actors), {7, -7})

    def test_rebound_retention_fight_adapter_and_foreign_provider_do_not_reuse_facts(
        self,
    ):
        case = self.case
        for changed in ("retention", "fight", "adapter"):
            with self.subTest(changed=changed):
                with events_module._phase_read_pass(case.events, case.inv):
                    prior = self.view()
                    self.ordinary._creation_population(prior)
                    original_retention = case.events.replay.retention
                    original_adapter = case.events.adapter
                    try:
                        if changed == "retention":
                            case.events.replay.retention = copy(original_retention)
                        elif changed == "fight":
                            original_retention.fight = copy(case.fight)
                        else:
                            case.events.adapter = copy(original_adapter)
                        self.assertIsNone(
                            events_module._ordinary_phase_facts(case.fight)
                        )
                        self.assertIsNone(events_module._ordinary_phase_facts(prior))
                    finally:
                        case.events.replay.retention = original_retention
                        original_retention.fight = case.fight
                        case.events.adapter = original_adapter
                    self.assertIsNot(self.view(), prior)
        with events_module._phase_read_pass(case.events, case.inv):
            self.view()
            self.assertIsNone(
                events_module._ordinary_phase_facts(
                    case.fight, authority=copy(self.ordinary)
                )
            )
