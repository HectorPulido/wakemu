"""QI identity aliases do not execute Qf; retained 937 callbacks still protect it."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from test_gc_owned_collections import OwnedCollectionGCTests
from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_pointer_qi_actor import (
    ActualActorQI,
    ActualRetained937,
    RetainedContext,
)
from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint
from wakfu_server.combat_pointer_qi_lifecycle import NativeRunner937, NativePK937
from wakfu_server import combat_pointer_qi_lifecycle
from wakfu_server.combat_pointer_qi_spatialowned import NativeSpatialRecord
from wakfu_server.combat_retained_runtime import group_payload
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.fight_checkpoint_store import snapshot


class QKRootStrengthTests(unittest.TestCase):
    def fixture(self):
        _, fight, runtime, dead, uid = OwnedCollectionGCTests().fixture()
        for actor in fight.actors.values():
            actor.native_physical_position = actor.position
        fight.native_pointer_checkpoint = NativePointerCheckpoint(ActualActorQI(fight))
        qi = fight.native_pointer_checkpoint._qi
        qi.remove(qi.objects[dead])
        fight.native_pointer_checkpoint.publish()
        return deepcopy(fight), fight, runtime, dead, uid

    def test_dead_qk_alias_does_not_retain_unrelated_effect_or_change_checkpoint(self):
        previous, fight, runtime, dead, uid = self.fixture()
        checkpoint = fight.native_pointer_checkpoint
        original = deepcopy(dict(checkpoint))
        pointer = checkpoint._qi.objects[dead]
        projection, roots = boundary.planning_snapshot(fight)
        self.assertNotIn("native_pointer_checkpoint", projection)
        self.assertIn("native_pointer_checkpoint", snapshot(fight))
        self.assertEqual(roots, [])
        events = []
        original_view, original_projection = (
            boundary._complete_view,
            boundary._project_snapshot,
        )

        def view(current):
            events.append("view")
            return original_view(current)

        def project(current, pending):
            events.append("snapshot")
            return original_projection(current, pending)

        with patch.object(boundary, "_complete_view", side_effect=view), patch.object(
            boundary, "_project_snapshot", side_effect=project
        ):
            boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertEqual(events, ["view", "snapshot", "view"])
        self.assertNotIn(uid, fight.native_retained_records)
        self.assertNotIn(uid, fight.native_owned_group_effects)
        self.assertIn(uid, previous.native_retained_records)
        self.assertIs(checkpoint._qi.objects[dead], pointer)
        self.assertIs(pointer.actor, fight.actors[dead])
        self.assertEqual(dict(checkpoint), original)

    def test_no_eligible_terminal_does_not_serialize_planning_snapshot(self):
        previous, fight, runtime, _, uid = self.fixture()
        with patch(
            "wakfu_server.combat_ordinary_qi_retirement.retired_ordinary_qi_ids",
            return_value=(),
        ), patch.object(
            boundary,
            "_project_snapshot",
            side_effect=AssertionError("unnecessary snapshot"),
        ):
            boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertIn(uid, fight.native_retained_records)

    def test_actual_937_target_with_callbacks_is_preserved_by_opaque_defer(self):
        previous, fight, runtime, dead, uid = self.fixture()
        checkpoint = fight.native_pointer_checkpoint
        definitions = json.loads(
            Path(combat_pointer_qi_lifecycle.__file__)
            .with_name("native-spatial937-source.json")
            .read_text()
        )
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
                checkpoint._qi.objects[dead],
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
            target_id=dead,
            cell=fight.actors[dead].position,
            container_type=None,
            container_id=None,
            timing_payload=b"",
        )
        row = NativeSpatialRecord(runner, caster_id=7, state_uid=None, payload=payload)
        self.assertIs(row.validate(fight), runner)
        fight.native_owned_spatial_effects[10002] = row
        fight.native_retained_records.install_owned(
            10002,
            asdict(
                RetainedEffect(
                    10002,
                    dead,
                    937,
                    reference,
                    manager_id=dead,
                    container_present=False,
                )
            ),
        )
        fight.native_retained_order.append(10002)
        self.assertTrue(fight.native_retained_records.owner.consistent())
        self.assertIsNone(boundary.planning_snapshot(fight))
        boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertIn(uid, fight.native_retained_records)
        self.assertIs(fight.native_owned_spatial_effects[10002], row)
        self.assertFalse(runner.disposed)
        self.assertIs(runner.spatial.target.actor, fight.actors[dead])


if __name__ == "__main__":
    unittest.main()
