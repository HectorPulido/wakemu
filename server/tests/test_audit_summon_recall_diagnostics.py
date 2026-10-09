import unittest
from types import SimpleNamespace
from unittest.mock import patch

from audit_summon_recall_transaction import (
    _actor_facts,
    _recall_summon_authority,
    _trace_native_resolution,
)
from wakfu_server.combat_state import Actor
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_resolver import (
    EffectResolutionContext,
    NativeEffectResolver,
)


class RecallAuditDiagnosticsTests(unittest.TestCase):
    def _resolver(self, *, native_context=True):
        caster = SimpleNamespace(
            id=7,
            position=(0, 0, 0),
            team=0,
            hp=100,
            physical_radius=0,
        )
        target = SimpleNamespace(
            id=295,
            position=(0, 0, 0),
            team=1,
            hp=1,
            physical_radius=0,
        )
        contexts = {
            identity: {
                "is_eGj": True,
                "baF": True,
                "bEe": True,
                "UNTARGETTABLE_BY_OTHER": False,
                "is_eHH": False,
                "is_Qq": False,
            }
            for identity in (7, 295)
        }
        resolver = NativeEffectResolver(
            actors=lambda effect, invocation: (caster, target),
            native_context=(
                (lambda effect, invocation: contexts)
                if native_context
                else (lambda effect, invocation: None)
            ),
            context=lambda effect, invocation: EffectResolutionContext(
                "EFFECTS_ONLY",
                "immediate",
                "actors",
                True,
            ),
            caster=lambda effect, invocation: caster,
            direct_target_policies={"42": [859, False, False]},
        )
        effect = {
            "reference": 326443,
            "effect_class": 859,
            "variant": 0,
            "native_target_selector": {"class": "fcE", "mask": 1},
            "target_masks": (None,) * 7,
            "area_class": "anD",
            "area_native": "point",
            "native_effect_flags": (15,),
        }
        invocation = EffectInvocation(
            42,
            153,
            7,
            295,
            (0, 0, 0),
            native_explicit_target=False,
        )
        return resolver, effect, invocation

    def test_canonical_resolution_wrapper_traces_selector_and_restores_hooks(self):
        import wakfu_server.combat_effect_resolver as resolver_module

        resolver, effect, invocation = self._resolver()
        candidate_globals = NativeEffectResolver.candidate_invocations.__globals__
        self.assertIs(
            candidate_globals["select_native_effect_targets"],
            resolver_module.select_native_effect_targets,
        )
        original_context = resolver.context
        original_selector = resolver_module.select_native_effect_targets
        resolutions, selectors = [], []

        result = _trace_native_resolution(
            resolver,
            effect,
            invocation,
            original_resolve=NativeEffectResolver.__call__,
            resolution_diagnostics=resolutions,
            selector_diagnostics=selectors,
        )

        self.assertEqual([item.target_id for item in result], [7, 295])
        self.assertTrue(resolutions[0]["candidate_selector_patch_identity"])
        self.assertEqual(
            resolutions[0]["resolution_context"]["variant_mode"], "EFFECTS_ONLY"
        )
        self.assertTrue(resolutions[0]["application_eligible"])
        self.assertEqual(resolutions[0]["direct_target_policy"], [859, False, False])
        self.assertEqual(selectors[0]["invocation_reference"], 42)
        self.assertEqual(selectors[0]["selected_actor_ids"], [7, 295])
        self.assertIs(resolver.context, original_context)
        self.assertIs(resolver_module.select_native_effect_targets, original_selector)

    def test_canonical_resolution_wrapper_preserves_selector_exception_and_restores(
        self,
    ):
        import wakfu_server.combat_effect_resolver as resolver_module

        resolver, effect, invocation = self._resolver(native_context=False)
        original_context = resolver.context
        original_selector = resolver_module.select_native_effect_targets
        resolutions, selectors = [], []

        with self.assertRaisesRegex(ValueError, "Missing native context"):
            _trace_native_resolution(
                resolver,
                effect,
                invocation,
                original_resolve=NativeEffectResolver.__call__,
                resolution_diagnostics=resolutions,
                selector_diagnostics=selectors,
            )

        self.assertEqual(len(selectors), 1)
        self.assertIn("selector_error", selectors[0])
        self.assertEqual(len(resolutions), 1)
        self.assertIn("resolution_error", resolutions[0])
        self.assertIs(resolver.context, original_context)
        self.assertIs(resolver_module.select_native_effect_targets, original_selector)

    def test_diagnostic_capture_failure_does_not_change_selector_result(self):
        import wakfu_server.combat_effect_resolver as resolver_module

        resolver, effect, invocation = self._resolver()
        original_context = resolver.context
        original_selector = resolver_module.select_native_effect_targets
        resolutions, selectors = [], []

        with patch(
            "audit_summon_recall_transaction._summary",
            side_effect=RuntimeError("trace only"),
        ):
            result = _trace_native_resolution(
                resolver,
                effect,
                invocation,
                original_resolve=NativeEffectResolver.__call__,
                resolution_diagnostics=resolutions,
                selector_diagnostics=selectors,
            )

        self.assertEqual([item.target_id for item in result], [7, 295])
        self.assertTrue(resolutions[0]["diagnostic_errors"])
        self.assertTrue(selectors[0]["diagnostic_errors"])
        self.assertIs(resolver.context, original_context)
        self.assertIs(resolver_module.select_native_effect_targets, original_selector)

    def test_authority_comes_from_owned_server_runtime_factory(self):
        authority = lambda fight, actor: {"actor_id": actor.id}
        factory = SimpleNamespace(summon_authority=authority)
        runtime = SimpleNamespace(action_id=21)
        character = {"id": 7}
        monster = {"id": 9}
        deck = b"owned-deck"

        with patch(
            "wakfu_server.combat_server_spell.server_runtime",
            return_value=(factory, object()),
        ) as server_runtime:
            resolved = _recall_summon_authority(runtime, character, monster, deck)

        self.assertIs(resolved, authority)
        args, kwargs = server_runtime.call_args
        self.assertEqual(args, (character, {9: monster}, deck))
        self.assertEqual(kwargs["action_id"], 22)
        self.assertIs(kwargs["critical"], False)
        self.assertIsNotNone(kwargs["rng"])

    def test_actor_facts_record_authority_result_without_runtime_message_fields(self):
        owner = Actor(7, 0, (0, 0, 0), 100, 6, 3, 0, 20, owner_id=7, controlled=True)
        summon = Actor(295, 0, (-23, -142, 70), 1, 1, 1, 0, 20)
        summon.effect_stats = {1: 1, 14: 2}
        summon.effect_minima = {1: 1, 14: 0}
        summon.effect_maxima = {1: 100, 14: 10}
        summon.effect_base_maxima = {1: 100, 14: 10}
        summon.effect_frozen = frozenset()
        summon.native_fight_properties = frozenset({65})
        fight = SimpleNamespace(native_summon_registrations={295: {"actor_id": 295}})
        authority = lambda live_fight, live_actor: {
            "fight_identity": id(live_fight),
            "actor_id": live_actor.id,
        }
        owner_facts = _actor_facts(fight, owner, authority)
        facts = _actor_facts(fight, summon, authority)

        self.assertEqual(
            facts["authority"],
            {
                "fight_identity": id(fight),
                "actor_id": 295,
            },
        )
        self.assertEqual(facts["registration"], {"actor_id": 295})
        self.assertEqual(facts["effect_stats"], {"1": 1, "14": 2})
        self.assertEqual(facts["effect_base_maxima"], {"1": 100, "14": 10})
        self.assertEqual(facts["effect_frozen"], [])
        self.assertEqual(facts["fight_properties"], [65])
        self.assertIsNone(owner_facts["effect_stats"])
        self.assertIsNone(owner_facts["fight_properties"])


if __name__ == "__main__":
    unittest.main()
