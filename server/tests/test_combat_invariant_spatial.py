"""Read-only QI footprint and pointer-checkpoint invariant coverage."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server.combat_invariants import Boundary, check_prepared_boundary
from wakfu_server.combat_pointer_qi_actor import ActualActorQI
from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint
from wakfu_server.combat_state import Actor, Fight


class CombatInvariantSpatialTests(unittest.TestCase):
    @staticmethod
    def report(fight):
        return check_prepared_boundary(
            fight, None, Boundary("spatial-test", "prepared")
        )

    @staticmethod
    def spatial_violations(report):
        return [
            row for row in report.violations if row.invariant.startswith("spatial.")
        ]

    @staticmethod
    def legacy_fixture():
        # This is the existing native QI placement recipe: radius-one actor
        # footprints occupy neighboring cells in the serialized legacy grid.
        from test_combat_behind_target_condition import BehindTargetConditionTests

        fight, _caster, _target = BehindTargetConditionTests().fixture(
            caster_cell=(-7, -7, 2), radius=1
        )
        return fight

    @staticmethod
    def pointer_fixture():
        from native_combat_fixture import initialize_fixture_qi

        player = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        fight = Fight(
            779,
            (player, npc),
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        initialize_fixture_qi(fight)
        qi = ActualActorQI(fight)
        # This is the existing bounded pointer-checkpoint recipe used by the
        # reproduction-state tests, including a retained canonical QK object.
        qi.remove(qi.objects[-7])
        checkpoint = NativePointerCheckpoint(qi)
        fight.native_pointer_checkpoint = checkpoint
        checkpoint.publish()
        return fight, checkpoint

    def test_legacy_radius_footprints_match_actual_cell_topology(self):
        fight = self.legacy_fixture()
        slots = fight.native_qi_slots
        topology = fight.native_qi_byte_topology
        slots_before, topology_before = deepcopy(slots), deepcopy(topology)
        with patch(
            "wakfu_server.combat_qi_fight.current_registry",
            side_effect=AssertionError("diagnostics must not rebuild or validate QI"),
        ):
            report = self.report(fight)
        self.assertFalse(self.spatial_violations(report))
        self.assertIn("spatial.occupancy", report.checked)
        self.assertIn("spatial.cell_topology", report.checked)
        self.assertIs(fight.native_qi_slots, slots)
        self.assertIs(fight.native_qi_byte_topology, topology)
        self.assertEqual(fight.native_qi_slots, slots_before)
        self.assertEqual(fight.native_qi_byte_topology, topology_before)

        self.assertTrue(
            any(
                any(status == 1 for status in row["states"])
                for row in topology.values()
            )
        )

    def test_legacy_cell_membership_change_is_reported_without_repair(self):
        fight = self.legacy_fixture()
        before = deepcopy(fight.native_qi_byte_topology)
        selected = None
        for key, row in fight.native_qi_byte_topology.items():
            if 1 in row["states"]:
                selected = (key, row)
                break
        self.assertIsNotNone(selected)
        _key, row = selected
        live_index = row["states"].index(1)
        row["states"][live_index] = 2
        row["size"] -= 1
        corrupted = deepcopy(fight.native_qi_byte_topology)

        report = self.report(fight)
        self.assertTrue(
            any(
                row.invariant == "spatial.occupancy"
                for row in self.spatial_violations(report)
            )
        )
        self.assertNotEqual(fight.native_qi_byte_topology, before)
        self.assertEqual(fight.native_qi_byte_topology, corrupted)
        self.assertEqual(row["states"][live_index], 2)

    def test_pointer_checkpoint_preserves_canonical_and_tombstone_cell_aliases(self):
        fight, checkpoint = self.pointer_fixture()
        qi = checkpoint._qi
        self.assertTrue(any(2 in value.state["states"] for value in qi.cells.values()))
        pointer_ids = {identity: id(obj) for identity, obj in qi.objects.items()}
        slot_ids = [None if obj is None else id(obj) for obj in qi.slots]
        cell_ids = {
            cell: (id(value), id(value.state)) for cell, value in qi.cells.items()
        }
        states_before = {
            cell: deepcopy(value.state) for cell, value in qi.cells.items()
        }
        checkpoint_before = deepcopy(dict(checkpoint))

        with patch.object(
            NativePointerCheckpoint,
            "validate",
            side_effect=AssertionError(
                "diagnostics must not invoke checkpoint validation"
            ),
        ), patch(
            "wakfu_server.combat_qi_fight.current_registry",
            side_effect=AssertionError("diagnostics must not rebuild or validate QI"),
        ):
            report = self.report(fight)

        self.assertFalse(self.spatial_violations(report))
        self.assertEqual(
            pointer_ids, {identity: id(obj) for identity, obj in qi.objects.items()}
        )
        self.assertEqual(
            slot_ids, [None if obj is None else id(obj) for obj in qi.slots]
        )
        self.assertEqual(
            cell_ids,
            {cell: (id(value), id(value.state)) for cell, value in qi.cells.items()},
        )
        self.assertEqual(
            states_before, {cell: value.state for cell, value in qi.cells.items()}
        )
        self.assertEqual(checkpoint_before, dict(checkpoint))

    def test_pointer_canonical_actor_replacement_is_reported(self):
        fight, checkpoint = self.pointer_fixture()
        checkpoint._qi.objects[7].actor = fight.actors[-7]
        report = self.report(fight)
        self.assertTrue(
            any(
                row.invariant == "spatial.owner"
                for row in self.spatial_violations(report)
            )
        )

    def test_pointer_slot_snapshot_mismatch_is_reported(self):
        fight, checkpoint = self.pointer_fixture()
        index = next(
            i for i, value in enumerate(checkpoint["slots"]) if value is not None
        )
        checkpoint["slots"][index] = ["actor", 123456]
        report = self.report(fight)
        self.assertTrue(
            any(
                row.invariant == "spatial.checkpoint"
                for row in self.spatial_violations(report)
            )
        )

    def test_pointer_cell_snapshot_mismatch_is_reported(self):
        fight, checkpoint = self.pointer_fixture()
        row = next(row for row in checkpoint["cells"] if row["trove"]["keys"])
        row["trove"]["size"] += 1
        report = self.report(fight)
        self.assertTrue(
            any(
                row.invariant == "spatial.checkpoint"
                for row in self.spatial_violations(report)
            )
        )


if __name__ == "__main__":
    unittest.main()
