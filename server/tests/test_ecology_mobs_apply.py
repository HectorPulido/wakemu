"""Fresh world-side guards for externally prepared monster movement."""
import unittest
import struct
from unittest.mock import patch

from wakfu_server import ecology_mobs, monster_wander


class LockProbe:
    def __init__(self):
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, *_args):
        return False


class FakeGroups:
    def __init__(self, rows=(), move_result=True):
        self.lock = LockProbe()
        self.rows = list(rows)
        self.move_result = move_result
        self.move_calls = []

    def snapshot(self, *_scope):
        return self.rows

    def move_members(self, key, expected, replacement):
        self.move_calls.append((key, expected, replacement))
        return self.move_result


class FakeHarvests:
    def __init__(self, targets=()):
        self.lock = LockProbe()
        self.targets = set(targets)


class FakeWorld:
    def __init__(self, players):
        self.players = players
        self.emitted = []

    def snapshot(self):
        return self.players

    def emit_location(self, *event):
        self.emitted.append(event)


class EcologyMobsApplyTests(unittest.TestCase):
    scope = (1134, 0)
    configuration = {
        "move_probability": 1.0,
        "radius": 3,
        "min_steps": 1,
        "max_steps": 1,
    }

    def movement(self, actor_id=-7001, origin=(0, 0, 0), destination=(1, 0, 0)):
        opcode, payload = monster_wander.movement_packet(actor_id, origin, destination)
        return [[opcode, payload.hex()]]

    def proposal(self, *, packets=None):
        before = {"id": -7001, "ref": 60, "team": 1, "x": 0, "y": 0, "z": 0}
        after = dict(before, x=1)
        return {
            "kind": "wander",
            "world_epoch": "boot-a",
            "scope": list(self.scope),
            "group_id": 17,
            "expected_members": [before],
            "moved_members": [after],
            "packets": self.movement() if packets is None else packets,
            "configuration": self.configuration,
        }

    def apply(self, proposal, *, groups=None, harvests=None, players=None):
        groups = groups or FakeGroups(
            [
                {
                    "group_id": 17,
                    "status": "available",
                    "members": proposal["expected_members"],
                }
            ]
        )
        harvests = harvests or FakeHarvests()
        world = FakeWorld(
            players
            if players is not None
            else [
                {
                    "id": 9001,
                    "map_id": self.scope[0],
                    "instance_id": self.scope[1],
                    "x": 20,
                    "y": 20,
                    "z": 0,
                }
            ]
        )
        with patch.object(monster_wander, "policy", return_value=self.configuration):
            result = ecology_mobs.apply(
                object(), groups, harvests, world, proposal, world_epoch="boot-a"
            )
        return result, groups, harvests, world

    def test_stale_world_epoch_is_rejected_before_live_locks(self):
        proposal = self.proposal()
        groups = FakeGroups()
        harvests = FakeHarvests()
        world = FakeWorld([])
        result = ecology_mobs.apply(
            object(), groups, harvests, world, proposal, world_epoch="boot-b"
        )
        self.assertEqual(result, {"status": "stale_epoch"})
        self.assertEqual(groups.lock.entered, 0)
        self.assertEqual(harvests.lock.entered, 0)

    def test_current_harvest_claim_blocks_stale_movement_plan(self):
        proposal = self.proposal()
        groups = FakeGroups(
            [
                {
                    "group_id": 17,
                    "status": "available",
                    "members": proposal["expected_members"],
                }
            ]
        )
        harvests = FakeHarvests({-7001})
        world = FakeWorld(
            [
                {
                    "id": 9001,
                    "map_id": self.scope[0],
                    "instance_id": 0,
                    "x": 20,
                    "y": 20,
                    "z": 0,
                }
            ]
        )
        with patch.object(monster_wander, "policy", return_value=self.configuration):
            result = ecology_mobs.apply(
                object(), groups, harvests, world, proposal, world_epoch="boot-a"
            )
        self.assertEqual(result, {"status": "harvesting"})
        self.assertEqual(groups.move_calls, [])
        self.assertEqual(world.emitted, [])

    def test_intermediate_path_collision_with_player_or_other_group_rejects_move(self):
        proposal = self.proposal()
        own = proposal["expected_members"][0]
        other_group = {
            "group_id": 18,
            "status": "available",
            "members": [{"id": -7002, "ref": 60, "team": 1, "x": 1, "y": 0, "z": 0}],
        }
        cases = (
            (
                [
                    {
                        "id": 9001,
                        "map_id": 1134,
                        "instance_id": 0,
                        "x": 1,
                        "y": 0,
                        "z": 0,
                    }
                ],
                [],
            ),
            (
                [
                    {
                        "id": 9001,
                        "map_id": 1134,
                        "instance_id": 0,
                        "x": 20,
                        "y": 20,
                        "z": 0,
                    }
                ],
                [other_group],
            ),
        )
        for players, other_groups in cases:
            with self.subTest(
                players=players[0]["id"], other_groups=bool(other_groups)
            ):
                groups = FakeGroups(
                    [
                        {"group_id": 17, "status": "available", "members": [own]},
                        *other_groups,
                    ]
                )
                result, _, _, world = self.apply(
                    proposal, groups=groups, players=players
                )
                self.assertEqual(result, {"status": "occupied"})
                self.assertEqual(groups.move_calls, [])
                self.assertEqual(world.emitted, [])

    def test_stale_group_cas_and_malformed_path_never_publish(self):
        proposal = self.proposal()
        groups = FakeGroups(
            [
                {
                    "group_id": 17,
                    "status": "available",
                    "members": proposal["expected_members"],
                }
            ],
            move_result=False,
        )
        result, _, _, world = self.apply(proposal, groups=groups)
        self.assertEqual(result, {"status": "stale_group"})
        self.assertEqual(world.emitted, [])

        malformed_packets = (
            [[13852, "00"]],
            [[13852, struct.pack(">qiihB", -7001, 0, 0, 0, 1).hex()]],
        )
        for packets in malformed_packets:
            malformed = self.proposal(packets=packets)
            groups = FakeGroups(
                [
                    {
                        "group_id": 17,
                        "status": "available",
                        "members": malformed["expected_members"],
                    }
                ]
            )
            with self.subTest(payload=packets[0][1]), self.assertRaises(
                (ValueError, struct.error)
            ):
                self.apply(malformed, groups=groups)
            self.assertEqual(groups.move_calls, [])


if __name__ == "__main__":
    unittest.main()
