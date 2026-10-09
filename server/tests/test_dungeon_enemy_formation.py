"""Native terrain checks for party-safe dungeon encounter formations."""

import json
import os
from pathlib import Path
import unittest

from wakfu_server.combat_arena_selection import bounded_arena
from wakfu_server.combat_placement_cells import generate
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.maps.dungeon_encounters import enemy_formation, reachable_cells


def native_sections():
    configured = os.environ.get(
        "WAKFU_JALATO_NATIVE_SECTIONS_FIXTURE"
    ) or os.environ.get("WAKFU_JALATO_RUNTIME_CONFIG_FIXTURE")
    if configured:
        path = Path(configured)
    else:
        root = Path(__file__).resolve().parents[2]
        path = root / "server/test-fixtures/dungeons/jalato-native-sections.json"
        if not path.is_file():
            path = root / "server/test-fixtures/dungeons/jalato-runtime-config-v1.json"
    document = json.loads(path.read_text(encoding="utf8"))
    if "topology" in document:
        document = document["topology"]
    return document


class DungeonEnemyFormationTests(unittest.TestCase):
    def test_jalato_room_rosters_keep_native_party_and_enemy_slots_separate(self):
        sections = native_sections()
        geometry = map_geometry(1086)
        native_cells = {tuple(cell) for cell in geometry["cells"]}
        native_edges = {(tuple(start), tuple(end)) for start, end in geometry["edges"]}
        requested = ((1, 3), (2, 5), (3, 6))

        for room_order, npc_count in requested:
            with self.subTest(room=room_order, npc_count=npc_count):
                matches = [
                    room for room in sections["rooms"] if room["order"] == room_order
                ]
                self.assertEqual(1, len(matches))
                room = matches[0]
                anchor = tuple(room["anchor"])
                room_cells = {tuple(cell) for cell in room["cells"]}
                self.assertIn(anchor, room_cells)
                self.assertTrue(room_cells <= native_cells)
                room_edges = {
                    edge
                    for edge in native_edges
                    if edge[0] in room_cells and edge[1] in room_cells
                }
                room_geometry = {
                    "map_id": 1086,
                    "cells": sorted(room_cells),
                    "edges": sorted(room_edges),
                }
                npcs = enemy_formation(room_geometry, anchor, npc_count, player_slots=6)
                self.assertEqual(npc_count, len(npcs))
                self.assertEqual(npc_count, len(set(npcs)))
                self.assertTrue(set(npcs) <= room_cells)
                centroid = tuple(
                    sum(cell[axis] for cell in room_cells) / len(room_cells)
                    for axis in (0, 1)
                )
                self.assertLessEqual(
                    max(abs(npcs[0][axis] - centroid[axis]) for axis in (0, 1)), 3
                )

                six_player_slots = (anchor, *reachable_cells(room_geometry, anchor, 5))
                for party_size in (2, 6):
                    with self.subTest(party_size=party_size):
                        player_seeds = six_player_slots[:party_size]
                        self.assertEqual(party_size, len(set(player_seeds)))
                        self.assertTrue(set(player_seeds) <= room_cells)
                        self.assertFalse(set(player_seeds) & set(npcs))

                        arena = bounded_arena(room_geometry, anchor, npcs, radius=89)
                        self.assertEqual(1086, arena["map_id"])
                        self.assertTrue(set(player_seeds) <= arena["cells"])
                        self.assertTrue(set(npcs) <= arena["cells"])
                        placement = generate(
                            arena["cells"],
                            arena["edges"],
                            {0: player_seeds, 1: npcs},
                            slots_per_team=6,
                        )
                        self.assertTrue(set(player_seeds) <= placement[0])
                        self.assertTrue(set(npcs) <= placement[1])
                        self.assertEqual(6, len(placement[0]))
                        self.assertEqual(6, len(placement[1]))
                        self.assertFalse(placement[0] & placement[1])
                        self.assertTrue((placement[0] | placement[1]) <= arena["cells"])

    def test_formation_fails_when_native_room_cannot_fit_both_teams(self):
        cells = [(x, 0, 0) for x in range(7)]
        edges = [
            edge
            for x in range(6)
            for edge in (((x, 0, 0), (x + 1, 0, 0)), ((x + 1, 0, 0), (x, 0, 0)))
        ]
        geometry = {"map_id": 1086, "cells": cells, "edges": edges}
        with self.assertRaisesRegex(
            ValueError, "cannot separate party and enemy formations"
        ):
            enemy_formation(geometry, (0, 0, 0), 3, player_slots=6)

    def test_stacked_native_floors_keep_formation_on_safe_reachable_cells(self):
        geometry = map_geometry(545)
        native_cells = {tuple(cell) for cell in geometry["cells"]}
        stacked = {(-1, -15, 3), (-1, -15, 4)}
        self.assertTrue(stacked <= native_cells)

        # This native anchor sits on one of the stacked floors. Combat's
        # reachable-floor selector must ignore the disconnected alternate
        # height while keeping every chosen position on exported map cells.
        anchor = (-1, -15, 4)
        enemies = enemy_formation(geometry, anchor, 3, player_slots=6)
        self.assertEqual(3, len(enemies))
        self.assertTrue(set(enemies) <= native_cells)
        arena = bounded_arena(geometry, anchor, [enemies[0]], radius=89)
        self.assertIn(anchor, arena["cells"])
        self.assertTrue(set(enemies) <= arena["cells"])
        columns = [cell[:2] for cell in arena["cells"]]
        self.assertEqual(len(columns), len(set(columns)))

    def test_ambiguous_stacked_floor_cannot_be_a_combat_participant_anchor(self):
        lower = (-1, -15, 3)
        upper = (-1, -15, 4)
        origin = (-2, -15, 0)
        upper_steps = [(-2, -14, 4), (-1, -14, 4)]
        cells = [origin, lower, upper, *upper_steps, (-2, -15, 3)]
        edges = [
            (origin, lower),
            (lower, origin),
            (origin, upper_steps[0]),
            (upper_steps[0], origin),
            (upper_steps[0], upper_steps[1]),
            (upper_steps[1], upper_steps[0]),
            (upper_steps[1], upper),
            (upper, upper_steps[1]),
            (lower, (-2, -15, 3)),
            ((-2, -15, 3), lower),
        ]
        ambiguous_geometry = {"map_id": 545, "cells": cells, "edges": edges}
        with self.assertRaisesRegex(ValueError, "ambiguous reachable floor"):
            bounded_arena(ambiguous_geometry, lower, [origin], radius=12)


if __name__ == "__main__":
    unittest.main()
