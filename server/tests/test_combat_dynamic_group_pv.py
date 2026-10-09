import unittest
from types import SimpleNamespace
from wakfu_server.combat_group_pv import resolve_group_level_pv, scoped_group_actors
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_summon_initialization import detached_summon_scope
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_effect_removal import _identity_fields


class DynamicGroupPVTests(unittest.TestCase):
    def construction(self):
        actor = SimpleNamespace(
            id=91,
            team=-1,
            effective_level=37,
            state_ledger=StateLedger(91),
            effect_stats={1: 60, 92: 20},
            effect_maxima={1: 100, 92: 50},
        )
        authority = NativeActorAuthority(
            targeting={"dpu_id": 91, "dpr_id": 91, "bcN": -1},
            is_player=False,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=2382,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
            native_controller_id=91,
        )
        return SimpleNamespace(actors={}), actor, authority

    def test_detached_constructor_level_source_is_actual_and_scope_limited(self):
        fight, actor, authority = self.construction()
        with detached_summon_scope(fight, actor, authority):
            self.assertIs(resolve_group_level_pv(fight, 91), actor)
            self.assertIs(scoped_group_actors(fight)[91], actor)
            self.assertNotIn(91, fight.actors)
        self.assertEqual(scoped_group_actors(fight), {})
        with self.assertRaisesRegex(ValueError, "level-source PV"):
            resolve_group_level_pv(fight, 91)

    def test_actual_999_child_context_resolves_detached_eGj_level(self):
        fight, actor, authority = self.construction()
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.fight = fight
        runtime.plan = {
            "native_retained_container": {"present": True, "type": 11, "level": 23}
        }
        parameters = [0, 0, 0, 0, 1, 0, 1, 100]
        effect = {
            "effect_class": 999,
            "native_effect_flags": [],
            "parameters": [part for value in parameters for part in (value, 0)],
        }
        invocation = EffectInvocation(1, 1, 91, None, (0, 0, 0))
        with detached_summon_scope(fight, actor, authority):
            level, context = runtime.child_level_context(
                effect, {"parameters": parameters}, invocation, default_level=1
            )
        self.assertEqual(level, 37)
        self.assertEqual(_identity_fields(context, integer_fields=(4,))[4], 37)

    def test_hp_and_characteristic_null_rebind_keep_detached_caster(self):
        from wakfu_server.combat_characteristic_level_group import (
            runtime_group_level as pc_level,
        )
        from wakfu_server.combat_hp_level_group import runtime_group_level as hp_level

        fight, actor, authority = self.construction()
        invocation = EffectInvocation(1, 1, 91, None, (0, 0, 0))
        for family, callback, expected in ((913, pc_level, 60), (1047, hp_level, 80)):
            for rebind in (1, 2):
                parameters = [0, 0, 0, 0, 1, rebind, 1, 1, 0, 1, 0]
                effect = {
                    "effect_class": family,
                    "native_execution_mode": 0,
                    "parameters": [part for value in parameters for part in (value, 0)],
                }
                with detached_summon_scope(fight, actor, authority):
                    self.assertEqual(
                        callback(
                            effect,
                            {"parameters": parameters},
                            invocation,
                            scoped_group_actors(fight),
                        ),
                        expected,
                    )
