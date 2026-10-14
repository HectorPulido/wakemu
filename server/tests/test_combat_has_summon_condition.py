"""Native eIF uses owned captured descriptors, never active summon counts."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.combat_captured_roster_condition import has_captured_summon
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class HasSummonConditionTests(unittest.TestCase):
    def test_any_tenth_slot_descriptor_counts_even_unselected_and_unavailable(self):
        roster = OwnedCapturedRoster(
            7, (None,) * 9 + (CapturedCreature(9, 5347, ""),), (False,) * 10, 0
        )
        self.assertTrue(
            has_captured_summon(
                SimpleNamespace(native_is_ehp=True, native_captured_roster=roster)
            )
        )
        self.assertIsNone(roster.selected_creature)
        self.assertFalse(any(roster.available))

    def test_known_npc_null_empty_and_missing_component_have_distinct_authority(self):
        self.assertFalse(has_captured_summon(None))
        self.assertFalse(has_captured_summon(SimpleNamespace(native_is_ehp=False)))
        self.assertFalse(
            has_captured_summon(
                SimpleNamespace(
                    native_is_ehp=True, native_captured_roster=OwnedCapturedRoster(7)
                )
            )
        )
        for typed in (None, True):
            with self.assertRaises(ValueError):
                has_captured_summon(
                    SimpleNamespace(native_is_ehp=typed, native_captured_roster=None)
                )

    def test_native_optional_selector_trims_target_and_other_strings_select_caster(
        self,
    ):
        seen = []
        context = ConditionContext(
            {},
            has_summon_query=lambda selector: seen.append(selector)
            or selector == "target",
        )
        self.assertFalse(evaluate_condition("HasSummon()", context))
        self.assertTrue(evaluate_condition('HasSummon(" TARGET ")', context))
        self.assertFalse(evaluate_condition('HasSummon("unrecognized")', context))
        self.assertEqual(seen, ["caster", "target", "caster"])
        self.assertTrue(evaluate_condition("not HasSummon()", context))

    def test_bad_signatures_and_missing_context_fail_closed(self):
        for expression in (
            "HasSummon(1)",
            'HasSummon("target", "caster")',
            "HasSummon()",
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition(expression, ConditionContext({}))


class HasSummonAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_combat_runtime_adapter as fixture_module

        fixture_module.ServerAdapterTests.setUpClass()

    def test_real_adapter_reads_selected_owned_component_not_active_summon_count(self):
        import test_combat_runtime_adapter as fixture_module
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        fixture = fixture_module.ServerAdapterTests()
        fixture.setUp()
        original = fixture.adapter.actor_authority
        occupied = OwnedCapturedRoster(
            7, (CapturedCreature(0, 5347, ""),) + (None,) * 9, (False,) * 10
        )

        def authority(preview, actor):
            metadata = original(preview, actor)
            return replace(
                metadata,
                targeting=dict(metadata.targeting, is_eGj=True),
                native_is_ehp=actor.id == 7,
                native_captured_roster=occupied if actor.id == 7 else None,
                summon_count=0,
            )

        fixture.adapter.actor_authority = authority
        context = fixture.adapter.condition(
            fixture.preview,
            {},
            None,
            EffectInvocation(326382, 200, 7, -7, fixture.preview.actors[-7].position),
        )
        self.assertTrue(evaluate_condition("HasSummon()", context))
        self.assertFalse(evaluate_condition('HasSummon("target")', context))
        self.assertTrue(evaluate_condition('not HasSummon("target")', context))


class HasSummonFactoryTypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_combat_ordinary_authority as fixture_module

        fixture_module.OrdinaryAuthorityTests.setUpClass()

    def fixture(self):
        import test_combat_ordinary_authority as fixture_module

        fixture = fixture_module.OrdinaryAuthorityTests()
        fixture.setUp()
        return fixture

    def test_actual_ordinary_npc_factory_attests_non_ehp_and_preserves_pc_unknown_roster(
        self,
    ):
        fixture = self.fixture()
        npc = fixture.authority(fixture.preview, fixture.preview.actors[-7])
        player = fixture.authority(fixture.preview, fixture.preview.actors[7])
        self.assertIs(npc.native_is_ehp, False)
        self.assertFalse(has_captured_summon(npc))
        self.assertIs(player.native_is_ehp, True)
        with self.assertRaisesRegex(ValueError, "owned eHU"):
            has_captured_summon(player)

    def test_actual_detached_bje_factory_type_flows_through_owned_construction_scope(
        self,
    ):
        from wakfu_server.combat_summon_creation import native_fresh_summon_authority
        from wakfu_server.combat_summon_initialization import detached_summon_scope

        fixture = self.fixture()
        actor = fixture.preview.actors.pop(-7)
        actor.team = -1
        authority = native_fresh_summon_authority(actor, 5525)
        self.assertIs(authority.native_is_ehp, False)
        original_roster = dict(fixture.preview.actors)
        with detached_summon_scope(fixture.preview, actor, authority):
            actual = fixture.authority(fixture.preview, actor)
            self.assertIs(actual, authority)
            context = ConditionContext(
                {}, has_summon_query=lambda selector: has_captured_summon(actual)
            )
            self.assertTrue(evaluate_condition('not HasSummon("caster")', context))
            self.assertNotIn(actor.id, fixture.preview.actors)
        self.assertEqual(fixture.preview.actors, original_roster)
