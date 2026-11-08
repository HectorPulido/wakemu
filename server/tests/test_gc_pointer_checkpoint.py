"""Actual pointer checkpoint admission preserves live and detached native roots."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from test_combat_pointer_qi_projection import PointerQIProjectionTests
from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint
from wakfu_server.combat_state import Actor


class PointerCheckpointGCTests(unittest.TestCase):
    def fixture(self):
        fight, registry, actor, other = PointerQIProjectionTests().real_registry()
        return fight, registry, actor, other

    def admitted(self, fight):
        roots = []
        checkpoint = fight.native_pointer_checkpoint
        qi = checkpoint._qi
        before = deepcopy(dict(checkpoint))
        topology = (qi.slots, qi.cells, qi.anchors)
        with patch.object(
            NativePointerCheckpoint,
            "validate",
            side_effect=AssertionError("mutating validation"),
        ):
            self.assertTrue(boundary._canonical_graph(fight, pending_roots=roots))
        self.assertEqual(dict(checkpoint), before)
        for actual, expected in zip((qi.slots, qi.cells, qi.anchors), topology):
            self.assertIs(actual, expected)
        return roots

    def test_actual_live_checkpoint_preserves_aliases_without_full_effect_roots(self):
        fight, _, actor, other = self.fixture()
        roots = self.admitted(fight)
        self.assertEqual(roots, [])
        qi = fight.native_pointer_checkpoint._qi
        self.assertIs(qi.objects[actor.id].actor, actor)
        self.assertIs(qi.objects[other.id].actor, other)
        clone = deepcopy(fight)
        self.assertEqual(self.admitted(clone), [])
        self.assertIs(
            clone.native_pointer_checkpoint._qi.objects[actor.id].actor,
            clone.actors[actor.id],
        )

    def test_actual_pending_constructor_payload_remains_an_operative_root(self):
        fight, registry, _, _ = self.fixture()
        actor = Actor(-9, 1, (2, 0, 0), 20, 6, 3, 5, 1)
        actor.native_physical_position = actor.position
        actor.physical_radius = 0
        actor.native_obstacle_id = -1
        registry.register_constructor_actor(actor)
        fight.native_pointer_checkpoint.publish()
        roots = self.admitted(fight)
        self.assertNotIn(actor.id, fight.actors)
        self.assertTrue(any(root is vars(actor) for root in roots))
        self.assertEqual(len(roots), 1)
        self.assertIs(roots[0], vars(actor))
        self.assertIs(
            fight.native_pointer_checkpoint._qi.objects[actor.id].actor, actor
        )

    def test_removed_slot_preserves_historical_qk_but_foreign_binding_rejects(self):
        fight, _, _, other = self.fixture()
        checkpoint = fight.native_pointer_checkpoint
        qi = checkpoint._qi
        qi.remove(qi.objects[other.id])
        checkpoint.publish()
        pointer = qi.objects[other.id]
        self.assertEqual(self.admitted(fight), [])
        self.assertIs(qi.objects[other.id], pointer)
        self.assertIs(pointer.actor, other)
        self.assertFalse(any(slot is pointer for slot in qi.slots))
        # OUT/current-slot absence does not dispose the native pointer; retained
        # 937 removal can still register it. Replacing its owner is not valid.
        qi.fight = deepcopy(fight)
        self.assertFalse(boundary._canonical_graph(fight))


if __name__ == "__main__":
    unittest.main()
