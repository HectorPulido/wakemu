"""Planning and publication share the same living-monster occupancy policy."""
import unittest
from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import MagicMock, patch

from protocol_codec import decode_body
from test_ecology_mobs_apply import FakeGroups, FakeHarvests, FakeWorld
from wakfu_server import (
    ecology_mobs,
    monster_maturation,
    monster_reproduction,
    monster_wander,
)


class DefeatedOccupancyTests(unittest.TestCase):
    def test_only_living_groups_block_single_monster_planning_and_publication(self):
        configuration = dict(move_probability=1.0, radius=20, min_steps=1, max_steps=1)
        before = dict(id=-701, ref=60, team=1, x=0, y=0, z=0)
        other = dict(id=-702, ref=60, team=1, x=1, y=0, z=0)
        snapshot = dict(
            world_epoch="corpses",
            excluded_ids=[],
            locations=[[999999, 0]],
            now_ms=1000,
            players=[dict(id=40, map_id=999999, instance_id=0, x=0, y=2, z=0)],
        )
        for status in ("defeated", "available", "fighting"):
            with self.subTest(status=status), ExitStack() as patches:
                rows = [
                    dict(group_id=701, status="available", members=[before]),
                    dict(group_id=702, status=status, members=[other]),
                ]
                store = MagicMock()
                db = store.connection.return_value.__enter__.return_value
                db.execute.side_effect = (
                    lambda sql, *_: rows if "FROM combat_groups" in sql else []
                )
                for domain in (monster_maturation, monster_reproduction):
                    patches.enter_context(
                        patch.object(domain, "policy", return_value={})
                    )
                patches.enter_context(
                    patch.object(
                        monster_reproduction, "dungeon_population", return_value=False
                    )
                )
                patches.enter_context(
                    patch.object(monster_wander, "policy", return_value=configuration)
                )
                patches.enter_context(
                    patch.object(
                        ecology_mobs,
                        "_edges",
                        return_value=monster_wander.edge_index(
                            [((0, 0, 0), (1, 0, 0))]
                        ),
                    )
                )
                patches.enter_context(
                    patch.object(ecology_mobs.random, "random", return_value=0)
                )
                patches.enter_context(
                    patch.object(ecology_mobs.time, "monotonic", return_value=0)
                )
                plans = ecology_mobs.prepare(store, snapshot, limit=1)
                if status != "defeated":
                    self.assertEqual(plans, [])
                    continue
                self.assertEqual(len(plans), 1)
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
                world = FakeWorld(snapshot["players"])
                result = ecology_mobs.apply(
                    store,
                    groups,
                    FakeHarvests(),
                    world,
                    plans[0],
                    world_epoch="corpses",
                )
                self.assertEqual(result["applied_groups"], 1)
                self.assertEqual(groups.rows[0]["members"][0]["x"], 1)
                packet = world.emitted[0][2][0]
                decoded = decode_body("in", *packet)
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
