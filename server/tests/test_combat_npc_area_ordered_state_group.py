"""Immediate ordered state groups preserve zero-range NPC recipient casting."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_npc_area_groups import immediate_state_group
from wakfu_server.combat_npc_area_preflight import eligible_recipients, qualified_roots
from wakfu_server.combat_effect_dispatch import EffectInvocation


class OrderedStateAreaGroupTests(unittest.TestCase):
    def setUp(self):
        self.child = dict(
            effect_class=321,
            children=[],
            criteria="",
            native_target_selector={"class": "fcE", "mask": 2},
            area_class="anA",
            area_native="empty",
            application_flag="NONE",
            removal_flag="NONE",
        )
        self.root = dict(
            effect_class=330,
            parameter_count=1,
            parameters=[0.0, 0.0],
            children=[2],
            criteria="",
            native_target_selector={"class": "fcE", "mask": 129},
            area_class="anu",
            area_native="circle-5",
            application_flag="NONE",
            removal_flag="NONE",
        )
        self.effects = {"1": self.root, "2": self.child}

    def test_dispatcher_owned_immediate_group_qualifies(self):
        caster = SimpleNamespace(
            id=-1, controlled=False, hp=100, position=(0, 0, 0), direction=0
        )
        result = qualified_roots(
            SimpleNamespace(actors={-1: caster}),
            dict(actor_id=-1, target=(0, 0, 0)),
            dict(minimum=0, maximum=0, roots=[1]),
            self.effects,
        )
        self.assertEqual(result, {1: self.root})

    def test_state_children_with_conditions_remain_rejected(self):
        self.child["criteria"] = "IsInState(1)"
        self.assertIsNone(immediate_state_group(self.root, self.effects))

    def test_frozen_compiled_parameters_match_raw_catalog_parameters(self):
        self.root["parameters"] = (0.0, 0.0)
        self.assertIs(immediate_state_group(self.root, self.effects), self.child)

    def test_random_or_rebound_groups_remain_rejected(self):
        self.root["parameter_count"] = 6
        self.assertIsNone(immediate_state_group(self.root, self.effects))

    def test_missing_state_handler_definition_remains_rejected(self):
        del self.effects["2"]
        self.assertIsNone(immediate_state_group(self.root, self.effects))

    def test_internal_group_uses_actual_recipients_without_leaf_handler(self):
        invocation = EffectInvocation(1, 39, -1, -1, (0, 0, 0))
        selected = EffectInvocation(1, 39, -1, 7, (0, 0, 0))
        dispatcher = SimpleNamespace(
            effects=self.effects,
            handlers={321: object()},
            resolve=lambda *_: (selected,),
            condition_context=lambda *_: None,
        )
        fight = SimpleNamespace(actors={7: SimpleNamespace(id=7, hp=100)})
        with patch(
            "wakfu_server.combat_conditions.evaluate_condition", return_value=True
        ):
            self.assertEqual(
                eligible_recipients(dispatcher, self.root, invocation, fight), (7,)
            )
        dispatcher.handlers.clear()
        with self.assertRaisesRegex(ValueError, "state group authority"):
            eligible_recipients(dispatcher, self.root, invocation, fight)
