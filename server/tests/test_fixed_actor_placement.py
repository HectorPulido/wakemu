"""Fixed source actors reserve native bodies without moving ordinary scenes."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_arena_selection import full_room_encounter
from wakfu_server.combat_fixed_actor_placement import (
    declarations,
    member_positions,
    bind_initial_directions,
)
from wakfu_server.combat_placement_footprints import covered_cells


class FixedActorPlacementTests(unittest.TestCase):
    def geometry(self):
        cells = {(x, y, 0) for x in range(12) for y in range(12)}
        edges = {
            (c, (c[0] + dx, c[1] + dy, 0))
            for c in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (c[0] + dx, c[1] + dy, 0) in cells
        }
        return dict(map_id=1, cells=cells, edges=edges)

    def descriptor(self):
        return dict(
            fixed_actor_placements=[
                dict(
                    reference=71,
                    cell=[9, 2, 0],
                    direction=5,
                    source=dict(
                        kind="original_native_marker",
                        uri="test-native-marker",
                        sha256="a" * 64,
                    ),
                )
            ]
        )

    def test_fixed_body_precedes_party_and_other_members_including_reserved_arrival(
        self,
    ):
        g = self.geometry()
        members = [(3, 3, 0), (4, 3, 0), (5, 3, 0)]
        body = covered_cells((9, 2, 0), 1, g["cells"])
        for origin in ((1, 10, 0), (9, 2, 0)):
            with self.subTest(origin=origin):
                result = full_room_encounter(
                    g,
                    origin,
                    members,
                    member_radii=(1, 0, 0),
                    player_slots=3,
                    placement_ground_cells=g["cells"],
                    fixed_member_positions={0: (9, 2, 0)},
                )
                self.assertEqual(
                    result["participant_positions"][0], ((3, 3, 0), (9, 2, 0))
                )
                self.assertFalse(body.intersection(result["party_reserved_cells"]))
                other = [
                    destination
                    for _, destination in result["participant_positions"][1:]
                ]
                self.assertFalse(body.intersection(other))
                self.assertEqual(len(set(other)), 2)
                self.assertEqual(set(result["cells"]), g["cells"])
                if origin in body:
                    self.assertEqual(
                        result["participant_player_position"][0], list(origin)
                    )
                    self.assertNotIn(
                        tuple(result["participant_player_position"][1]), body
                    )

    def test_unique_initial_reference_and_native_facing_are_preserved(self):
        desc = self.descriptor()
        cells = self.geometry()["cells"]
        self.assertEqual(
            member_positions(desc, [{"ref": 72}, {"ref": 71}], room_cells=cells),
            {1: (9, 2, 0)},
        )
        actor = SimpleNamespace(
            controlled=False,
            position=(9, 2, 0),
            direction=1,
            native_fight_property_counts={51: 1},
        )
        bind_initial_directions(
            SimpleNamespace(actors={-3: actor}), desc, {-3: {"ref": 71}}
        )
        self.assertEqual(actor.direction, 5)
        self.assertEqual(actor.native_fight_property_counts, {51: 1})
        for members in ([{"ref": 72}], [{"ref": 71}, {"ref": 71}]):
            with self.assertRaisesRegex(ValueError, "one admitted initial actor"):
                member_positions(desc, members, room_cells=cells)
        desc["fixed_actor_placements"][0]["cell"] = [99, 99, 0]
        with self.assertRaises(ValueError):
            declarations(desc, room_cells=cells)

    def test_ordinary_formation_is_unchanged_without_an_opt_in(self):
        g = self.geometry()
        kwargs = dict(
            member_radii=(1, 0), player_slots=3, placement_ground_cells=g["cells"]
        )
        ordinary = full_room_encounter(g, (1, 10, 0), [(4, 4, 0), (5, 4, 0)], **kwargs)
        self.assertEqual(
            ordinary,
            full_room_encounter(
                g,
                (1, 10, 0),
                [(4, 4, 0), (5, 4, 0)],
                fixed_member_positions={},
                **kwargs
            ),
        )

    def test_authored_native_body_can_use_nonordinary_ground_without_relaxing_other_actors(
        self,
    ):
        g = self.geometry()
        body = covered_cells((9, 2, 0), 1, g["cells"])
        ground = g["cells"] - body
        result = full_room_encounter(
            g,
            (1, 10, 0),
            [(3, 3, 0), (4, 3, 0)],
            member_radii=(1, 0),
            player_slots=3,
            placement_ground_cells=ground,
            fixed_member_positions={0: (9, 2, 0)},
        )
        self.assertEqual(result["participant_positions"][0][1], (9, 2, 0))
        self.assertTrue(set(result["party_reserved_cells"]) <= ground)
        self.assertIn(result["participant_positions"][1][1], ground)
        self.assertFalse(body & set(result["party_reserved_cells"]))
        ordinary = full_room_encounter(
            g,
            (1, 10, 0),
            [(3, 3, 0), (4, 3, 0)],
            member_radii=(1, 0),
            player_slots=3,
            placement_ground_cells=ground,
        )
        self.assertTrue(
            all(target in ground for _, target in ordinary["participant_positions"])
        )
        with self.assertRaisesRegex(ValueError, "overlaps an initial native obstacle"):
            full_room_encounter(
                g,
                (1, 10, 0),
                [(3, 3, 0), (4, 3, 0)],
                member_radii=(1, 0),
                placement_ground_cells=ground,
                fixed_member_positions={0: (9, 2, 0)},
                reserved_cells={(9, 2, 0)},
            )
        missing = dict(
            g,
            cells=g["cells"] - {(10, 3, 0)},
            edges={edge for edge in g["edges"] if (10, 3, 0) not in edge},
        )
        with self.assertRaisesRegex(
            ValueError, "footprint exceeds selected native terrain"
        ):
            full_room_encounter(
                missing,
                (1, 10, 0),
                [(3, 3, 0), (4, 3, 0)],
                member_radii=(1, 0),
                placement_ground_cells=ground,
                fixed_member_positions={0: (9, 2, 0)},
            )
