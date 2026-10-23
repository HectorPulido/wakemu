"""Native empty-column LOS and path-mask semantics remain independent."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server.combat_arena_empty_gaps import (
    POLICY,
    TRANSPARENT_VOID_POLICY,
    native_empty_gap_indices,
    restored_gap_indices,
)
from wakfu_server.combat_qi_surfaces import NativeQISurfaces
from wakfu_server.combat_qi_snapshot import NativeQISnapshot
from wakfu_server.combat_wire import arena


class NativeEmptyGapTests(unittest.TestCase):
    def test_actual_crow_transparent_sentinel_keeps_native_los_and_path_independent(
        self,
    ):
        from wakfu_server.combat_crow_steel_scene_layout import reconstructed_crow_scene
        from wakfu_server.combat_qi_surface_catalog import native_qi_surfaces
        from wakfu_server.combat_qi_surface_selection import native_surface_indices
        from wakfu_server.combat_native_los_ray import topology_columns, cast_rays
        from wakfu_server.combat_casting_los import native_qi_h
        from wakfu_server.combat_qi_registry import NativeQIRegistry
        from wakfu_server.combat_sn_path import NativeSnColumns, native_sm_transitions

        geometry = json.loads(
            (
                Path(__file__).parent / "fixtures/ultimate_encounter_scene_recipes.json"
            ).read_text()
        )["maps"]["363"]
        scene = reconstructed_crow_scene(geometry)
        surfaces, columns = native_qi_surfaces(363), topology_columns(363)
        old = native_empty_gap_indices(surfaces, columns, scene["cells"])
        gaps = native_empty_gap_indices(
            surfaces, columns, scene["cells"], transparent_void=True
        )
        self.assertNotIn((-6, -14), old)
        self.assertEqual(gaps[(-6, -14)], 0)
        self.assertEqual(columns[-6, -14], ((-32768, 0, True),))
        self.assertEqual(scene["native_los_gap_policy"], TRANSPARENT_VOID_POLICY)
        candidate = arena(
            363,
            78,
            scene["cells"],
            {0: {(-6, -13, 88)}, 1: {scene["source"]}},
            surface_indices=native_surface_indices(surfaces, scene["cells"]),
            gap_surface_indices=gaps,
        )
        terrain = NativeQISnapshot(candidate)
        self.assertTrue(terrain.Z(-6, -14))
        physical = NativeSnColumns.from_published(363)
        source_column = physical.column(-6, -13)
        source_index = next(
            index
            for index, value in enumerate(source_column)
            if value.z == 88 and value.bld != -1
        )
        self.assertEqual(
            native_sm_transitions(
                source_index, source_column, physical.column(-6, -14), height=6, jump=1
            ),
            (),
        )
        self.assertNotIn((-6, -14, 88), scene["cells"])
        rays = cast_rays(
            363, (-6, -13, 88), (-6, -17, 88), source_height=6, target_height=6
        )
        self.assertTrue(any(clear and (-6, -14) in probes for clear, probes in rays))
        registry = NativeQIRegistry(candidate, [None] * 127)
        registry.capture_fresh_cell_topology([])

        def accepts():
            return any(
                clear
                and not any(
                    native_qi_h(
                        terrain,
                        x,
                        y,
                        88,
                        ordered_slots=registry.ordered_U,
                        visibility=lambda slot: True,
                        ignored=(),
                    )
                    for x, y in probes
                )
                for clear, probes in rays
            )

        self.assertTrue(accepts())
        slot = registry.register(
            dict(
                identity=("effect_area", 902),
                position=(-6, -14),
                radius=0,
                indexed=False,
                movement_blocking=True,
            )
        )
        self.assertFalse(accepts())
        registry.remove(slot, ("effect_area", 902))
        self.assertTrue(accepts())

    def test_actual_steel_ray_crosses_empty_gap_but_native_path_and_dynamic_qk_still_block(
        self,
    ):
        from wakfu_server.combat_crow_steel_scene_layout import (
            reconstructed_steel_scene,
        )
        from wakfu_server.combat_qi_surface_catalog import native_qi_surfaces
        from wakfu_server.combat_qi_surface_selection import native_surface_indices
        from wakfu_server.combat_native_los_ray import topology_columns, cast_rays
        from wakfu_server.combat_casting_los import native_qi_h
        from wakfu_server.combat_qi_registry import NativeQIRegistry
        from wakfu_server.combat_sn_path import NativeSnColumns, native_sm_transitions

        geometry = json.loads(
            (
                Path(__file__).parent / "fixtures/ultimate_encounter_scene_recipes.json"
            ).read_text()
        )["maps"]["959"]
        scene = reconstructed_steel_scene(geometry)
        gaps = native_empty_gap_indices(
            native_qi_surfaces(959), topology_columns(959), scene["cells"]
        )
        self.assertEqual(gaps[(-15, 3)], 0)
        self.assertNotIn((-15, 1), gaps)  # Original multi-surface solid column.
        arguments = dict(
            surface_indices=native_surface_indices(
                native_qi_surfaces(959), scene["cells"]
            ),
            border_cells=scene["native_border_cells"],
        )
        placement = {0: {(-13, 3, 0)}, 1: {scene["source"]}}
        baseline = arena(959, 78, scene["cells"], placement, **arguments)
        candidate = arena(
            959, 78, scene["cells"], placement, gap_surface_indices=gaps, **arguments
        )
        old, new = NativeQISnapshot(baseline), NativeQISnapshot(candidate)
        index = (-15 - new.x) + (3 - new.y) * new.width
        self.assertEqual((old.masks[index], new.masks[index]), (256, 512))
        self.assertTrue(old.Z(-15, 3))
        self.assertTrue(new.Z(-15, 3))
        self.assertEqual(old.R(-15, 3), new.R(-15, 3))
        self.assertNotIn((-15, 3, 0), scene["cells"])
        self.assertFalse(any((-15, 3, 0) in edge for edge in scene["edges"]))
        physical = NativeSnColumns.from_published(959)
        self.assertEqual(
            native_sm_transitions(
                0, physical.column(-14, 3), physical.column(-15, 3), height=6, jump=1
            ),
            (),
        )
        rays = cast_rays(
            959, (-13, 3, 0), (-17, 3, 0), source_height=6, target_height=6
        )
        self.assertTrue(any(clear and (-15, 3) in probes for clear, probes in rays))
        registry = NativeQIRegistry(candidate, [None] * 127)
        registry.capture_fresh_cell_topology([])

        def accepts(terrain, registry):
            return any(
                clear
                and not any(
                    native_qi_h(
                        terrain,
                        x,
                        y,
                        0,
                        ordered_slots=registry.ordered_U,
                        visibility=lambda slot: True,
                        ignored=(),
                    )
                    for x, y in probes
                )
                for clear, probes in rays
            )

        original_registry = NativeQIRegistry(baseline, [None] * 127)
        original_registry.capture_fresh_cell_topology([])
        self.assertFalse(accepts(old, original_registry))
        self.assertTrue(accepts(new, registry))
        slot = registry.register(
            dict(
                identity=("effect_area", 901),
                position=(-15, 3),
                radius=0,
                indexed=False,
                movement_blocking=True,
            )
        )
        self.assertFalse(accepts(new, registry))
        registry.remove(slot, ("effect_area", 901))
        self.assertTrue(accepts(new, registry))
        self.assertEqual(baseline["cell_flags"], candidate["cell_flags"])

    def test_only_unambiguous_finite_native_empty_columns_are_selected(self):
        columns = [
            [0, 0, [[0, 0]]],
            [1, 0, [[0, -1]]],
            [2, 0, [[0, -1]]],
            [3, 0, [[-32768, -1]]],
            [4, 0, [[0, -1], [2, -1]]],
            [5, 0, [[0, 0]]],
        ]
        surfaces = NativeQISurfaces(
            dict(
                schema="native-QI-Vy-columns-v1",
                map_id=959,
                source_sha256="0" * 64,
                chunks=[dict(x=0, y=0, width=6, height=1, columns=columns)],
            ),
            map_id=959,
            source_sha256="0" * 64,
        )
        static = {
            (0, 0): ((0, 0, False),),
            (1, 0): ((0, 0, False),),
            (2, 0): ((0, 10, False),),
            (3, 0): ((-32768, 0, False),),
            (4, 0): ((0, 0, False),),
            (5, 0): ((0, 0, False),),
        }
        self.assertEqual(
            native_empty_gap_indices(surfaces, static, ((0, 0, 0), (5, 0, 0))),
            {(1, 0): 0},
        )
        self.assertEqual(
            native_empty_gap_indices(
                surfaces, static, ((0, 0, 0), (5, 0, 0)), transparent_void=True
            ),
            {(1, 0): 0},
        )
        static[3, 0] = ((-32768, 0, True),)
        self.assertEqual(
            native_empty_gap_indices(
                surfaces, static, ((0, 0, 0), (5, 0, 0)), transparent_void=True
            ),
            {(1, 0): 0, (3, 0): 0},
        )
        self.assertEqual(
            native_empty_gap_indices(surfaces, static, ((0, 0, 0), (5, 0, 0))),
            {(1, 0): 0},
        )
        static[3, 0] = ((-32768, 1, True),)
        self.assertEqual(
            native_empty_gap_indices(
                surfaces, static, ((0, 0, 0), (5, 0, 0)), transparent_void=True
            ),
            {(1, 0): 0},
        )
        static[1, 0] = ((1, 0, False),)
        self.assertEqual(
            native_empty_gap_indices(surfaces, static, ((0, 0, 0), (5, 0, 0))), {}
        )
        with self.assertRaisesRegex(ValueError, "bounds"):
            native_empty_gap_indices(surfaces, static, ((0, 0, 0), (32767, 1, 0)))

    def test_ordinary_default_is_opaque_and_gap_input_cannot_add_selected_cells(self):
        cells = ((0, 0, 0), (2, 0, 0))
        arguments = dict(
            map_id=959,
            instance_id=1,
            cells=cells,
            placement={0: {cells[0]}, 1: {cells[1]}},
        )
        self.assertEqual(arena(**arguments)["cell_masks"], [0, 256, 0])
        self.assertEqual(
            arena(**arguments, gap_surface_indices={(1, 0): 0})["cell_masks"],
            [0, 512, 0],
        )
        for invalid in ({(0, 0): 0}, {(3, 0): 0}, {(1, 0): 64}, {(1, 0): True}):
            with self.assertRaisesRegex(ValueError, "gap"):
                arena(**arguments, gap_surface_indices=invalid)

    def test_durable_gap_indices_are_revalidated_against_native_source(self):
        record = dict(native_los_gap_policy=POLICY, native_los_gap_surfaces=[[1, 0, 0]])
        with patch(
            "wakfu_server.combat_arena_empty_gaps.selected_gap_indices",
            return_value={(1, 0): 0},
        ):
            self.assertEqual(
                restored_gap_indices(959, ((0, 0, 0), (2, 0, 0)), record), {(1, 0): 0}
            )
            record["native_los_gap_surfaces"] = [[1, 0, 1]]
            with self.assertRaisesRegex(ValueError, "Persisted"):
                restored_gap_indices(959, ((0, 0, 0), (2, 0, 0)), record)
        record = dict(
            native_los_gap_policy=TRANSPARENT_VOID_POLICY,
            native_los_gap_surfaces=[[1, 0, 0]],
        )
        with patch(
            "wakfu_server.combat_arena_empty_gaps.selected_gap_indices",
            return_value={(1, 0): 0},
        ) as select:
            self.assertEqual(
                restored_gap_indices(363, ((0, 0, 0), (2, 0, 0)), record), {(1, 0): 0}
            )
            select.assert_called_once_with(
                363, ((0, 0, 0), (2, 0, 0)), TRANSPARENT_VOID_POLICY
            )
        with self.assertRaisesRegex(ValueError, "declared policy"):
            restored_gap_indices(
                959, ((0, 0, 0), (2, 0, 0)), dict(native_los_gap_surfaces=[[1, 0, 0]])
            )
