"""Actor-only current-package 937 integration without private prototype imports."""
from pathlib import Path
from dataclasses import replace
import json, unittest
import test_combat_behind_target_condition as fixtures


class CurrentActor937IntegrationTests(unittest.TestCase):
    def test_actual_package_uid_preparation_dispatch_wrapper_and_removal(self):
        from wakfu_server.combat_pointer_qi_handler import (
            NativeSpatialHandler,
            publish_spatial_registry,
        )
        from wakfu_server.combat_pointer_qi_lifecycle import _SOURCE
        from wakfu_server.combat_pointer_qi_spatialowned import validate_spatial_record
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_effect_dispatch import (
            EffectInvocation,
            EffectDispatcher,
        )
        from wakfu_server.combat_qi_fight import current_registry

        fight, actor, other = fixtures.BehindTargetConditionTests().fixture()
        effect = json.loads(_SOURCE.read_bytes())["112320"]
        metadata = json.loads(
            (
                Path(__file__).with_name("fixtures") / "native-spatial937-retained.json"
            ).read_bytes()
        )
        packets = []
        plan = {"native_retained_container": {"present": False}}
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan=plan,
            state_catalog={},
            action_id=1,
            timing=None,
            metadata={"effects": metadata["effects"], "states": {}, "spells": {}},
        )
        timing = NativeEffectTimingProvider({})
        handler = NativeSpatialHandler(
            fight,
            packets,
            action_id=1,
            retention=retention,
            context=lambda effect, invocation: timing.stat(
                fight, plan, effect, invocation
            ),
            publish_registry=publish_spatial_registry,
            rng=lambda: 0.0,
        )
        first = EffectInvocation(
            112320,
            100,
            actor.id,
            actor.id,
            actor.position,
            native_retained_container={"present": False},
        )
        second = replace(first, target_id=other.id, cell=other.position)
        fight.native_effect_uid_next = 777
        dispatcher = EffectDispatcher(
            {str(first.reference): effect},
            {937: retention.wrap(handler)},
            resolve=lambda *args: (first, second),
            condition_context=lambda invocation: {},
            probability_accepts=lambda *args: True,
            group_cells=lambda *args: (),
            actor_position=lambda uid: fight.actors[uid].position,
            prepare_effect=handler.prepare,
        )
        self.assertTrue(dispatcher.execute(first))
        self.assertEqual(fight.native_retained_order, [777, 778])
        self.assertFalse(handler.prepared)
        self.assertIs(current_registry(fight).qi, fight.native_pointer_checkpoint._qi)
        runner = validate_spatial_record(fight, fight.native_owned_spatial_effects[777])
        self.assertIs(runner.spatial.target.actor, actor)
        self.assertIs(runner.spatial.context.qi.fight, fight)
        runner.dispose()
        retention.synchronize()
        self.assertGreaterEqual(actor.native_obstacle_id, 0)
        self.assertEqual(other.native_obstacle_id, -1)
        self.assertEqual(fight.native_retained_order, [778])
        self.assertEqual(len(packets), 2)
