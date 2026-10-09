"""Actual factory activation of original Steamer aura/removal definitions.

Only criteria are cleared to isolate machinery. A real class summon constructor
supplies selector4096 ownership; no targeting or relation facts are invented.
"""
import unittest
from copy import deepcopy
from random import Random
import test_combat_displacement as fixtures
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_execution_context import constructed_execution_context
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_summon import RegisteredSummonAuthority, SummonSpecification
from wakfu_server.combat_summon_creation import NativeSummonBuilder


class AuraRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeDisplacementTests.setUpClass()

    def test_original338_creation_then316_removes_exact_retained_aura(self):
        f = fixtures.NativeDisplacementTests()
        f.setUp()
        authority = RegisteredSummonAuthority(f.authority)
        # Native class profile3791 has an original empty cle INITIALSTATES list.
        # Its common builder installs actual NPC PA, controller and summon flags.
        spec = SummonSpecification(3791, 1, False, 2, 0, "caster", 0)
        actor, registration = NativeSummonBuilder(authority)(
            f.preview, spec, 7, 901, (8, 0, 0)
        )
        authority.register(
            f.preview,
            actor,
            registration,
            new_order=list(f.preview.order),
            new_turn_index=f.preview.turn_index,
        )
        self.assertTrue(authority(f.preview, actor).targeting["dTE"])
        effects = dict(f.fixture.effects)
        states = dict(f.fixture.states, effects=dict(f.fixture.states["effects"]))
        for reference in ("344975", "297966"):
            original = effects.get(reference, states["effects"].get(reference))
            self.assertIsNotNone(original)
            isolated = deepcopy(original)
            isolated["criteria"] = ""
            if reference in effects:
                effects[reference] = isolated
            if reference in states["effects"]:
                states["effects"][reference] = isolated
        adapter = NativeServerRuntimeAdapter(
            actor_authority=authority,
            cast=ordinary_cast_authority(
                actors=authority,
                timing=NativeEffectTimingProvider(states),
                rng=Random(1),
                critical=False,
            ),
        )
        factory = NativeEffectRuntimeFactory(
            effects=effects,
            state_catalog=states,
            characteristic_registry=f.fixture.registry,
            action_id=1,
            contexts=adapter.contexts(),
            displacement_authority=authority,
            summon_authority=authority,
        )
        dispatcher, packets = factory(
            f.preview,
            dict(
                actor_id=7,
                spell_id=6266,
                evaluation_level=1,
                target_id=901,
                target=actor.position,
            ),
        )
        context = constructed_execution_context().payload().hex()
        self.assertTrue(
            dispatcher.execute(
                EffectInvocation(
                    344975, 1, 7, 901, actor.position, native_context_hex=context
                )
            )
        )
        retained = dispatcher.group_retention.view()
        selected = [entry for entry in retained.entries if entry.effect_class == 338]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].manager_id, 901)
        row = next(
            row
            for row in f.preview.native_effect_areas.values()
            if row["effect_class"] == 338
        )
        self.assertEqual(
            (row["owner_id"], row["direction"], row["native_anchor_id"]), (901, 2, 901)
        )
        area_uid, running_uid = row["uid"], selected[0].uid
        self.assertTrue(
            dispatcher.execute(
                EffectInvocation(
                    297966, 1, 7, 901, actor.position, native_context_hex=context
                )
            )
        )
        self.assertNotIn(area_uid, f.preview.native_effect_areas)
        self.assertNotIn(running_uid, f.preview.native_owned_area_effects)
        self.assertFalse(
            any(
                entry.effect_class == 338
                for entry in dispatcher.group_retention.view().entries
            )
        )
        self.assertTrue(any(opcode == 13497 for opcode, _ in packets))
        self.assertTrue(any(opcode == 13560 for opcode, _ in packets))
