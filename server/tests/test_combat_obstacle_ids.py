import struct, unittest, copy
from wakfu_server.combat_bootstrap import create_placement
from wakfu_server.combat_wire import arena, decode_bootstrap
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_actor import actual_monster_actor_stats


class ObstacleIdentityTests(unittest.TestCase):
    def test_two_and_eight_large_uid_npcs_keep_distinct_obstacles_and_affiliation(self):
        for count in (2, 8):
            character = dict(
                id=11,
                account_id=3,
                breed=11,
                level=20,
                hp=250,
                max_hp=250,
                map_id=1134,
                x=0,
                y=0,
                z=0,
            )
            cells = {(i, 0, 0) for i in range(count + 1)}
            members = [
                owned_instance(
                    5525, 1, -652221269888486132 - i, map_id=1134, x=i + 1, y=0, z=0
                )
                for i in range(count)
            ]
            placement = {0: {(0, 0, 0)}, 1: cells - {(0, 0, 0)}}
            terrain = arena(1134, 0, cells, placement)
            terrain.update(validated_cells=cells, placement_cells=placement)
            fight, packets = create_placement(
                character,
                members,
                terrain,
                fight_id=582056262,
                player_ap=6,
                player_mp=3,
                player_wp=6,
                player_initiative=0,
                terrain_effect_id=46,
                terrain_instance_id=-300,
            )
            # The placement wire above emits the fresh ordinary-NPC po.SX
            # byte as false; carry that same known constructor fact into the
            # live actor fixture used by the later snapshot serializer.
            for member in members:
                fight.actors[member["id"]].native_controlled_by_ai = False
            parsed = decode_bootstrap(next(b for op, b in packets if op == 12847))
            ids = []
            for row in parsed["participants"]:
                blob = row["myE"]
                position_end = 29 if blob[0] == 3 else 21
                ids.append(struct.unpack_from(">iBBBBbB", blob, position_end)[5])
                self.assertEqual(row["myn"], fight.actors[row["actor_id"]].team)
            self.assertEqual(ids, list(range(count + 1)))
            clone = copy.deepcopy(fight)
            for member in members:
                actor = clone.actors[member["id"]]
                body = actual_monster_actor_stats(
                    member,
                    actor,
                    clone.id,
                    wp_current=member["wp"],
                    wp_maximum=member["wp"],
                )
                self.assertEqual(
                    struct.unpack_from(">iBBBBbB", body, 21)[5],
                    actor.native_obstacle_id,
                )
                self.assertEqual(actor.team, 1)

    def test_capacity_failure_is_atomic_and_reserved_corpse_index_is_not_reused(self):
        from types import SimpleNamespace
        from wakfu_server.combat_obstacle_ids import assign_obstacle_ids

        actors = [SimpleNamespace(native_obstacle_id=None) for _ in range(128)]
        with self.assertRaisesRegex(ValueError, "capacity"):
            assign_obstacle_ids(actors)
        self.assertTrue(all(a.native_obstacle_id is None for a in actors))
        roster = [
            SimpleNamespace(native_obstacle_id=0),
            SimpleNamespace(native_obstacle_id=1, hp=0),
        ]
        for i in range(2, 127):
            new = SimpleNamespace(native_obstacle_id=None)
            assign_obstacle_ids([*roster, new])
            roster.append(new)
            self.assertEqual(new.native_obstacle_id, i)
        extra = SimpleNamespace(native_obstacle_id=None)
        with self.assertRaisesRegex(ValueError, "capacity"):
            assign_obstacle_ids([*roster, extra])
        self.assertIsNone(extra.native_obstacle_id)
        self.assertEqual([a.native_obstacle_id for a in roster], list(range(127)))

    def test_duplicate_provided_index_is_rejected(self):
        from types import SimpleNamespace
        from wakfu_server.combat_obstacle_ids import assign_obstacle_ids

        with self.assertRaisesRegex(ValueError, "duplicate"):
            assign_obstacle_ids(
                [
                    SimpleNamespace(native_obstacle_id=4),
                    SimpleNamespace(native_obstacle_id=4),
                ]
            )
