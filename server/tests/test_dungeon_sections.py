import copy
import unittest
from wakfu_server.dungeon_sections import derive_sections


class DungeonSectionTests(unittest.TestCase):
    def setUp(self):
        self.geometry = dict(
            map_id=1,
            cells=[
                [0, 0, 0],
                [1, 0, 0],
                [10, 0, 0],
                [11, 0, 0],
                [20, 0, 0],
                [21, 0, 0],
                [50, 0, 0],
            ],
            edges=[
                [[0, 0, 0], [1, 0, 0]],
                [[10, 0, 0], [11, 0, 0]],
                [[20, 0, 0], [21, 0, 0]],
            ],
        )
        self.entry = dict(map_id=1, x=0, y=0, z=0)
        self.doors = []
        for identity, start, end in [(1, 1, 10), (2, 11, 0), (3, 11, 20), (4, 21, 10)]:
            self.doors.append(
                dict(
                    id=identity,
                    map_id=1,
                    x=start,
                    y=0,
                    z=0,
                    destinations=[
                        dict(
                            destination_id=identity + 100,
                            map_id=1,
                            x=end,
                            y=0,
                            z=0,
                            criterion="allowed",
                        )
                    ],
                )
            )

    def derive(self, count=3):
        return derive_sections(
            self.geometry,
            self.doors,
            self.entry,
            count,
            criterion_allowed=lambda c: c == "allowed",
        )

    def test_linear_rooms_ignore_unreferenced_terrain(self):
        result = self.derive()
        self.assertEqual(
            [(0, 0, 0), (10, 0, 0), (20, 0, 0)], [r["anchor"] for r in result["rooms"]]
        )
        self.assertEqual(
            [(1, 2), (2, 1), (2, 3), (3, 2)],
            [(d["source_room"], d["destination_room"]) for d in result["doors"]],
        )

    def test_branch_fails_instead_of_guessing(self):
        extra = copy.deepcopy(self.doors[0])
        extra["destinations"][0]["x"] = 20
        self.doors.append(extra)
        with self.assertRaises(ValueError):
            self.derive()

    def test_missing_room_fails(self):
        with self.assertRaises(ValueError):
            self.derive(4)

    def test_unknown_criterion_cannot_open_chain(self):
        self.doors[0]["destinations"][0]["criterion"] = "unknown"
        with self.assertRaises(ValueError):
            self.derive()

    def test_nonwalkable_destination_fails(self):
        self.doors[0]["destinations"][0]["x"] = 99
        with self.assertRaises(ValueError):
            self.derive()

    def test_duplicate_forward_anchor_fails(self):
        self.doors.append(copy.deepcopy(self.doors[0]))
        with self.assertRaises(ValueError):
            self.derive()
