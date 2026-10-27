"""Actual native actor snapshots through the public condition adapter."""
from unittest.mock import patch
import unittest

from wakfu_server.combat_runtime_adapter import (
    NativeServerRuntimeAdapter,
    NativeCastAuthority,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_summon import RegisteredSummonAuthority
from wakfu_server.combat_condition_selection_scope import (
    condition_actor_selection_scope,
)


class RangeSelectionProjectionTests(unittest.TestCase):
    def setUp(self):
        # Same actual ordinary snapshot shape as the existing adapter fixtures,
        # without loading/copying an unrelated full spell/effect population.
        actors = [
            Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True),
            Actor(8, 0, (0, 1, 0), 40, 6, 3, 8, 1),
            Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1),
        ]
        self.fight = Fight(
            77,
            actors,
            {a.position for a in actors},
            {team: {a.position for a in actors if a.team == team} for team in (0, 1)},
        )
        self.fight.ready(3)
        for actor in actors:
            actor.spell_ap_cost_modifiers = {}
            actor.spell_range_modifiers = {}
            actor.effect_stats = {
                1: actor.hp,
                2: 6,
                3: 3,
                4: 6,
                20: 0,
                32: 0,
                92: 0,
                97: 0,
                100: 0,
            }
            actor.effect_minima = {key: 0 for key in actor.effect_stats}
            actor.effect_maxima = {
                1: actor.max_hp,
                2: 6,
                3: 3,
                4: 6,
                20: 1000,
                32: 1000,
                92: 0,
                97: 1000,
                100: 1000,
            }
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        self.ordinary = OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=15, map_id=1134, level=1)},
            monsters={i: dict(id=i, ref=5525, map_id=1134) for i in (8, -7)},
            decks={7: [6266]},
            excluded_decks={7: []},
        )
        self.native = RegisteredSummonAuthority(self.ordinary)
        no_cast = lambda *args: False
        cast = NativeCastAuthority(*(no_cast for _ in range(10)))
        self.adapter = NativeServerRuntimeAdapter(
            actor_authority=self.native, cast=cast
        )

    def context(self, x=0, adapter=None):
        return (adapter or self.adapter).condition(
            self.fight, {}, None, EffectInvocation(339526, 1, 7, None, (x, 0, 0))
        )

    def test_same_native_results_with_fewer_actual_actor_validations(self):
        outputs, validations = [], []
        original = OrdinaryActorAuthority.__call__
        for reuse in (False, True):
            calls = []

            def counted(provider, fight, actor):
                calls.append(actor.id)
                return original(provider, fight, actor)

            with patch.object(
                OrdinaryActorAuthority, "__call__", counted
            ), condition_actor_selection_scope(enabled=reuse):
                outputs.append(
                    [
                        self.context(x).enemy_range_query(0, 5, "target", False, False)
                        for x in (0, 1, 2, 0)
                    ]
                )
            validations.append(len(calls))
        self.assertEqual(outputs[0], outputs[1])
        self.assertLess(validations[1], validations[0])

    def test_nested_callback_discards_cached_native_properties(self):
        with condition_actor_selection_scope():
            context = self.context()
            before = context.enemy_range_query(0, 100, "caster", False, False)
            with condition_actor_selection_scope(enabled=False):
                self.fight.actors[-7].native_fight_properties = frozenset({42})
            after = context.enemy_range_query(0, 100, "caster", False, False)
        self.assertEqual(after, before - 1)

    def test_custom_authority_and_wrapped_subclass_keep_fresh_range_getters(self):
        native = self.native

        class SeparateReads:
            def __call__(self, fight, actor):
                return native(fight, actor)

            def __getattr__(self, name):
                return getattr(native, name)

        class CustomOrdinary(OrdinaryActorAuthority):
            pass

        custom = CustomOrdinary.__new__(CustomOrdinary)
        custom.__dict__.update(self.ordinary.__dict__)
        for authority in (SeparateReads(), RegisteredSummonAuthority(custom)):
            adapter = NativeServerRuntimeAdapter(
                actor_authority=authority, cast=self.adapter.cast
            )
            with condition_actor_selection_scope():
                context = self.context(adapter=adapter)
                with patch.object(
                    authority, "properties", wraps=authority.properties
                ) as properties:
                    first = context.enemy_range_query(0, 100, "caster", False, False)
                    calls = properties.call_count
                    second = context.enemy_range_query(0, 100, "caster", False, False)
                    self.assertEqual(first, second)
                    self.assertGreater(properties.call_count, calls)

    def test_outside_scope_and_new_scope_reject_changed_native_actor(self):
        with condition_actor_selection_scope():
            self.context().enemy_range_query(0, 100, "caster", False, False)
        self.fight.actors[-7].team = -1
        for scoped in (False, True):
            with condition_actor_selection_scope(enabled=scoped), self.assertRaises(
                ValueError
            ):
                self.context().enemy_range_query(0, 100, "caster", False, False)
