"""No-argument eMU path existence uses physical topology, never paid movement."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_conditions import ConditionContext, evaluate_condition
from wakfu_server.combat_sn_path import NativePhysicalSurface
from wakfu_server.combat_valid_path_native import (
    NativeValidPathSearch,
    native_default_valid_path,
)


class NativeValidPathTests(unittest.TestCase):
    def search(self, cells, *, blocked=(), radius=0, height=6, jump=4, rows=None):
        columns = (
            {
                cell[:2]: (NativePhysicalSurface(cell[2], 0, 0, 0, 1, False),)
                for cell in cells
            }
            if rows is None
            else rows
        )
        return NativeValidPathSearch(
            column=lambda x, y: columns.get((x, y)),
            blocked=lambda x, y, z: (x, y) in blocked,
            contains=lambda x, y: (x, y) in columns,
            height=height,
            radius=radius,
            jump=jump,
        )

    def test_no_argument_condition_uses_default_search_beyond_two_steps(self):
        cells = {(x, 0, 0) for x in range(8)}
        search = self.search(cells)
        seen = []

        def query(options, limit):
            seen.append((options, limit))
            return search((0, 0, 0), (7, 0, 0))

        self.assertTrue(
            evaluate_condition(
                "HasValidPathToTarget()", ConditionContext({}, valid_path_query=query)
            )
        )
        self.assertEqual(seen, [(None, None)])

    def test_occupied_endpoint_and_intermediate_blockers_do_not_get_excluded(self):
        cells = {(x, 0, 0) for x in range(5)}
        for blocked in ({(4, 0)}, {(2, 0)}):
            self.assertFalse(self.search(cells, blocked=blocked)((0, 0, 0), (4, 0, 0)))
        # Own occupied source is not a destination; native Sn may leave it.
        self.assertTrue(self.search(cells, blocked={(0, 0)})((0, 0, 0), (4, 0, 0)))
        self.assertFalse(self.search(cells, blocked={(0, 0)})((0, 0, 0), (0, 0, 0)))

    def test_detour_requires_real_physical_columns_and_complete_endpoint_altitude(self):
        cells = {(x, y, 0) for x in range(4) for y in range(2)}
        self.assertTrue(self.search(cells, blocked={(1, 0)})((0, 0, 0), (3, 0, 0)))
        self.assertFalse(self.search(cells)((0, 0, 0), (3, 0, 1)))
        self.assertFalse(self.search({(0, 0, 0), (2, 0, 0)})((0, 0, 0), (2, 0, 0)))

    def test_jump_and_actual_ceiling_restrict_path(self):
        cells = {(0, 0, 0), (1, 0, 5)}
        self.assertFalse(self.search(cells)((0, 0, 0), (1, 0, 5)))
        self.assertTrue(self.search(cells, jump=5)((0, 0, 0), (1, 0, 5)))
        floor = NativePhysicalSurface(0, 0, 0, 0, 1, False)
        ceiling = NativePhysicalSurface(4, -1, 0, 0, 1, False)
        rows = {(0, 0): (floor,), (1, 0): (floor, ceiling)}
        self.assertFalse(self.search(cells, rows=rows)((0, 0, 0), (1, 0, 0)))

    def test_large_mover_needs_translated_footprint_and_same_native_height(self):
        cells = {(x, y, 0) for x in range(5) for y in range(3)}
        search = self.search(cells, radius=1)
        self.assertTrue(search((1, 1, 0), (3, 1, 0)))
        self.assertFalse(search((1, 1, 0), (4, 1, 0)))
        self.assertFalse(
            self.search(cells, radius=1, blocked={(3, 0)})((1, 1, 0), (3, 1, 0))
        )

    def test_native_result_buffer_and_search_cap_are_not_unbounded(self):
        cells = {(x, 0, 0) for x in range(260)}
        self.assertTrue(self.search(cells)((0, 0, 0), (127, 0, 0)))
        self.assertFalse(self.search(cells)((0, 0, 0), (128, 0, 0)))
        self.assertFalse(self.search(cells)((0, 0, 0), (259, 0, 0)))

    def test_native_goal_slot_survives_full_node_buffer_before_discovery(self):
        # Thirty-two floors per intermediate column fill MAX_NODES before
        # discovery of the final column; Sn reserved its goal So beforehand.
        floor = lambda z: NativePhysicalSurface(z, 0, 0, 0, 1, False)
        rows = {(x, 0): tuple(floor(z) for z in range(0, 64, 2)) for x in range(1, 33)}
        rows[0, 0] = rows[33, 0] = (floor(0),)
        self.assertTrue(
            self.search((), rows=rows, height=1, jump=1000)((0, 0, 0), (33, 0, 0))
        )

    def test_unknown_physics_and_missing_qi_boolean_are_not_false(self):
        with self.assertRaisesRegex(ValueError, "movement authority"):
            self.search({(0, 0, 0)}, height=None)
        search = self.search({(0, 0, 0), (1, 0, 0)})
        search.blocked = lambda *args: None
        with self.assertRaisesRegex(ValueError, "QI.g boolean"):
            search((0, 0, 0), (1, 0, 0))

    def test_actual_complete_and_pointer_registries_share_flags_without_paying_mp(self):
        from test_combat_valid_path_policy import ValidPathPolicyTests
        from test_combat_pointer_qi_projection import PointerQIProjectionTests

        legacy, actor = ValidPathPolicyTests().fixture()
        pointer, _, pointer_actor, _ = PointerQIProjectionTests().real_registry()
        for fight, actor in ((legacy, actor), (pointer, pointer_actor)):
            with self.subTest(pointer=hasattr(fight, "native_pointer_checkpoint")):
                actor.native_los_height, actor.native_jump_height = 6, 4
                actor.mp = 0
                provenance = {"map_id": 363}
                fight.native_qi_surface_provenance = provenance
                rows = {
                    cell[:2]: (NativePhysicalSurface(cell[2], 0, 0, 0, 1, False),)
                    for cell in fight.walkable
                }
                columns = SimpleNamespace(column=lambda x, y: rows.get((x, y)))
                target = next(
                    other.position
                    for other in fight.actors.values()
                    if other.id != actor.id
                )
                with patch(
                    "wakfu_server.combat_qi_surface_catalog.native_qi_surface_provenance",
                    return_value=provenance,
                ), patch(
                    "wakfu_server.combat_sn_path.NativeSnColumns.from_published",
                    return_value=columns,
                ):
                    self.assertFalse(native_default_valid_path(fight, actor, target))
                    fight.native_qi_movement_override = True
                    self.assertTrue(native_default_valid_path(fight, actor, target))
                    self.assertEqual(actor.mp, 0)
                    self.assertEqual(actor.position, (0, 0, 0))
                    # Terrain rejection precedes the override in native QI.g.
                    arena = fight.native_qi_snapshot
                    index = (
                        (target[1] - arena["y"]) * arena["width"]
                        + target[0]
                        - arena["x"]
                    )
                    arena["cell_masks"][index] = 768
                    self.assertFalse(native_default_valid_path(fight, actor, target))
                    self.assertEqual(actor.mp, 0)


if __name__ == "__main__":
    unittest.main()
