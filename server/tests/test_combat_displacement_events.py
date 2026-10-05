import random
import unittest
from unittest.mock import patch
import test_combat_displacement as fixture
from wakfu_server.combat_displacement_events import (
    BASE_EVENT_IDS,
    displacement_event_ids,
)
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields


class NativeDisplacementMaskTests(unittest.TestCase):
    def test_registry_masks_do_not_fabricate_collision_or_external_events(self):
        for kind, expected in BASE_EVENT_IDS.items():
            effect = dict(effect_class=kind, target_masks=[None] * 7)
            self.assertEqual(displacement_event_ids(effect), expected)
            self.assertNotIn(204, expected)
            self.assertNotIn(1002, expected)
        effect = dict(effect_class=301, target_masks=[None] * 6 + [[2254]])
        self.assertEqual(displacement_event_ids(effect), (0, 185, 188, 2254))


class OrdinaryDisplacementEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.NativeDisplacementTests.setUpClass()

    def setUp(self):
        self.f = fixture.NativeDisplacementTests()
        self.f.setUp()
        f = self.f
        self.adapter = NativeServerRuntimeAdapter(
            actor_authority=f.authority,
            cast=ordinary_cast_authority(
                actors=f.authority,
                timing=NativeEffectTimingProvider(f.fixture.states),
                rng=random.Random(1),
                critical=False,
            ),
        )
        factory = NativeEffectRuntimeFactory(
            effects=f.effects,
            state_catalog=f.fixture.states,
            characteristic_registry=f.fixture.registry,
            action_id=1,
            contexts=self.adapter.contexts(),
            displacement_authority=f.authority,
        )
        self.dispatcher, self.packets = factory(
            f.preview, dict(spell_id=6266, evaluation_level=1)
        )

    def capture(self, invocation):
        seen = []
        original = type(self.dispatcher.replay_event).__call__

        def replay(instance, source, **kwargs):
            seen.append(
                (
                    source.channel,
                    source.manager_actor_id,
                    source.target_id,
                    source.value,
                    source.event_ids,
                    self.f.preview.actors[-7].position,
                )
            )
            return original(instance, source, **kwargs)

        with patch.object(type(self.dispatcher.replay_event), "__call__", replay):
            self.dispatcher.execute(invocation)
        return seen

    def test_native_pull_phase_order_values_and_actual_position(self):
        seen = self.capture(
            EffectInvocation(326111, 1, 7, -7, (0, 0, 0), native_explicit_target=True)
        )
        self.assertEqual([row[0] for row in seen], [10, 1, 20, 2, 30, 3, 40, 4])
        self.assertEqual([row[3] for row in seen], [0, 0, 0, 0, 2, 2, 2, 2])
        self.assertTrue(all(row[4] == (0, 185, 188) for row in seen))
        self.assertEqual([row[5] for row in seen], [(4, 0, 0)] * 4 + [(2, 0, 0)] * 4)
        self.assertEqual(self.f.preview.native_effect_uid_next, 201)

    def test_targetless_teleport_keeps_native_null_target_and_caster_roles(self):
        seen = self.capture(EffectInvocation(349548, 1, 7, None, (2, 2, 0)))
        self.assertEqual([row[0] for row in seen], [10, 20, 30, 40])
        self.assertTrue(all(row[1] == 7 and row[2] is None for row in seen))
        self.assertTrue(all(row[4] == (0, 189, 197) for row in seen))
        self.assertEqual(self.f.preview.actors[7].position, (2, 2, 0))

    def test_original_movement_listener_activates_and_removal_stops_reaction(self):
        # Original eYg353389 is REVERSED: its mask187/188 receives caster
        # channel40, then native Qd5 rebinds its target to the displaced NPC.
        # Install on player Qf; neither subscription nor criteria are changed.
        self.dispatcher.execute(EffectInvocation(353389, 1, 7, 7, (0, 0, 0)))
        groups = self.f.preview.native_owned_group_effects
        listener = next(
            uid
            for uid, row in groups.items()
            if row["invocation"]["reference"] == 353389
        )
        self.dispatcher.execute(
            EffectInvocation(326111, 1, 7, -7, (0, 0, 0), native_explicit_target=True)
        )

        def executions():
            return sum(
                _identity_fields(body[18:])[3] == 353390
                for opcode, body in self.packets
                if opcode == 13497
            )

        self.assertGreater(executions(), 0)
        self.dispatcher.native_retention.remove_group(listener)
        previous = executions()
        self.dispatcher.execute(
            EffectInvocation(358000, 1, 7, -7, (2, 0, 0), native_explicit_target=True)
        )
        self.assertEqual(executions(), previous)
