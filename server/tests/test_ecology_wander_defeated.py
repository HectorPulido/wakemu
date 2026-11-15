"""World publication rejects living occupancy and permits defeated history.

The corresponding Rust planner occupancy/neighbor kernels are tested in
mob_geometry.rs; no Python planner is retained as a test implementation.
"""

from test_ecology_mobs_apply import prepared_movement_packet
import unittest
from copy import deepcopy
from unittest.mock import patch

from protocol_codec import decode_body
from test_ecology_mobs_apply import FakeGroups, FakeHarvests, FakeWorld
from wakfu_server import (
    ecology_mobs,
    monster_wander,
)


class DefeatedOccupancyTests(unittest.TestCase):
    def test_only_living_groups_block_prepared_monster_publication(self):
        configuration = dict(move_probability=1.0, radius=20, min_steps=1, max_steps=1)
        before = dict(id=-701, ref=60, team=1, x=0, y=0, z=0)
        other = dict(id=-702, ref=60, team=1, x=1, y=0, z=0)
        players = [dict(id=40, map_id=999999, instance_id=0, x=0, y=2, z=0)]
        opcode, payload = prepared_movement_packet(-701, (0, 0, 0), (1, 0, 0))
        proposal = dict(
            kind="wander",
            world_epoch="corpses",
            scope=[999999, 0],
            group_id=701,
            expected_members=[before],
            moved_members=[dict(before, x=1)],
            packets=[[opcode, payload.hex()]],
            configuration=configuration,
        )
        for status in ("defeated", "available", "fighting"):
            with self.subTest(status=status):
                rows = [
                    dict(group_id=701, status="available", members=[before]),
                    dict(group_id=702, status=status, members=[other]),
                ]
                groups = FakeGroups(deepcopy(rows))

                def cas(key, expected, replacement):
                    current = next(
                        row for row in groups.rows if row["group_id"] == key[2]
                    )
                    if current["members"] != expected:
                        return False
                    current["members"] = deepcopy(replacement)
                    return True

                groups.move_members = cas
                world = FakeWorld(players)
                with patch.object(monster_wander, "policy", return_value=configuration):
                    result = ecology_mobs.apply(
                        object(),
                        groups,
                        FakeHarvests(),
                        world,
                        deepcopy(proposal),
                        world_epoch="corpses",
                    )
                if status != "defeated":
                    self.assertEqual(result, {"status": "occupied"})
                    self.assertEqual(groups.rows[0]["members"], [before])
                    self.assertEqual(world.emitted, [])
                    continue
                self.assertEqual(result, {"status": "applied"})
                self.assertEqual(groups.rows[0]["members"][0]["x"], 1)
                decoded = decode_body("in", *world.emitted[0][2:])
                self.assertEqual(decoded["actor_id"], before["id"])
                self.assertEqual(decoded["end_position"], dict(x=1, y=0, z=0))

    def test_defeated_groups_do_not_affect_dispersion_but_fighters_do(self):
        rows = [
            dict(status=status, members=[dict(x=x, y=0, z=0)])
            for status, x in (("defeated", 1), ("fighting", 3), ("available", 5))
        ]
        index = monster_wander.group_neighbor_index(rows)
        self.assertEqual(monster_wander.nearest_group((0, 0, 0), index), (3, 0, 0))
        self.assertIsNone(
            monster_wander.nearest_group(
                (0, 0, 0), monster_wander.group_neighbor_index(rows[:1])
            )
        )
