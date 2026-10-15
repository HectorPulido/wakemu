"""Focused guard coverage for NPC zero-range casts selecting real area PVs."""

import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_npc_area_preflight import (
    eligible_area_recipients,
    npc_cast_condition,
    qualified_area_roots,
)


class NpcAreaOnlyPreflightTests(unittest.TestCase):
    def setUp(self):
        self.caster = SimpleNamespace(
            id=-200,
            controlled=False,
            hp=100,
            position=(0, 0, 0),
            direction=0,
            is_summon=False,
        )
        self.fight = SimpleNamespace(
            actors={-200: self.caster},
            native_effect_areas={
                901: {"uid": 901, "reference": 1977, "native_area_contract": "faY"}
            },
        )
        self.request = {"actor_id": -200, "target": (0, 0, 0)}
        self.effect = {
            "effect_class": 330,
            "parameter_count": 0,
            "parameters": [],
            "children": [392622, 392984, 392621],
            "native_target_selector": {"class": "fcE", "mask": (1 << 51) | 64},
            "area_class": "anD",
            "area_native": "point",
            "application_flag": "NONE",
            "removal_flag": "NONE",
            "target_masks": [None] * 7,
            "criteria": "IsSpecificArea(1977)",
        }
        self.rule = {"minimum": 0, "maximum": 0, "roots": [392568]}
        self.effects = {"392568": self.effect}
        self.invocation = EffectInvocation(392568, 10, -200, -200, (0, 0, 0))

    def test_qualified_root_requires_exact_immediate_point_area_contract(self):
        self.assertEqual(
            qualified_area_roots(self.fight, self.request, self.rule, self.effects),
            {392568: self.effect},
        )
        self.effect["native_target_selector"] = {"class": "fcE", "mask": 64}
        self.assertEqual(
            qualified_area_roots(self.fight, self.request, self.rule, self.effects),
            {392568: self.effect},
        )
        self.effect["native_target_selector"] = {
            "class": "fcE",
            "mask": (1 << 51) | 64,
        }
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        compiled_effects = ImmutableCatalog({"392568": self.effect})
        self.assertIsInstance(compiled_effects["392568"]["parameters"], tuple)
        self.assertEqual(
            qualified_area_roots(self.fight, self.request, self.rule, compiled_effects),
            {392568: compiled_effects["392568"]},
        )
        for change in (
            {"minimum": 1},
            {"maximum": 1},
        ):
            with self.subTest(change=change):
                self.assertIsNone(
                    qualified_area_roots(
                        self.fight,
                        self.request,
                        dict(self.rule, **change),
                        self.effects,
                    )
                )
        self.caster.native_summon_source = {"profile_id": 2617}
        self.assertIsNone(
            qualified_area_roots(self.fight, self.request, self.rule, self.effects)
        )
        del self.caster.native_summon_source
        for change in (
            {"effect_class": 258},
            {"area_native": "empty"},
            {"area_class": "anA"},
            {"application_flag": "ON_TURN_START"},
            {"target_masks": [None] * 6},
        ):
            with self.subTest(change=change):
                self.effect.update(change)
                self.assertIsNone(
                    qualified_area_roots(
                        self.fight, self.request, self.rule, self.effects
                    )
                )
                self.effect.update(
                    effect_class=330,
                    area_native="point",
                    area_class="anD",
                    native_target_selector={"class": "fcE", "mask": (1 << 51) | 64},
                    application_flag="NONE",
                )

    def test_only_registered_area_recipient_with_true_criteria_is_eligible(self):
        selected = EffectInvocation(392568, 10, -200, 901, (0, 0, 0))
        dispatcher = SimpleNamespace(
            resolve=lambda *_: (selected,), condition_context=lambda _: object()
        )
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            side_effect=lambda fight, uid: (
                object()
                if uid == 901 and fight.native_effect_areas[uid]["reference"] == 1977
                else None
            ),
        ), patch(
            "wakfu_server.combat_conditions.evaluate_condition", return_value=True
        ):
            self.assertEqual(
                eligible_area_recipients(
                    dispatcher, self.effect, self.invocation, self.fight
                ),
                (901,),
            )

    def test_missing_unregistered_fighter_and_failed_criteria_are_rejected(self):
        dispatcher = SimpleNamespace(
            resolve=lambda *_: (EffectInvocation(392568, 10, -200, 999, (0, 0, 0)),),
            condition_context=lambda _: None,
        )
        self.assertEqual(
            eligible_area_recipients(
                dispatcher, self.effect, self.invocation, self.fight
            ),
            (),
        )

        dispatcher.resolve = lambda *_: (
            EffectInvocation(392568, 10, -200, -200, (0, 0, 0)),
        )
        self.assertEqual(
            eligible_area_recipients(
                dispatcher, self.effect, self.invocation, self.fight
            ),
            (),
        )

        dispatcher.resolve = lambda *_: (
            EffectInvocation(392568, 10, -200, 901, (0, 0, 0)),
        )
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv", return_value=None
        ):
            self.assertEqual(
                eligible_area_recipients(
                    dispatcher, self.effect, self.invocation, self.fight
                ),
                (),
            )
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            side_effect=lambda fight, uid: (
                object()
                if uid == 901 and fight.native_effect_areas[uid]["reference"] == 1977
                else None
            ),
        ), patch(
            "wakfu_server.combat_conditions.evaluate_condition", return_value=False
        ):
            self.assertEqual(
                eligible_area_recipients(
                    dispatcher, self.effect, self.invocation, self.fight
                ),
                (),
            )

    def test_unqualified_root_preserves_original_twE_result_and_cost_rule(self):
        @dataclass
        class Conditions:
            native_casting_query: object

        original = {"result": "twE", "aligned": True, "costs": [[3, 0, 0]]}
        adapter = SimpleNamespace(
            cast_condition=lambda *_: Conditions(lambda *_: original)
        )
        factory = SimpleNamespace(
            effects={"392568": {**self.effect, "area_native": "unknown"}}
        )
        wrapped = npc_cast_condition(
            adapter, self.fight, self.request, factory=factory, enabled=True
        )
        self.assertIs(wrapped.native_casting_query(self.rule, 5776, 10), original)
        self.assertEqual(self.rule["minimum"], 0)
        self.assertEqual(self.rule["maximum"], 0)
        self.assertEqual(original["costs"], [[3, 0, 0]])
        self.assertEqual(tuple(self.request["target"]), self.caster.position)


if __name__ == "__main__":
    unittest.main()
