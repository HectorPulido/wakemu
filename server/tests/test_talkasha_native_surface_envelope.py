"""Original room surfaces retain physical QI without new movement edges."""
import json
from pathlib import Path
import unittest


class TalKashaNativeSurfaceEnvelopeTests(unittest.TestCase):
    def test_isolated_native_surface_restores_terrain_los_without_connecting_rooms(
        self,
    ):
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_talkasha_scene,
        )
        from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene
        from wakfu_server.combat_native_los_ray import cast_rays
        from wakfu_server.combat_casting_los import native_qi_h
        from wakfu_server.combat_qi_snapshot import NativeQISnapshot

        root = Path(__file__).resolve().parents[2]
        geometry = json.loads(
            (
                root
                / ".runtime/parallel-readiness-20261021/supreme-entry-staging/map-1400.json"
            ).read_text()
        )
        scene = reconstructed_talkasha_scene(geometry)
        isolated = (0, -37, -22)
        original_cells = set(map(tuple, geometry["cells"]))
        original_edges = {(tuple(a), tuple(b)) for a, b in geometry["edges"]}
        self.assertIn(isolated, original_cells)
        self.assertIn(isolated, scene["cells"])
        self.assertEqual(scene["isolated_native_surfaces"], (isolated,))
        self.assertFalse(any(isolated in edge for edge in original_edges))
        self.assertFalse(any(isolated in edge for edge in scene["edges"]))
        old_cells = set(scene["cells"]) - {isolated}
        self.assertEqual(len(old_cells), 548)
        self.assertEqual(
            scene["edges"],
            frozenset(
                (a, b) for a, b in original_edges if a in old_cells and b in old_cells
            ),
        )
        self.assertTrue(
            any(cell[0] >= 149 and cell[2] == -22 for cell in original_cells)
        )
        self.assertFalse(any(cell[0] >= 149 for cell in scene["cells"]))
        self.assertNotIn(isolated, scene["party_placement_cells"])

        character = dict(id=7, map_id=1400, x=0, y=-34, z=-22)
        member = dict(id=-200, ref=5500, map_id=1400, x=1, y=-33, z=-22)
        selected = prepare_encounter_scene(
            character, [member], dict(map_id=1400, instance_id=78), layout=scene
        )
        qi = NativeQISnapshot(selected)
        index = (-37 - qi.y) * qi.width + (0 - qi.x)
        self.assertEqual(qi.masks[index] & 63, 0)  # The actual sole native Vy index.
        self.assertFalse(qi.masks[index] & 256)
        # Terrain-only fcr/QI.h check: no actors or QK obstacles are invented.
        rays = cast_rays(
            1400, (0, -35, -22), (0, -38, -22), source_height=6, target_height=6
        )

        def terrain_blocks(x, y):
            return native_qi_h(
                qi,
                x,
                y,
                0,
                ordered_slots=lambda x, y: (),
                visibility=lambda slot: None,
                ignored=frozenset(),
            )

        self.assertFalse(terrain_blocks(0, -37))
        self.assertTrue(
            any(
                clear and not any(terrain_blocks(x, y) for x, y in probes)
                for clear, probes in rays
            )
        )
