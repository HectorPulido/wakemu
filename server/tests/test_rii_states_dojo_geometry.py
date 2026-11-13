"""State lesson marker selection against installed dojo geometry and QI."""
import unittest

from wakfu_server.achievements.rii_states_contract import choose_markers, _marker_los
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_terrain import local_arena
from wakfu_server.combat_geometry_snapshot import freeze_terrain
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
)


class StateDojoGeometryTests(unittest.TestCase):
    def test_unrelocated_native_sack_uses_real_dojo_placement(self):
        start, sack = (-1, -16, 0), (-1, -15, 0)
        terrain = local_arena(
            1388, 7, start, [sack], relocate_monsters=False, ordinary_npc_placement=True
        )
        self.assertIn(start, terrain["validated_cells"])
        self.assertIn(sack, terrain["validated_cells"])
        self.assertEqual(terrain.get("participant_positions", []), [])

    def test_markers_on_installed_dojo_and_real_qi(self):
        start, sack = (0, -16, 0), (1, -16, 0)
        terrain = local_arena(1388, 7, start, sack, relocate_monsters=False)
        owner = Actor(7, 0, start, 100, 6, 3, 100, 1, 2, True)
        target = Actor(-7, 1, sack, 100, 6, 3, 10, 1)
        for actor in (owner, target):
            actor.physical_radius = 0
            actor.native_los_height = 6
        fight = Fight(
            78,
            [owner, target],
            terrain["validated_cells"],
            {0: {start}, 1: {sack}},
            terrain["valid_edges"],
        )
        fight.native_qi_snapshot = {
            key: terrain[key] for key in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(
            terrain["native_qi_surface_provenance"]
        )
        freeze_terrain(fight)
        initialize_global_pv_collections(fight, (7, -7))
        install_fresh_actor_slots(
            fight, prepare_fresh_actor_slots(fight, physical_radii={7: 0, -7: 0})
        )
        markers = choose_markers(fight, target, owner_id=7)
        self.assertEqual(len(set(markers)), 2)
        for cell in markers:
            self.assertTrue(_marker_los(fight, 7, -7, cell))
        self.assertEqual(owner.position, start)


if __name__ == "__main__":
    unittest.main()
