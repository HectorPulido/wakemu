import unittest


class JuicioUsageTests(unittest.TestCase):
    def test_third_native_cast_rejects_without_spending_or_mutating(self):
        import struct, random
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
        )
        from wakfu_server.monsters import owned_instance
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.spells import encode_deck
        from wakfu_server.combat_geometry_snapshot import source_snapshot

        level, spell, critical = 20, 4776, False
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.combat_wire import arena as encode_arena
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.health import maximum

        character = dict(
            id=7,
            account_id=3,
            name="Turn regression",
            breed=8,
            level=level,
            hp=maximum(8, level),
            max_hp=maximum(8, level),
            map_id=1134,
            instance_id=0,
            x=-8,
            y=-7,
            z=-1,
            builds={},
            inventory_items=[],
        )
        monster = owned_instance(4085, 23, -7, map_id=1134, x=-7, y=-7, z=-1)
        terrain = local_arena(1134, 7, (-8, -7, -1), (-7, -7, -1))
        placement = {0: {(-8, -7, -1)}, 1: {(-7, -7, -1)}}
        arena = encode_arena(1134, 0, terrain["validated_cells"], placement)
        arena.update(
            validated_cells=terrain["validated_cells"],
            valid_edges=terrain["valid_edges"],
            placement_cells=placement,
        )
        fight, _ = create_placement(
            character,
            monster,
            arena,
            fight_id=78,
            player_ap=6,
            player_mp=4,
            player_wp=6,
            player_initiative=0,
            terrain_effect_id=46,
            terrain_instance_id=-300,
        )
        initialize_fight_snapshots(
            fight,
            characters={7: character},
            monsters={-7: monster},
            wp_resources={7: (6, 6), -7: (0, 0)},
            running_effects={7: (), -7: ()},
            initial_effect_uid=1,
        )
        fight.actors[7].direction = 0
        fight.actors[-7].direction = 3
        fight.ready(3)
        deck = encode_deck([spell])
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(1),
            fight_start=True,
        )
        # Install at actual first-turn boundary before the native
        # creature's higher initiative first turn is passed.
        while not fight.current.controlled:
            fight.end_server_turn(fight.current.id, fight.turn_id)
        fight.native_table_turn = fight.current.turn_count
        from wakfu_server.combat_geometry_snapshot import source_snapshot

        before = source_snapshot(fight)
        transaction = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | spell, -7, -7, -1),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=critical,
            rng=random.Random(1),
        )
        second = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | spell, -7, -7, -1),
            character,
            {-7: monster},
            transaction.fight,
            3,
            deck,
            action_id=3,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        self.assertGreater(second.fight.actors[-7].hp, 0)
        self.assertEqual(
            second.fight.actors[7].ap,
            6 - transaction.plan["costs"]["ap"] - second.plan["costs"]["ap"],
        )
        before = source_snapshot(second.fight)
        with self.assertRaisesRegex(ValueError, "maximum casts per target"):
            prepare_server_spell(
                struct.pack(">qqiih", 7, (7 << 32) | spell, -7, -7, -1),
                character,
                {-7: monster},
                second.fight,
                3,
                deck,
                action_id=4,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(1),
            )
        self.assertEqual(source_snapshot(second.fight), before)
