import unittest
from types import SimpleNamespace
from copy import deepcopy
from wakfu_server.combat_event_costs import (
    LiveEventCostAuthority,
    source_cost_descriptor,
)
from wakfu_server.combat_cost_level_group import runtime_group_level
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server import native_catalog


class EventCostTests(unittest.TestCase):
    def setUp(self):
        # Source Ouginak6260 cost3AP, receiving listener belongs to anotherbreed.
        self.actor = SimpleNamespace(spell_ap_cost_modifiers={2: 2})
        self.preview = SimpleNamespace(actors={8: self.actor})
        self.context_calls = []

        def conditions(effect, invocation, plan):
            self.context_calls.append(
                (invocation.caster_id, invocation.target_id, plan)
            )
            return None  # installed6260 has no conditional cost criteria.

        self.authority = LiveEventCostAuthority(
            self.preview,
            actor_authority=lambda *a: SimpleNamespace(targeting={"is_eGj": True}),
            condition_context=conditions,
        )
        self.source = dict(
            runner_class="other",
            spell_context=dict(present=True, container_type=11, spell_id=6260, level=1),
        )
        self.inv = EffectInvocation(308144, 1, 8, 7, (0, 0, 0))

    def test_resolves_against_receiver_snapshot_without_source_ownership_or_paid_cost(
        self,
    ):
        before = deepcopy(self.source)
        out = self.authority(dict(effect_class=910), self.inv, self.source)
        self.assertEqual(out["spell_context"]["resolved_costs"], dict(ap=5, mp=0, wp=0))
        self.assertEqual(self.context_calls[0][0:2], (8, 7))
        self.assertEqual(self.source, before)
        self.actor.spell_ap_cost_modifiers = {2: -1}
        self.assertEqual(
            self.authority(dict(effect_class=910), self.inv, self.source)[
                "spell_context"
            ]["resolved_costs"]["ap"],
            2,
        )

    def test_912_keeps_paid_snapshot_and_does_not_resolve_live_spell_costs(self):
        paid = dict(runner_class="eWf", action_costs=dict(ap=1, mp=0, wp=0))
        self.assertEqual(self.authority(dict(effect_class=912), self.inv, paid), paid)
        self.assertEqual(self.context_calls, [])

    def test_state_container_is_not_a_source_spell_and_unknown_is_not_absence(self):
        for kind in (1, 3):  # fyW state and faV area, respectively.
            with self.subTest(container_type=kind):
                retention = SimpleNamespace(
                    plan={"spell_id": 6260, "evaluation_level": 1},
                    container=lambda inv: (
                        {"container_present": True, "container_type": kind},
                        123,
                    ),
                )
                descriptor = source_cost_descriptor(retention, self.inv)
                self.assertEqual(
                    descriptor["spell_context"], dict(present=True, container_type=kind)
                )
                self.assertEqual(
                    self.authority(dict(effect_class=910), self.inv, descriptor),
                    descriptor,
                )
                self.assertNotIn("spell_id", descriptor["spell_context"])
        self.assertEqual(self.context_calls, [])
        with self.assertRaises(ValueError):
            self.authority(dict(effect_class=910), self.inv, {"runner_class": "other"})

    def test_real_910_tree_receives_live_costs_in_runtime_callback(self):
        from dataclasses import replace
        import json
        from wakfu_server.paths import DATA_ROOT

        effect = json.loads(
            native_catalog.read_text(DATA_ROOT / "spell-effect-trees.json")
        )["effects"]["308144"]
        inv = replace(self.inv, native_trigger_context={"cost_source": self.source})
        self.assertEqual(
            runtime_group_level(effect, {}, inv, {}, cost_resolver=self.authority), 5
        )


class CostEmitterIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_combat_ordinary_damage_events import OrdinaryDamageEventsTests

        OrdinaryDamageEventsTests.setUpClass()

    def test_factory_emits_native_source_descriptor_without_freezing_receiver_costs(
        self,
    ):
        from test_combat_ordinary_damage_events import OrdinaryDamageEventsTests
        from unittest.mock import patch

        fixture = OrdinaryDamageEventsTests()
        fixture.setUp()
        seen = []
        with patch.object(
            type(fixture.dispatcher.replay_event),
            "__call__",
            lambda replay, source, **kwargs: seen.append(source.cost_source),
        ):
            fixture.dispatcher.execute(fixture.inv)
        self.assertEqual(len(seen), 8)
        for source in seen:
            self.assertEqual(source["runner_class"], "other")
            descriptor = source["spell_context"]
            self.assertTrue(descriptor["present"])
            self.assertEqual(descriptor["container_type"], 11)
            self.assertEqual((descriptor["spell_id"], descriptor["level"]), (6266, 1))
            self.assertNotIn("resolved_costs", descriptor)
