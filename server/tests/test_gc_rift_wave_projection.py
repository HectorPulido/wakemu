import unittest

from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_retained_gc import plan_retired_effects
from wakfu_server.fight_checkpoint_store import snapshot
import test_gc_area_collections as _area_fixture


class RiftWavePlannerProjectionTests(unittest.TestCase):
    def test_full_and_projected_plans_preserve_remaining_area_roots(self):
        (
            previous,
            fight,
            runtime,
            dead,
            _,
            _,
        ) = _area_fixture.AreaCollectionGCTests().fixture()
        fight.rift_wave_state = {
            "wave": 3,
            "staged_receipts": [{"completed_wave": wave} for wave in range(1, 4)],
            "native_wave_entries": {str(wave): {"wave": wave} for wave in range(1, 4)},
            "native_artifact_groups": {
                "3": {
                    "wave": 3,
                    "original": {"901": 1759, "999": 1759},
                    "remaining": [901, 999],
                    "assignments": [],
                    "choices_allowed": 1,
                    "choices_made": 0,
                }
            },
        }
        self.assertTrue(boundary._canonical_graph(fight))

        full = snapshot(fight)
        projected, roots = boundary.planning_snapshot(fight)
        full_plan = plan_retired_effects(full, {dead}, pending_roots=roots)
        projected_plan = plan_retired_effects(projected, {dead}, pending_roots=roots)

        self.assertEqual(full_plan, projected_plan)
        self.assertIn(901, projected_plan.marked_actor_ids)
        self.assertIn((None, "unresolved_future_area"), projected_plan.opaque_sources)
        self.assertEqual(
            projected["rift_wave_state"],
            {"native_artifact_groups": {"3": {"remaining": [901, 999]}}},
        )
        # This is only a planner input projection; durable checkpoint history
        # remains complete and the live Fight was not rewritten.
        self.assertEqual(full["rift_wave_state"], fight.rift_wave_state)
        self.assertEqual(len(fight.rift_wave_state["staged_receipts"]), 3)

    def test_missing_or_unknown_shapes_fall_back_and_missing_remaining_stays_missing(
        self,
    ):
        no_groups = {"wave": 3, "staged_receipts": []}
        unknown_field = {
            "wave": 3,
            "native_artifact_groups": {},
            "future_extension": {"opaque": 1},
        }
        malformed_group = {"native_artifact_groups": {"3": {"remaining": "not-a-list"}}}
        unknown_group_field = {
            "native_artifact_groups": {
                "3": {"remaining": [901], "future_group_extension": True}
            }
        }
        self.assertIs(boundary._planner_rift_wave_state(no_groups), no_groups)
        self.assertIs(boundary._planner_rift_wave_state(unknown_field), unknown_field)
        self.assertIs(
            boundary._planner_rift_wave_state(malformed_group), malformed_group
        )
        self.assertIs(
            boundary._planner_rift_wave_state(unknown_group_field),
            unknown_group_field,
        )
        self.assertEqual(
            boundary._planner_rift_wave_state(
                {"native_artifact_groups": {"3": {"wave": 3}}}
            ),
            {"native_artifact_groups": {"3": {}}},
        )


if __name__ == "__main__":
    unittest.main()
