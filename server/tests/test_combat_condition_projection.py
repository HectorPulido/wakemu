"""One-call native property projection retains actor validation and freshness."""
import unittest
from unittest.mock import patch

import test_combat_ordinary_authority as ordinary_fixtures
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_summon import RegisteredSummonAuthority


class ConditionProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ordinary_fixtures.OrdinaryAuthorityTests.setUpClass()

    def setUp(self):
        fixture = ordinary_fixtures.OrdinaryAuthorityTests()
        fixture.setUp()
        self.fight = fixture.preview
        self.ordinary = fixture.authority

    def test_ordinary_and_wrapped_projection_match_separate_native_reads(self):
        for authority in (self.ordinary, RegisteredSummonAuthority(self.ordinary)):
            for actor in self.fight.actors.values():
                with self.subTest(provider=type(authority).__name__, actor=actor.id):
                    expected = (
                        authority(self.fight, actor),
                        authority.world_properties(self.fight, actor),
                        authority.properties(self.fight, actor),
                    )
                    self.assertEqual(
                        authority.condition_projection(self.fight, actor), expected
                    )

    def test_wrapped_projection_validates_ordinary_actor_once(self):
        actor = self.fight.actors[7]
        authority = RegisteredSummonAuthority(self.ordinary)
        original = OrdinaryActorAuthority.__call__
        calls = []

        def counted(provider, fight, candidate):
            calls.append(candidate.id)
            return original(provider, fight, candidate)

        with patch.object(OrdinaryActorAuthority, "__call__", counted):
            authority.condition_projection(self.fight, actor)
        self.assertEqual(calls, [actor.id])

    def test_next_projection_observes_changed_properties_and_rejects_invalid_actor(
        self,
    ):
        actor = self.fight.actors[7]
        authority = RegisteredSummonAuthority(self.ordinary)
        before = authority.condition_projection(self.fight, actor)
        actor.native_fight_properties = frozenset({15, 78})
        actor.native_world_properties = frozenset({9})
        after = authority.condition_projection(self.fight, actor)
        self.assertEqual(after[1:], (frozenset({9}), frozenset({15, 78})))
        self.assertNotEqual(before[1:], after[1:])
        actor.team = -1
        with self.assertRaisesRegex(ValueError, "signed-byte fight affiliation"):
            authority.condition_projection(self.fight, actor)

    def test_adapter_native_projection_matches_unoptimized_provider(self):
        import test_combat_runtime_adapter as adapter_fixtures
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_conditions import evaluate_condition

        fixture = adapter_fixtures.ServerAdapterTests()
        fixture.setUp()
        native = RegisteredSummonAuthority(self.ordinary)

        class SeparateReads:
            def __call__(provider, preview, actor):
                return native(preview, actor)

            def __getattr__(provider, name):
                return getattr(native, name)

        invocation = EffectInvocation(339526, 1, 7, -7, (1, 0, 0))
        contexts = [
            NativeServerRuntimeAdapter(
                actor_authority=provider, cast=fixture.cast
            ).condition(self.fight, {}, None, invocation)
            for provider in (SeparateReads(), native)
        ]
        self.assertEqual(contexts[0].actors, contexts[1].actors)
        for criterion in ("1 == 1", "1 == 0", "IsTriggeredByMeleeEffect()"):
            self.assertEqual(
                evaluate_condition(criterion, contexts[0]),
                evaluate_condition(criterion, contexts[1]),
            )

    def test_custom_ordinary_property_getters_are_preserved(self):
        class CustomOrdinary(OrdinaryActorAuthority):
            def properties(provider, preview, actor):
                observed.append("fight")
                return super().properties(preview, actor)

            def world_properties(provider, preview, actor):
                observed.append("world")
                return super().world_properties(preview, actor)

        observed = []
        custom = CustomOrdinary.__new__(CustomOrdinary)
        custom.__dict__.update(self.ordinary.__dict__)
        authority = RegisteredSummonAuthority(custom)
        authority.condition_projection(self.fight, self.fight.actors[7])
        self.assertEqual(observed, ["world", "fight"])


if __name__ == "__main__":
    unittest.main()
