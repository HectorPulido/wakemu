"""Local path/displacement lookups must not build the whole QI slot view."""
import unittest
from types import SimpleNamespace
from unittest.mock import PropertyMock, patch


class LocalQISlotReadTests(unittest.TestCase):
    def test_path_displacement_and_mutation_use_fresh_single_slot_reads(self):
        from test_combat_pointer_qi_projection import PointerQIProjectionTests
        from test_combat_tackle_movement import Authority
        from wakfu_server.combat_displacement import NativeDisplacementHandler
        from wakfu_server.combat_valid_path_policy import admitted_route
        from wakfu_server.combat_pointer_qi_registry import PointerRegistryCompatibility

        fight, registry, actor, other = PointerQIProjectionTests().real_registry()
        fight.ready(3)
        fight.native_rail_movement_authority = Authority()
        for member in (actor, other):
            member.effect_stats = {7: 0, 8: 0}
            member.effective_level = 60
            member.physical_radius = 0
        fight.walkable = {(x, 0, 0) for x in range(4)}
        fight.edges = {
            (left, right)
            for left in fight.walkable
            for right in fight.walkable
            if abs(left[0] - right[0]) == 1
        }
        fight.native_qi_movement_override = False
        fight.native_qi_ignored_slots = []

        # The existing compatibility property traverses every cell to produce
        # all 127 rows. These local consumers should need only the requested QK.
        with patch.object(
            PointerRegistryCompatibility,
            "slots",
            new_callable=PropertyMock,
            side_effect=AssertionError("whole-QI slot projection used"),
        ), patch.object(
            PointerRegistryCompatibility,
            "snapshot",
            side_effect=AssertionError("whole-QI occupancy snapshot used"),
        ):
            self.assertIsNone(admitted_route(fight, actor.id, (1, 0, 0), limit=2))

            registry.qi.move_actor(other, (2, 0, 0))
            fight.native_pointer_checkpoint.publish()
            route = admitted_route(fight, actor.id, (1, 0, 0), limit=2)
            self.assertEqual(route, ((1, 0, 0),))

            handler = SimpleNamespace(fight=fight)
            self.assertTrue(
                NativeDisplacementHandler._teleport_free(handler, actor, (1, 0, 0))
            )
            blocked, identity = NativeDisplacementHandler._forced_obstruction(
                handler, actor, (2, 0, 0)
            )
            self.assertEqual((blocked, identity), (True, other.id))

            # A later QK mutation is visible without retaining a projected row.
            registry.qi.move_actor(other, (3, 0, 0))
            fight.native_pointer_checkpoint.publish()
            self.assertTrue(
                NativeDisplacementHandler._teleport_free(handler, actor, (2, 0, 0))
            )


if __name__ == "__main__":
    unittest.main()
