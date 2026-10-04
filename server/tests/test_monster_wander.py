import tempfile
import unittest
from pathlib import Path
from copy import deepcopy
from wakfu_server.monster_wander import plan, wander_location
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_group_redis import RedisGroups
from wakfu_server.store import Store
from tests.test_combat_group_redis import MemoryRedis
from protocol_codec import decode_body


class WanderTests(unittest.TestCase):
    def test_nearness_edges_and_occupancy(self):
        members = [owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)]
        edges = [((0, 0, 0), (1, 0, 1))]
        self.assertIsNone(plan(members, [], edges))
        self.assertIsNone(plan(members, [dict(x=50, y=50, z=0)], edges))
        self.assertIsNone(
            plan(members, [dict(x=2, y=0, z=0)], edges, occupied=[(1, 0, 1)])
        )
        result = plan(members, [dict(x=2, y=0, z=0)], edges)
        op, body = result["packets"][0]
        decoded = decode_body("in", op, body)
        self.assertEqual(op, 13852)
        self.assertEqual(result["members"][0]["z"], 1)
        self.assertEqual(members[0]["x"], 0)

    def test_durable_positions_claim_race_and_sql_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "world.db")
            client = MemoryRedis()
            groups = RedisGroups(store, client, namespace="wander-test")
            members = [owned_instance(5525, 1, -200, map_id=1134, x=0, y=0, z=0)]
            key = groups.register(1134, 0, 500, members)
            player = dict(map_id=1134, instance_id=0, x=2, y=0, z=0)
            packets = []
            self.assertEqual(
                wander_location(
                    groups,
                    1134,
                    0,
                    [player],
                    [((0, 0, 0), (1, 0, 0))],
                    lambda *p: packets.append(p),
                ),
                [key],
            )
            recovered = RedisGroups(store, client, namespace="wander-test")
            self.assertEqual(recovered.available(1134, 0)[0]["members"][0]["x"], 1)
            self.assertFalse(groups.move_members(key, members, members))
            groups.flush()
            self.assertEqual(groups.register_seed(1134, 0, 500, members), key)
            badseed = deepcopy(members)
            badseed[0]["id"] = -201
            with self.assertRaises(ValueError):
                groups.register_seed(1134, 0, 500, badseed)
            self.assertEqual(
                wander_location(
                    groups,
                    1134,
                    0,
                    [player],
                    [((1, 0, 0), (0, 0, 0))],
                    lambda *p: packets.append(p),
                    excluded_ids={-200},
                ),
                [],
            )
            with store.connection() as db:
                self.assertIn(
                    '"x":1',
                    db.execute("SELECT members FROM combat_groups")
                    .fetchone()[0]
                    .replace(" ", ""),
                )
            current = groups.available(1134, 0)[0]["members"]
            groups.claim(key, "generation", 12)
            changed = deepcopy(current)
            changed[0]["x"] = 0
            self.assertFalse(groups.move_members(key, current, changed))
            self.assertEqual(
                wander_location(
                    groups,
                    1134,
                    0,
                    [player],
                    [((1, 0, 0), (0, 0, 0))],
                    lambda *p: packets.append(p),
                ),
                [],
            )
            self.assertEqual(len(packets), 1)
