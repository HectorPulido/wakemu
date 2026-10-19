"""Initial enemy formations preserve at least one legal native escape step."""

import json
from pathlib import Path
import unittest

from wakfu_server.combat_arena_selection import compact_encounter
from wakfu_server.combat_geometry import prepare_geometry
from wakfu_server.combat_placement_footprints import covered_cells
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.combat.combat_actor_snapshot import native_actor_catalog
from wakfu_server.maps.dungeon_encounters import enemy_formation


ROOT = Path(__file__).resolve().parents[1]
JALATO_SECTIONS = ROOT / "test-fixtures/dungeons/jalato-native-sections.json"


def native_room_fixture(order=3):
    document = json.loads(JALATO_SECTIONS.read_text(encoding="utf8"))
    room = next(row for row in document["rooms"] if row["order"] == order)
    full = map_geometry(document["asset_map_id"])
    native_cells = {tuple(cell) for cell in full["cells"]}
    allowed = {tuple(cell) for cell in room["cells"]}
    if not allowed or not allowed <= native_cells:
        raise AssertionError("Dungeon room fixture is not a subset of native map cells")
    native_edges = {(tuple(a), tuple(b)) for a, b in full["edges"]}
    edges = {edge for edge in native_edges if edge[0] in allowed and edge[1] in allowed}
    geometry = prepare_geometry(
        {"map_id": document["asset_map_id"], "cells": allowed, "edges": edges}
    )
    return geometry, tuple(room["anchor"])


def legal_first_steps(geometry, result, player, radii):
    """Count native outgoing moves whose whole footprint clears other actors."""
    positions = [destination for _, destination in result["participant_positions"]]
    cells = set(result["cells"])
    by_xy = {cell[:2]: cell for cell in cells}
    occupied = [
        covered_cells(position, radius, cells, by_xy=by_xy)
        for position, radius in zip(positions, radii)
    ]
    player_cells = covered_cells(player, 0, cells, by_xy=by_xy)
    outgoing = geometry.outgoing
    counts = []
    for index, (position, radius) in enumerate(zip(positions, radii)):
        other_occupied = set(player_cells)
        for other_index, footprint in enumerate(occupied):
            if other_index != index:
                other_occupied.update(footprint)
        legal = 0
        for destination in outgoing.get(position, ()):
            try:
                target = covered_cells(destination, radius, cells, by_xy=by_xy)
            except ValueError:
                continue
            if target.isdisjoint(other_occupied):
                legal += 1
        counts.append(legal)
    return positions, occupied, counts


class InitialEnemyMobilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.geometry, cls.player = native_room_fixture()
        cls.originals = enemy_formation(
            {
                "map_id": cls.geometry.map_id,
                "cells": cls.geometry.cells,
                "edges": cls.geometry.edges,
            },
            cls.player,
            8,
            player_slots=6,
        )
        cls.native_roster = (44, 3, 3, 1, 41, 41)
        profiles = native_actor_catalog()["npc_profiles"]
        cls.native_radii = [
            profiles[str(ref)]["physical_radius"] for ref in cls.native_roster
        ]
        cls.native_originals = enemy_formation(
            {
                "map_id": cls.geometry.map_id,
                "cells": cls.geometry.cells,
                "edges": cls.geometry.edges,
            },
            cls.player,
            len(cls.native_roster),
            player_slots=6,
        )
        cls.mixed_roster = (42, 3, 3, 1, 41, 41)
        cls.mixed_radii = [
            profiles[str(ref)]["physical_radius"] for ref in cls.mixed_roster
        ]
        cls.mixed_originals = enemy_formation(
            {
                "map_id": cls.geometry.map_id,
                "cells": cls.geometry.cells,
                "edges": cls.geometry.edges,
            },
            cls.player,
            len(cls.mixed_roster),
            player_slots=6,
        )

    def encounter(self, radii, *, spread=True):
        return compact_encounter(
            {
                "map_id": self.geometry.map_id,
                "cells": self.geometry.cells,
                "edges": self.geometry.edges,
            },
            self.player,
            self.originals,
            minimum_cells=49,
            minimum_dimensions=(7, 7),
            spread_opponents=spread,
            automatic_cell_budget=2500,
            member_radii=radii,
        )

    def native_roster_encounter(self):
        return compact_encounter(
            {
                "map_id": self.geometry.map_id,
                "cells": self.geometry.cells,
                "edges": self.geometry.edges,
            },
            self.player,
            self.native_originals,
            minimum_cells=49,
            minimum_dimensions=(7, 7),
            spread_opponents=True,
            automatic_cell_budget=2500,
            member_radii=self.native_radii,
        )

    def mixed_roster_encounter(self):
        return compact_encounter(
            {
                "map_id": self.geometry.map_id,
                "cells": self.geometry.cells,
                "edges": self.geometry.edges,
            },
            self.player,
            self.mixed_originals,
            minimum_cells=49,
            minimum_dimensions=(7, 7),
            spread_opponents=True,
            automatic_cell_budget=2500,
            member_radii=self.mixed_radii,
        )

    def assert_native_footprints_and_edges(self, result, radii):
        positions, footprints, _ = legal_first_steps(
            self.geometry, result, self.player, radii
        )
        selected = set(result["cells"])
        self.assertTrue(selected <= set(self.geometry.cells))
        self.assertEqual(len(positions), len(radii))
        self.assertTrue(
            all(footprint <= selected for footprint in footprints),
            "Every initial actor must fit wholly on selected native cells",
        )
        occupied = set(covered_cells(self.player, 0, selected))
        for footprint in footprints:
            self.assertTrue(occupied.isdisjoint(footprint))
            occupied.update(footprint)
        native_edges = set(self.geometry.edges)
        self.assertTrue(set(result["edges"]) <= native_edges)
        self.assertTrue(
            all((a, b) in native_edges for a, b in result["edges"]),
            "Selection must not synthesize movement edges",
        )
        return positions, footprints

    def test_small_enemy_roster_has_a_native_first_step_for_each_member(self):
        radii = [0] * len(self.originals)
        result = self.encounter(radii)
        self.assert_native_footprints_and_edges(result, radii)
        _, _, steps = legal_first_steps(self.geometry, result, self.player, radii)
        self.assertTrue(
            all(count > 0 for count in steps),
            f"Initial small-actor formation traps members: legal first steps={steps}",
        )

    def test_mixed_three_by_three_and_small_actors_each_keep_a_native_exit(self):
        radii = self.mixed_radii
        result = self.mixed_roster_encounter()
        positions, footprints = self.assert_native_footprints_and_edges(result, radii)
        self.assertEqual(
            9, len(footprints[0]), "Radius one must retain its full 3x3 footprint"
        )
        _, _, steps = legal_first_steps(self.geometry, result, self.player, radii)
        self.assertTrue(
            all(count > 0 for count in steps),
            f"Mixed footprint formation traps members: legal first steps={steps}; positions={positions}",
        )

    def test_native_roster_profiles_have_mobile_nonadjacent_initial_footprints(self):
        result = self.native_roster_encounter()
        positions, footprints = self.assert_native_footprints_and_edges(
            result, self.native_radii
        )
        _, _, steps = legal_first_steps(
            self.geometry, result, self.player, self.native_radii
        )
        self.assertTrue(
            all(count > 0 for count in steps),
            f"Native roster {self.native_roster} has a trapped first-turn actor: {steps}",
        )
        for index, first in enumerate(footprints):
            for second in footprints[index + 1 :]:
                self.assertFalse(
                    any(
                        abs(a[0] - b[0]) + abs(a[1] - b[1]) <= 1
                        for a in first
                        for b in second
                    ),
                    f"Native actor footprints are touching: {positions}",
                )

    def test_dense_unspread_roster_keeps_feasible_original_positions(self):
        radii = [0] * len(self.originals)
        result = self.encounter(radii, spread=False)
        self.assert_native_footprints_and_edges(result, radii)
        self.assertEqual(
            list(self.originals),
            [source for source, _ in result["participant_positions"]],
        )
        self.assertEqual(
            list(self.originals),
            [destination for _, destination in result["participant_positions"]],
            "Non-spread arena selection must preserve feasible native actor positions",
        )


class DenseSpreadFallbackTests(unittest.TestCase):
    def test_spread_mode_keeps_all_actors_when_no_escape_cell_can_be_reserved(self):
        cells = {(x, y, 0) for x in range(3) for y in range(3)}
        edges = {
            (source, target)
            for source in cells
            for target in cells
            if abs(source[0] - target[0]) + abs(source[1] - target[1]) == 1
        }
        player = (1, 1, 0)
        originals = sorted(cells - {player})
        result = compact_encounter(
            {"map_id": 777, "cells": cells, "edges": edges},
            player,
            originals,
            cell_budget=9,
            spread_opponents=True,
        )
        positions = [destination for _, destination in result["participant_positions"]]
        self.assertEqual(cells, set(result["cells"]))
        self.assertEqual(8, len(positions))
        self.assertEqual(8, len(set(positions)))
        self.assertTrue(set(positions) <= cells - {player})
        self.assertEqual(8, len(set(result["placement"][1])))
        self.assertTrue(set(result["edges"]) <= edges)
        self.assertEqual(cells, set(positions) | {player})


if __name__ == "__main__":
    unittest.main()
