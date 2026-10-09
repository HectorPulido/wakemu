import unittest
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
