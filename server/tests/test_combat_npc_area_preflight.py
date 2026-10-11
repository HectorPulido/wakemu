"""NPC policy preserves native recipient selection and casting rejection gates."""
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_npc_area_preflight import (
    eligible_recipients,
    npc_cast_condition,
    qualified_roots,
)


class NpcAreaPreflightTests(unittest.TestCase):
    def setUp(self):
        self.caster = SimpleNamespace(
            id=-200,
            controlled=False,
            is_summon=False,
            hp=100,
            max_hp=100,
            position=(0, 0, 0),
            direction=0,
        )
        self.ally = SimpleNamespace(id=7, hp=60, max_hp=100)
        self.fight = SimpleNamespace(actors={-200: self.caster, 7: self.ally})
        self.request = dict(actor_id=-200, target=(0, 0, 0))
        self.rule = dict(minimum=0, maximum=0, roots=[64489])
        self.effect = dict(
            effect_class=258,
            native_target_selector={"class": "fcE", "mask": 129},
            children=[],
            area_class="anH",
            area_native="ring-1-2",
            criteria="",
            application_flag="NONE",
            removal_flag="NONE",
        )
        self.effects = {"64489": self.effect}
        self.invocation = EffectInvocation(64489, 4, -200, -200, (0, 0, 0))
        self.dispatcher = SimpleNamespace(
            resolve=lambda _effect, _invocation: [
                EffectInvocation(64489, 4, -200, 7, (0, 0, 0))
            ],
            handlers={258: SimpleNamespace()},
            condition_context=lambda _invocation: None,
        )

    def test_attested_other_ally_ring_qualifies(self):
        self.assertEqual(
            qualified_roots(self.fight, self.request, self.rule, self.effects),
            {64489: self.effect},
        )

    def test_ordinary_actor_has_no_summon_boolean_field(self):
        del self.caster.is_summon
        self.assertIsNotNone(
            qualified_roots(self.fight, self.request, self.rule, self.effects)
        )
        self.caster.native_summon_source = dict(profile_id=2617)
        self.assertIsNone(
            qualified_roots(self.fight, self.request, self.rule, self.effects)
        )

    def test_native_in_area_exclude_self_257_qualifies(self):
        self.effect["native_target_selector"]["mask"] = 257
        self.effect.update(area_class="anu", area_native="circle-2")
        self.assertEqual(
            qualified_roots(self.fight, self.request, self.rule, self.effects),
            {64489: self.effect},
        )

    def test_attested_global_population_selector_has_distinct_empty_geometry(self):
        for mask in (8, 140737488355584):
            self.effect["native_target_selector"]["mask"] = mask
            self.effect.update(area_class="anA", area_native="empty")
            self.assertIsNotNone(
                qualified_roots(self.fight, self.request, self.rule, self.effects)
            )
            self.effect["area_class"] = "anE"
            self.assertIsNone(
                qualified_roots(self.fight, self.request, self.rule, self.effects)
            )

    def test_enemy_ring_mask9_qualifies_without_changing_recipient_relation(self):
        self.effect["native_target_selector"]["mask"] = 9
        self.assertIsNotNone(
            qualified_roots(self.fight, self.request, self.rule, self.effects)
        )

    def test_real_native_selector_rejects_wrong_team_outside_area_and_untargetable(
        self,
    ):
        from wakfu_server.combat_effect_targets import select_native_effect_targets

        caster = SimpleNamespace(
            id=-200, team=1, position=(0, 0, 0), direction=0, physical_radius=0
        )
        actor = SimpleNamespace(id=7, team=0, position=(1, 0, 0), physical_radius=0)
        facts = dict(
            is_amO=True,
            bEe=True,
            is_Qq=False,
            is_eGj=True,
            UNTARGETTABLE_BY_OTHER=False,
            is_eHH=False,
        )
        contexts = {-200: dict(facts), 7: dict(facts)}
        for mask, accepted in ((129, False), (9, True), (257, True)):
            self.effect["native_target_selector"]["mask"] = mask
            selected = select_native_effect_targets(
                self.effect,
                caster,
                caster.position,
                (caster, actor),
                native_context=contexts,
            )
            self.assertEqual(bool(selected), accepted)
        self.effect["native_target_selector"]["mask"] = 9
        actor.position = (5, 0, 0)
        self.assertEqual(
            select_native_effect_targets(
                self.effect,
                caster,
                caster.position,
                (caster, actor),
                native_context=contexts,
            ),
            (),
        )
        actor.position = (1, 0, 0)
        contexts[7]["UNTARGETTABLE_BY_OTHER"] = True
        self.assertEqual(
            select_native_effect_targets(
                self.effect,
                caster,
                caster.position,
                (caster, actor),
                native_context=contexts,
            ),
            (),
        )

    def test_global_enemy_selector_rejects_allies_and_requires_actual_population(self):
        from wakfu_server.combat_effect_targets import select_native_effect_targets

        caster = SimpleNamespace(id=-200, team=1, position=(0, 0, 0))
        actor = SimpleNamespace(id=7, team=1, position=(100, 100, 0))
        facts = dict(is_amO=True, bEe=True, is_Qq=False, is_eGj=True, is_eHH=False)
        contexts = {-200: dict(facts), 7: dict(facts)}
        self.effect.update(
            area_class="anA",
            area_native="empty",
            native_target_selector={"class": "fcE", "mask": 8},
        )
        self.assertEqual(
            select_native_effect_targets(
                self.effect,
                caster,
                caster.position,
                (caster, actor),
                native_context=contexts,
            ),
            (),
        )
        actor.team = 0
        self.assertEqual(
            select_native_effect_targets(
                self.effect,
                caster,
                caster.position,
                (caster, actor),
                native_context=contexts,
            ),
            (actor,),
        )
        self.assertEqual(
            select_native_effect_targets(
                self.effect, caster, caster.position, (caster,), native_context=contexts
            ),
            (),
        )

    def test_false_native_state_condition_does_not_admit_recipient(self):
        self.effect["criteria"] = 'HasState(1579, "target")'
        with patch(
            "wakfu_server.combat_conditions.evaluate_condition", return_value=False
        ) as condition:
            self.assertEqual(
                eligible_recipients(
                    self.dispatcher, self.effect, self.invocation, self.fight
                ),
                (),
            )
        condition.assert_called_once_with(self.effect["criteria"], None)

    def test_player_summon_dead_or_withdrawn_caster_never_qualifies(self):
        for name, value in (
            ("controlled", True),
            ("is_summon", True),
            ("hp", 0),
            ("pve_withdrawn", True),
        ):
            with self.subTest(name=name):
                original = getattr(self.caster, name, None)
                setattr(self.caster, name, value)
                self.assertIsNone(
                    qualified_roots(self.fight, self.request, self.rule, self.effects)
                )
                setattr(self.caster, name, original)

    def test_nonzero_range_or_foreign_anchor_never_qualifies(self):
        for key in ("minimum", "maximum"):
            rule = dict(self.rule, **{key: 1})
            self.assertIsNone(
                qualified_roots(self.fight, self.request, rule, self.effects)
            )
        self.assertIsNone(
            qualified_roots(
                self.fight,
                dict(self.request, target=(1, 0, 0)),
                self.rule,
                self.effects,
            )
        )

    def test_unknown_or_other_selector_never_qualifies(self):
        for selector in (
            None,
            {},
            {"class": "other", "mask": 129},
            {"class": "fcE", "mask": 1},
            {"class": "fcE", "mask": 385},
        ):
            with self.subTest(selector=selector):
                self.effect["native_target_selector"] = selector
                self.assertIsNone(
                    qualified_roots(self.fight, self.request, self.rule, self.effects)
                )

    def test_children_subscriptions_and_missing_roots_never_qualify(self):
        for key, value in (
            ("children", [12]),
            ("application_flag", "ON_TURN_START"),
            ("removal_flag", "ON_TURN_END"),
        ):
            original = self.effect[key]
            self.effect[key] = value
            self.assertIsNone(
                qualified_roots(self.fight, self.request, self.rule, self.effects)
            )
            self.effect[key] = original
        self.assertIsNone(
            qualified_roots(
                self.fight, self.request, dict(self.rule, roots=[999]), self.effects
            )
        )

    def test_unknown_geometry_rejects_instead_of_radius_guess(self):
        self.effect["area_class"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            qualified_roots(self.fight, self.request, self.rule, self.effects)

    def test_actual_wounded_recipient_is_selected_without_healing(self):
        self.assertEqual(
            eligible_recipients(
                self.dispatcher, self.effect, self.invocation, self.fight
            ),
            (7,),
        )
        self.assertEqual(self.ally.hp, 60)

    def test_full_health_dead_withdrawn_and_missing_recipients_rejected(self):
        for change in (dict(hp=100), dict(hp=0), dict(pve_withdrawn=True)):
            with self.subTest(change=change):
                ally = SimpleNamespace(id=7, hp=60, max_hp=100)
                ally.__dict__.update(change)
                fight = SimpleNamespace(actors={-200: self.caster, 7: ally})
                self.assertEqual(
                    eligible_recipients(
                        self.dispatcher, self.effect, self.invocation, fight
                    ),
                    (),
                )
        self.assertEqual(
            eligible_recipients(
                self.dispatcher,
                self.effect,
                self.invocation,
                SimpleNamespace(actors={}),
            ),
            (),
        )

    def test_shared_resolver_rejects_enemy_outside_area_and_untargetable(self):
        self.dispatcher.resolve = lambda *_: []
        self.assertEqual(
            eligible_recipients(
                self.dispatcher, self.effect, self.invocation, self.fight
            ),
            (),
        )

    def test_actual_native_handler_eligibility_is_preserved(self):
        self.dispatcher.handlers[258].native_eligibility = lambda *_: False
        self.assertEqual(
            eligible_recipients(
                self.dispatcher, self.effect, self.invocation, self.fight
            ),
            (),
        )

    def test_unknown_condition_and_missing_handler_stay_mandatory_failures(self):
        from wakfu_server.combat_conditions import UnknownCondition

        with patch(
            "wakfu_server.combat_conditions.evaluate_condition",
            side_effect=UnknownCondition("unknown"),
        ):
            with self.assertRaises(UnknownCondition):
                eligible_recipients(
                    self.dispatcher, self.effect, self.invocation, self.fight
                )
        self.dispatcher.handlers.clear()
        with self.assertRaisesRegex(ValueError, "mandatory NPC area handler"):
            eligible_recipients(
                self.dispatcher, self.effect, self.invocation, self.fight
            )

    def test_self_is_never_promoted_to_recipient(self):
        self.dispatcher.resolve = lambda *_: [self.invocation]
        self.assertEqual(
            eligible_recipients(
                self.dispatcher, self.effect, self.invocation, self.fight
            ),
            (),
        )

    def test_disabled_policy_returns_original_context(self):
        context = SimpleNamespace(native_casting_query=Mock())
        adapter = SimpleNamespace(cast_condition=lambda *_: context)
        self.assertIs(
            npc_cast_condition(
                adapter, self.fight, self.request, factory=Mock(), enabled=False
            ),
            context,
        )

    def test_native_rejections_other_than_anchor_selector_are_preserved(self):
        @dataclass
        class Conditions:
            native_casting_query: object

        for reason in ("twI", "twG", "twV", "twH", "twY", "twD"):
            with self.subTest(reason=reason):
                decision = dict(result=reason, aligned=True)
                adapter = SimpleNamespace(
                    cast_condition=lambda *_: Conditions(lambda *_: decision)
                )
                factory = Mock()
                context = npc_cast_condition(
                    adapter, self.fight, self.request, factory=factory, enabled=True
                )
                self.assertIs(
                    context.native_casting_query(self.rule, 2794, 4), decision
                )
                factory.assert_not_called()

    def test_shared_resource_gate_still_precedes_npc_area_query(self):
        from wakfu_server.combat_cast import _validate_target

        context = SimpleNamespace(native_casting_query=Mock(), actors={})
        self.caster.ap, self.caster.mp = 2, 3
        with patch("wakfu_server.combat_ap_property_cost.require_native_ap_cost"):
            with self.assertRaisesRegex(
                ValueError, "Insufficient authoritative spell resources"
            ):
                _validate_target(
                    self.request,
                    self.caster,
                    self.fight,
                    3,
                    dict(ap=3, mp=0, wp=0),
                    self.rule,
                    [64489],
                    4,
                    Mock(),
                    2794,
                    context,
                )
        context.native_casting_query.assert_not_called()

    def test_shared_usage_gate_still_rejects_after_area_query(self):
        from wakfu_server.combat_cast import _validate_target

        context = SimpleNamespace(
            native_casting_query=Mock(
                return_value=dict(result="twD", aligned=True, target_id=-200)
            ),
            actors={},
        )
        self.caster.ap, self.caster.mp = 6, 3
        with patch(
            "wakfu_server.combat_ap_property_cost.require_native_ap_cost"
        ), patch(
            "wakfu_server.combat_spell_resource_costs.extra_costs", return_value={}
        ), patch(
            "wakfu_server.combat_spell_resource_costs.validate_extra_resources"
        ), patch(
            "wakfu_server.combat_spell_usage.validate_usage",
            side_effect=ValueError("Native cooldown rejected"),
        ):
            with self.assertRaisesRegex(ValueError, "Native cooldown rejected"):
                _validate_target(
                    self.request,
                    self.caster,
                    self.fight,
                    3,
                    dict(ap=3, mp=0, wp=0),
                    self.rule,
                    [64489],
                    4,
                    Mock(),
                    2794,
                    context,
                )
        context.native_casting_query.assert_called_once()
        self.assertEqual(self.caster.ap, 6)

    def test_alignment_rejection_never_enters_area_policy(self):
        @dataclass
        class Conditions:
            native_casting_query: object

        decision = dict(result="twE", aligned=False)
        adapter = SimpleNamespace(
            cast_condition=lambda *_: Conditions(lambda *_: decision)
        )
        factory = Mock()
        context = npc_cast_condition(
            adapter, self.fight, self.request, factory=factory, enabled=True
        )
        self.assertIs(context.native_casting_query(self.rule, 2794, 4), decision)
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
