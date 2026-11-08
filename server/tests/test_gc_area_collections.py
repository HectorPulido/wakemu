"""GC understands native area storage without following weak membership owners."""
from copy import deepcopy
import unittest
from test_gc_owned_collections import OwnedCollectionGCTests
from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_retained_collections import (
    RetainedCollections,
    bound_area_collections,
)
from wakfu_server.combat_pointer_qi_actor import ActualActorQI, AreaQK
from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint


class AreaCollectionGCTests(unittest.TestCase):
    def fixture(self):
        _, fight, runtime, dead, uid = OwnedCollectionGCTests().fixture()
        for actor in fight.actors.values():
            actor.native_physical_position = actor.position
        checkpoint = NativePointerCheckpoint(ActualActorQI(fight))
        row = OwnedAreaRow(
            uid=901,
            reference=1759,
            native_area_contract="faY",
            native_running_effect_manager=True,
            cell=(2, 2, 0),
            native_obstacle_id=-1,
            state_ledger=StateLedger(901),
        )
        fight.native_effect_areas[901] = row
        fight.area_alias = row
        pointer = AreaQK(row)
        checkpoint._qi.area_objects[901] = pointer
        checkpoint._qi.movement_blocking[id(pointer)] = False
        checkpoint.publish()
        fight.native_pointer_checkpoint = checkpoint
        self.assertTrue(
            bound_area_collections(vars(fight), fight.native_retained_records.owner)
        )
        return deepcopy(fight), fight, runtime, dead, uid, row

    def test_area_ledger_alias_and_pointer_sources_survive_unrelated_sweep(self):
        previous, fight, runtime, dead, uid, row = self.fixture()
        checkpoint = fight.native_pointer_checkpoint
        self.assertTrue(boundary._canonical_graph(fight))
        projected, roots = boundary.planning_snapshot(fight)
        self.assertTrue(
            any(root.get("uid") == 901 for root in roots if type(root) is dict)
        )
        boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertNotIn(uid, fight.native_retained_records)
        self.assertIs(fight.native_effect_areas[901], row)
        self.assertIs(fight.area_alias, row)
        self.assertIs(checkpoint._qi.area_objects[901].row, row)
        self.assertEqual(row["state_ledger"].entries, ())

    def test_alien_area_owner_is_rejected_without_consuming_source(self):
        previous, fight, runtime, _, uid, row = self.fixture()
        foreign = RetainedCollections()
        foreign.area_sources["native_effect_areas"][901] = row
        self.assertFalse(boundary._canonical_graph(fight))
        boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertIn(uid, fight.native_retained_records)
        self.assertIs(fight.native_effect_areas[901], row)

    def test_pending_ack_defers_then_native_area_graph_collects_on_retry(self):
        previous, fight, runtime, _, uid, row = self.fixture()
        runtime.awaiting_ack = fight.turn_id
        boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertIn(uid, fight.native_retained_records)
        candidate, resumed = deepcopy((fight, runtime))
        resumed.awaiting_ack = None
        boundary.prepare_retired_gc(fight, candidate, resumed, ())
        self.assertNotIn(uid, candidate.native_retained_records)
        self.assertIs(candidate.area_alias, candidate.native_effect_areas[901])
        self.assertIsNot(candidate.area_alias, row)


if __name__ == "__main__":
    unittest.main()
