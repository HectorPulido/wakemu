import unittest
from contextlib import ExitStack
from dataclasses import replace
from types import SimpleNamespace
from wakfu_server.combat_spell_level import NativeSpellBook
from wakfu_server.combat_triggered_spell import (
    NativeTriggeredSpellRequest,
    triggered_spell_plan,
    consume_triggered_costs,
    triggered_spell_scope,
    InternalTriggeredAbility,
    triggered_spell_level,
)


class TriggeredSpellPolicyTests(unittest.TestCase):
    def fixture(self, consumes):
        actor = SimpleNamespace(
            id=7,
            ap=6,
            mp=3,
            effect_stats={2: 6, 3: 3, 4: 6},
            spell_ap_cost_modifiers={},
        )
        authority = SimpleNamespace(native_spellbook=NativeSpellBook({123: 17}, False))
        request = NativeTriggeredSpellRequest(123, 7, (1, 0, 0), consumes)
        return actor, authority, request

    def test_actual_book_level_and_flag_bind_all_three_resource_costs(self):
        for consumes, expected in ((False, (6, 3, 6)), (True, (4, 2, 3))):
            with self.subTest(consumes=consumes):
                actor, authority, request = self.fixture(consumes)
                seen = []

                def definition(reference, level, conditions, modifiers, **kwargs):
                    seen.append((reference, level, kwargs["calculate_costs"]))
                    return dict(costs=dict(ap=2, mp=1, wp=3), roots=(44, 55))

                plan = triggered_spell_plan(
                    request,
                    actor=actor,
                    authority=authority,
                    condition=None,
                    definition=definition,
                )
                consume_triggered_costs(actor, plan)
                self.assertEqual((actor.ap, actor.mp, actor.effect_stats[4]), expected)
                self.assertEqual(seen, [(123, 17, consumes)])
                self.assertEqual(plan["effect_ids"], (44, 55))

    def test_internal_spell_without_owned_descriptor_is_not_parent_level(self):
        actor, authority, request = self.fixture(True)
        authority.native_spellbook = NativeSpellBook({}, False)
        with self.assertRaisesRegex(ValueError, "owned level descriptor"):
            triggered_spell_plan(
                request,
                actor=actor,
                authority=authority,
                condition=None,
                definition=lambda *a, **k: None,
            )
        self.assertEqual(actor.effect_stats, {2: 6, 3: 3, 4: 6})

    def test_insufficient_resources_rejects_before_any_payment(self):
        actor, authority, request = self.fixture(True)
        actor.effect_stats[4] = 2
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            triggered_spell_plan(
                request,
                actor=actor,
                authority=authority,
                condition=None,
                definition=lambda *a, **k: dict(
                    costs=dict(ap=2, mp=1, wp=3), roots=(44,)
                ),
            )
        self.assertEqual((actor.ap, actor.mp, actor.effect_stats[4]), (6, 3, 2))

    def test_internal_descriptor_uses_actual_caster_level_capped_by_native_maximum(
        self,
    ):
        _, authority, request = self.fixture(False)
        authority.native_spellbook = NativeSpellBook({}, False)
        authority.native_real_level = 200
        descriptor = InternalTriggeredAbility(44, 123, 100)
        self.assertEqual(triggered_spell_level(request, authority, descriptor), 100)
        authority.native_real_level = 17
        self.assertEqual(triggered_spell_level(request, authority, descriptor), 17)
        with self.assertRaisesRegex(ValueError, "differs from request"):
            triggered_spell_level(
                request, authority, InternalTriggeredAbility(44, 124, 100)
            )
        authority.native_real_level = None
        with self.assertRaisesRegex(ValueError, "caster level"):
            triggered_spell_level(request, authority, descriptor)

    def test_recursion_policy_rejects_cycle_and_restores_scope_after_failure(self):
        _, _, request = self.fixture(False)
        with triggered_spell_scope(request):
            with self.assertRaisesRegex(ValueError, "cycle/depth"):
                with triggered_spell_scope(request):
                    pass
        with triggered_spell_scope(request):
            pass

    def test_same_spell_other_caster_is_distinct_but_indirect_cycle_is_rejected(self):
        _, _, request = self.fixture(False)
        other_caster = replace(request, caster_id=8)
        with triggered_spell_scope(request), triggered_spell_scope(other_caster):
            with self.assertRaisesRegex(ValueError, "cycle/depth"):
                with triggered_spell_scope(request):
                    self.fail("An active caster/spell cycle was admitted")
        with triggered_spell_scope(other_caster):
            pass

    def test_native_target_cell_distinguishes_chain_but_repeat_still_rejects(self):
        request = NativeTriggeredSpellRequest(6462, -100007, (31, -25, 0), False)
        next_target = replace(request, cell=(30, -24, 0))
        with triggered_spell_scope(request), triggered_spell_scope(next_target):
            # Changing who pays cannot turn the same active native target into
            # a distinct cast, even after another target has been processed.
            with self.assertRaisesRegex(ValueError, "cycle/depth"):
                with triggered_spell_scope(replace(request, native_rhe=True)):
                    self.fail("The same active native spell target recurred")
        with triggered_spell_scope(request):
            pass

    def test_distinct_requests_keep_depth_limit_and_release_every_scope(self):
        _, _, request = self.fixture(False)
        with ExitStack() as scopes:
            for offset in range(32):
                scopes.enter_context(
                    triggered_spell_scope(replace(request, spell_id=123 + offset))
                )
            with self.assertRaisesRegex(ValueError, "cycle/depth"):
                with triggered_spell_scope(replace(request, spell_id=155)):
                    self.fail("The unchanged depth budget was exceeded")
        with triggered_spell_scope(request):
            pass
