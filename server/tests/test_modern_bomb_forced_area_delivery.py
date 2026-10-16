"""Actual307 Rogue bombs share forced-movement QI and Qs publication."""
import os
import unittest
from unittest.mock import patch
import test_rogue_runtime_pipeline as pipeline
from wakfu_server.combat_server_spell import server_runtime
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_ordinary_events import OrdinaryDisplacementEvents
from wakfu_server.combat_displacement_events import displacement_event_ids
from wakfu_server.combat_qi_fight import current_registry


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class ModernBombForcedAreaDeliveryTests(unittest.TestCase):
    def test_native_bomb_push_preserves_qi_and_routes_native_events(self):
        helper = pipeline.RogueRuntimePipelineTests()
        data = helper.fixture()
        owner = data[2].actors[7]
        data, _ = helper.cast(
            data, 7906, (owner.position[0] + 1, owner.position[1], owner.position[2])
        )
        character, monster, fight, deck, rng = data
        bomb = helper.summons(fight, (3795, 3796, 3797))[0]
        before = tuple(bomb.position)
        factory, _ = server_runtime(
            character, {-7: monster}, deck, action_id=12, critical=False, rng=rng
        )
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        transitions, phases = [], []
        movement = NativeAreaEventRuntime.movement
        phase = OrdinaryDisplacementEvents.phase

        def observe_movement(runtime, actor_id, **cells):
            transitions.append((actor_id, cells["from_cell"], cells["to_cell"]))
            return movement(runtime, actor_id, **cells)

        def observe_phase(runtime, effect, invocation, **kwargs):
            phases.append(
                (
                    invocation.target_id,
                    kwargs["channel"],
                    displacement_event_ids(effect),
                )
            )
            return phase(runtime, effect, invocation, **kwargs)

        with patch.object(
            NativeAreaEventRuntime, "movement", observe_movement
        ), patch.object(OrdinaryDisplacementEvents, "phase", observe_phase):
            with fight.effect_resolution():
                dispatcher.execute(EffectInvocation(357535, 200, 7, bomb.id, before))
        after = tuple(fight.actors[bomb.id].position)
        self.assertNotEqual(after, before)
        self.assertIn((bomb.id, before, after), transitions)
        self.assertTrue(
            any(
                identity == bomb.id and channel == 3 and 185 in masks
                for identity, channel, masks in phases
            ),
            phases,
        )
        registry = current_registry(fight)
        row = registry.slots[bomb.native_obstacle_id]
        self.assertEqual(row["identity"], ["actor", bomb.id])
        self.assertEqual(row["position"], tuple(after[:2]))
        self.assertGreater(bomb.hp, 0)
