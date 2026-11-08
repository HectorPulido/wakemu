"""Actual retained 937 source rows use the shared prune user index."""
import json
import unittest
from unittest.mock import patch

from test_combat_qi_death_lifecycle import NativeQIDeathLifecycleTests
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_pointer_qi_actor import (
    ActualActorQI,
    ActualRetained937,
    RetainedContext,
)
from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint
from wakfu_server.combat_pointer_qi_lifecycle import NativeRunner937, NativePK937
from wakfu_server import combat_pointer_qi_lifecycle as lifecycle
from wakfu_server.combat_pointer_qi_spatialowned import NativeSpatialRecord
from wakfu_server.combat_retained_runtime import group_payload
from wakfu_server import combat_state_managers as managers
from wakfu_server import combat_native_container as containers


class PruneSpatialWrapperTests(unittest.TestCase):
    def test_actual_spatial_runner_keeps_parent_without_per_descriptor_scan(self):
        fight, _, target, _ = NativeQIDeathLifecycleTests().fight()
        for actor in fight.actors.values():
            actor.native_physical_position = actor.position
        checkpoint = NativePointerCheckpoint(ActualActorQI(fight))
        fight.native_pointer_checkpoint = checkpoint
        definitions = json.loads(lifecycle._SOURCE.read_text())
        reference = int(next(iter(definitions)))
        pk = NativePK937.from_sealed(reference, 1, definitions[str(reference)])

        class Hooks:
            def publish_execution(self, *args):
                pass

            def log_exception(self, *args):
                pass

            def after_application(self, *args):
                pass

            def before_dispose(self, *args):
                pass

            def release(self, *args):
                pass

        runner = NativeRunner937(
            ActualRetained937(
                10002,
                checkpoint._qi.objects[target.id],
                RetainedContext(checkpoint._qi),
                True,
            ),
            pk,
            Hooks(),
        )
        payload = group_payload(
            uid=10002,
            base_uid=10002,
            generic_effect=reference,
            caster_id=7,
            target_id=target.id,
            cell=target.position,
            container_type=None,
            container_id=None,
            timing_payload=b"",
        )
        row = NativeSpatialRecord(runner, caster_id=7, state_uid=900, payload=payload)
        fight.native_owned_spatial_effects[10002] = row
        fight.native_owned_state_containers = {
            900: {"uid": 900, "target_id": 101, "caster_id": None}
        }
        fight.native_retired_area_managers[101] = OwnedAreaRow(uid=101)
        fight.native_retired_area_managers[102] = OwnedAreaRow(uid=102)
        self.assertIs(row.validate(fight), runner)
        self.assertEqual(managers._owned_container_state_users(fight), {900})
        with patch.object(
            containers,
            "owned_container_users",
            side_effect=AssertionError("repeated source scan"),
        ):
            managers.prune_retired_state_managers(fight)
        self.assertEqual(set(fight.native_retired_area_managers), {101})
        self.assertIs(fight.native_owned_spatial_effects[10002], row)
        self.assertIs(row.validate(fight), runner)
        self.assertFalse(runner.disposed)
        self.assertIs(runner.spatial.target.actor, target)
        del fight.native_owned_spatial_effects[10002]
        managers.prune_retired_state_managers(fight)
        self.assertEqual(fight.native_retired_area_managers, {})


if __name__ == "__main__":
    unittest.main()
