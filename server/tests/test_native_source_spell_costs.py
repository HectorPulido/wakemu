"""Retained native NPC fyG cost sources share listener cost semantics."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from wakfu_server.combat_conditions import ConditionContext, UnknownCondition
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_event_costs import LiveEventCostAuthority
from wakfu_server.combat_native_spell_casting import native_casting_table


class NativeSourceCostTests(unittest.TestCase):
    def authority(self, *, casting=None):
        self.actor = SimpleNamespace(spell_ap_cost_modifiers={2: 2})
        self.calls = []
        if casting is not None:
            patched = patch(
                "wakfu_server.combat_native_spell_casting.catalog", return_value=casting
            )
            patched.start()
            self.addCleanup(patched.stop)

        def context(effect, invocation, plan):
            self.calls.append((invocation.caster_id, invocation.target_id, plan))
            return ConditionContext({})

        return LiveEventCostAuthority(
            SimpleNamespace(actors={8: self.actor}),
            catalog={},
            actor_authority=lambda *_: SimpleNamespace(targeting={"is_eGj": True}),
            condition_context=context,
        )

    def source(self, *, reference=4066, level=128):
        return dict(
            runner_class="other",
            spell_context=dict(
                present=True, container_type=11, spell_id=reference, level=level
            ),
        )

    def execute(self, authority, source):
        return authority(
            dict(effect_class=910), EffectInvocation(111026, 1, 8, 7, (0, 0, 0)), source
        )

    def test_actual_npc4066_level128_uses_installed_one_ap_source(self):
        source = self.source()
        before = deepcopy(source)
        row, index = native_casting_table(4066, 128)
        self.assertEqual(tuple(row["costs"][index]), (1, 0, 0))
        result = self.execute(self.authority(), source)
        self.assertEqual(
            result["spell_context"]["resolved_costs"], dict(ap=1, mp=0, wp=0)
        )
        self.assertEqual(source, before)
        self.assertEqual(
            self.calls, [(8, 7, dict(spell_id=4066, evaluation_level=128))]
        )

    def test_native_conditional_costs_and_listener_modifiers_keep_all_currencies(self):
        row = dict(
            levels=[[0, 0, []]],
            costs=[[2, 1, 1]],
            categories=[2],
            conditional=[dict(criteria="True", levels=[[4, 2, 3]])],
        )
        result = self.execute(
            self.authority(casting={"4066": row}), self.source(level=1)
        )
        self.assertEqual(
            result["spell_context"]["resolved_costs"], dict(ap=6, mp=2, wp=3)
        )

    def test_missing_source_invalid_level_and_unknown_category_reject(self):
        for source in (
            self.source(reference=999999),
            self.source(level=0),
            self.source(level=246),
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.execute(self.authority(casting={}), source)
        row = dict(
            levels=[[0, 0, []]], costs=[[2, 0, 0]], categories=None, conditional=[]
        )
        with self.assertRaisesRegex(
            ValueError, "Missing native source spell category metadata"
        ):
            self.execute(self.authority(casting={"4066": row}), self.source(level=1))

    def test_non_spell_and_paid_snapshot_do_not_resolve_source(self):
        authority = self.authority(casting={})
        source = dict(
            runner_class="other", spell_context=dict(present=True, container_type=1)
        )
        self.assertEqual(self.execute(authority, source), source)
        paid = dict(runner_class="eWf", action_costs=dict(ap=1, mp=0, wp=0))
        self.assertEqual(
            authority(
                dict(effect_class=912),
                EffectInvocation(111026, 1, 8, 7, (0, 0, 0)),
                paid,
            ),
            paid,
        )
        self.assertEqual(self.calls, [])
