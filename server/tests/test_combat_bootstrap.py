import unittest, struct
from wakfu_server.combat_bootstrap import placement_messages
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_wire import arena, decode_bootstrap
from protocol_codec import decode_body


class BootstrapTests(unittest.TestCase):
    def test_selected_fixed_build_controls_actor_level_without_rewriting_real_xp(self):
        from wakfu_server.combat_bootstrap import create_placement, player_payload
        from wakfu_server.monsters import owned_instance
        from wakfu_server.wire import proto_field
        from wakfu_server.progression import level_xp
        from wakfu_server.health import maximum

        char = dict(
            id=100,
            account_id=1,
            breed=8,
            level=50,
            xp=level_xp(50),
            hp=20,
            max_hp=maximum(8, 49),
            map_id=1134,
            x=0,
            y=0,
            z=0,
            active_build_index=1,
            inventory_items=[],
            builds={
                1: dict(
                    sheet=proto_field(24, 49).hex(), equipment="", aptitudes="", deck=""
                )
            },
        )
        monster = owned_instance(5525, 1, -200, map_id=1134, x=1, y=0, z=0)
        cells = [(0, 0, 0), (1, 0, 0)]
        terrain = arena(1134, 1, cells, {0: cells[0], 1: cells[1]})
        terrain.update(
            validated_cells=cells,
            valid_edges={(cells[0], cells[1]), (cells[1], cells[0])},
        )
        fight, messages = create_placement(
            char,
            monster,
            terrain,
            fight_id=7,
            player_ap=6,
            player_mp=4,
            player_wp=6,
            player_initiative=0,
            terrain_effect_id=46,
            terrain_instance_id=123,
            duration_ms=12345,
        )
        self.assertEqual(fight.actors[100].effective_level, 49)
        self.assertEqual((char["level"], char["xp"]), (50, level_xp(50)))
        payload, _ = player_payload(char, fight.actors[100], 7, wp=6)
        # Format3 carries real progression; actor's effective level is separate.
        self.assertEqual(struct.unpack_from(">q", payload, 1)[0], level_xp(50))
        self.assertEqual(struct.unpack_from(">h", payload, len(payload) - 2)[0], 50)
        self.assertEqual(
            decode_bootstrap(messages[1][1])["participants"][0]["actor_id"], 100
        )
        self.assertEqual(
            decode_body("in", 13684, messages[2][1]),
            dict(fight_id=7, placement_duration=12345),
        )
        from wakfu_server.combat_actor_snapshot import build_player_snapshot

        snapshot = build_player_snapshot(
            char, fight.actors[100], wp_current=6, wp_maximum=6, running_effects=()
        )
        self.assertEqual(snapshot.stats[1], 20)
        self.assertEqual(snapshot.maxima[1], maximum(8, 49))
        fight.actors[100].effective_level = 50
        with self.assertRaisesRegex(ValueError, "level disagrees"):
            build_player_snapshot(
                char, fight.actors[100], wp_current=6, wp_maximum=6, running_effects=()
            )

    def test_selected_map_placement_is_used_by_authoritative_fight(self):
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.monsters import owned_instance

        character = dict(
            id=100,
            account_id=1,
            breed=8,
            level=6,
            hp=110,
            max_hp=110,
            map_id=1385,
            x=3,
            y=-13,
            z=1,
        )
        monster = owned_instance(5525, 1, -200, map_id=1385, x=4, y=-13, z=1)
        terrain = local_arena(1385, 100, (3, -13, 1), (4, -13, 1))
        fight, _ = create_placement(
            character,
            monster,
            terrain,
            fight_id=7,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=0,
            terrain_effect_id=46,
            terrain_instance_id=123,
        )
        from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet

        self.assertIsInstance(fight.walkable, ImmutableTerrainSet)
        self.assertIsInstance(fight.edges, ImmutableTerrainSet)
        self.assertEqual(fight.native_obstacle_cells, frozenset())
        self.assertEqual(fight.placement, terrain["placement_cells"])
        self.assertEqual(
            {team: len(cells) for team, cells in fight.placement.items()},
            {0: 12, 1: 12},
        )
        destination = next(
            cell for cell in sorted(fight.placement[0]) if cell != (3, -13, 1)
        )
        fight.place(1, 100, destination)
        self.assertEqual(fight.actors[100].position, destination)

    def test_placement_only_uses_owned_identity_and_explicit_payloads(self):
        cells = [(0, 0, 0), (1, 0, 0)]
        f = Fight(
            7,
            [
                Actor(100, 0, cells[0], 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, cells[1], 20, 4, 2, 10, 1),
            ],
            cells,
            {0: {cells[0]}, 1: {cells[1]}},
        )
        terrain = arena(1134, 1, cells, {0: cells[0], 1: cells[1]})
        msgs = placement_messages(
            f,
            terrain,
            {100: (b"own player", b"\0\0"), -200: (b"own monster", b"\0\0")},
            terrain_effect_id=378,
            terrain_instance_id=-300,
            leaders={0: 100, 1: -200},
        )
        self.assertEqual([m[0] for m in msgs], [13652, 12847, 13684, 13026])
        v = decode_bootstrap(msgs[1][1])
        self.assertEqual([a["actor_id"] for a in v["participants"]], [100, -200])
        self.assertEqual((v["myp"], v["myI"], v["myJ"]), (-300, 100, -200))
        self.assertEqual(
            decode_body("in", 13684, msgs[2][1]),
            dict(fight_id=7, placement_duration=60000),
        )
        self.assertEqual(len(decode_body("in", 13652, msgs[0][1])["actors"]), 2)
        with self.assertRaises(ValueError):
            placement_messages(
                f,
                terrain,
                {100: (b"", b"")},
                terrain_effect_id=378,
                terrain_instance_id=-300,
                leaders={0: 100, 1: -200},
            )
        with self.assertRaises(ValueError):
            placement_messages(
                f,
                terrain,
                {100: (b"", b""), -200: (b"", b"")},
                terrain_effect_id=378,
                terrain_instance_id=-300,
                leaders={0: -200, 1: 100},
            )

    def test_constructor_combines_distinct_owned_player_and_monster_formats(self):
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.monsters import owned_instance

        character = dict(
            id=100,
            account_id=1,
            breed=2,
            level=1,
            hp=56,
            max_hp=60,
            map_id=1134,
            x=-8,
            y=-7,
            z=-1,
        )
        monster = owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)
        cells = [(-8, -7, -1), (-7, -7, -1)]
        terrain = arena(1134, 1, cells, {0: cells[0], 1: cells[1]})
        terrain["validated_cells"] = cells
        terrain["valid_edges"] = {(cells[0], cells[1]), (cells[1], cells[0])}
        fight, messages = create_placement(
            character,
            monster,
            terrain,
            fight_id=7,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=0,
            terrain_effect_id=378,
            terrain_instance_id=-300,
        )
        value = decode_bootstrap(messages[1][1])
        self.assertEqual([a["myE"][0] for a in value["participants"]], [3, 2])
        self.assertEqual(fight.actors[100].max_hp, 60)
        self.assertEqual(fight.actors[-200].hp, monster["hp"])
        self.assertEqual(fight.edges, terrain["valid_edges"])

    def test_two_monster_group_bootstrap_order_and_ack(self):
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.monsters import owned_instance
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_ai import plan

        character = dict(
            id=100,
            account_id=1,
            breed=2,
            level=1,
            hp=60,
            max_hp=60,
            map_id=1134,
            x=0,
            y=0,
            z=0,
        )
        members = [
            owned_instance(5525, 1, identity, map_id=1134, x=x, y=0, z=0)
            for identity, x in [(-200, 3), (-201, 4)]
        ]
        cells = [(x, 0, 0) for x in range(5)]
        terrain = arena(1134, 1, cells, {0: cells[0], 1: [cells[3], cells[4]]})
        terrain["validated_cells"] = cells
        terrain["valid_edges"] = {
            (a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1
        }
        fight, messages = create_placement(
            character,
            members,
            terrain,
            fight_id=7,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=0,
            terrain_effect_id=46,
            terrain_instance_id=-300,
        )
        value = decode_bootstrap(messages[1][1])
        self.assertEqual(
            [a["actor_id"] for a in value["participants"]], [100, -200, -201]
        )
        self.assertEqual(value["myJ"], -200)
        fight.ready(1)
        self.assertEqual(set(fight.order), {100, -200, -201})
        runtime = RuntimeMessages(fight)
        for _ in range(3):
            actor = fight.current
            if actor.controlled:
                runtime.end_turn(1, actor.id, actor.turn_count)
            else:
                route = plan(fight, actor.id)["path"]
                self.assertFalse(
                    any(
                        other.position in route
                        for other in fight.actors.values()
                        if other.id != actor.id and other.hp > 0
                    )
                )
                runtime.end_server_turn(actor.id, fight.turn_id)
            waiting = runtime.awaiting_ack
            runtime.acknowledge_turn(struct.pack(">i", waiting))
        self.assertEqual(fight.turn_id, 4)

    def test_rejects_duplicate_monster_positions(self):
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.monsters import owned_instance

        character = dict(
            id=100,
            account_id=1,
            breed=2,
            level=1,
            hp=60,
            max_hp=60,
            map_id=1134,
            x=0,
            y=0,
            z=0,
        )
        members = [
            owned_instance(5525, 1, identity, map_id=1134, x=1, y=0, z=0)
            for identity in (-200, -201)
        ]
        cells = [(0, 0, 0), (1, 0, 0)]
        terrain = arena(1134, 1, cells, {0: cells[0], 1: cells[1]})
        terrain["validated_cells"] = cells
        with self.assertRaises(ValueError):
            create_placement(
                character,
                members,
                terrain,
                fight_id=7,
                player_ap=6,
                player_mp=3,
                player_wp=6,
                player_initiative=0,
                terrain_effect_id=46,
                terrain_instance_id=-300,
            )
