import unittest


class NativeYopukaStateDeliveryTests(unittest.TestCase):
    def test_native_yopuka_carriers_are_retained_with_complete_identity(self):
        import struct, random
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            prepare_server_turn_end,
        )
        from wakfu_server.monsters import owned_instance
        from wakfu_server.combat_actor_snapshot import build_npc_snapshot
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.spells import encode_deck

        for level, spell, critical in (
            (l, s, c)
            for l in (20, 200)
            for s in (4780, 4783, 4778)
            for c in (False, True)
        ):
            with self.subTest(level=level, spell=spell, critical=critical):
                from wakfu_server.combat_bootstrap import create_placement
                from wakfu_server.combat_wire import arena as encode_arena
                from wakfu_server.combat_actor_snapshot import (
                    initialize_fight_snapshots,
                )
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
                from wakfu_server.combat_geometry_snapshot import source_snapshot
                from wakfu_server.combat_effect_removal import _identity_fields

                preview = transaction.fight
                self.assertEqual(source_snapshot(fight), before)
                self.assertGreater(preview.actors[-7].hp, 0)
                self.assertLess(preview.actors[-7].hp, monster["hp"])
                from wakfu_server.combat_state_carrier import (
                    STATE_CARRIER_APPLICATION_OPCODE,
                )

                carriers = []
                for opcode, packet in transaction.packets:
                    if (
                        opcode == STATE_CARRIER_APPLICATION_OPCODE
                        and struct.unpack(
                            ">i", packet[13:17] if opcode == 12613 else packet[12:16]
                        )[0]
                        == 310
                    ):
                        fields = _identity_fields(
                            packet[19:] if opcode == 12613 else packet[18:]
                        )
                        self.assertEqual(fields[1], fields[2])
                        self.assertEqual(fields[6], 7)
                        carriers.append(fields)
                references = {f[4] >> 16 for f in carriers}
                self.assertIn(3442, references)
                self.assertGreater(
                    next(
                        e.level
                        for e in preview.actors[7].state_ledger.entries
                        if e.reference == 3442
                    ),
                    0,
                )
                for fields in carriers:
                    actor_id = (
                        fields[7] if fields[7] < (1 << 63) else fields[7] - (1 << 64)
                    )
                    self.assertTrue(
                        any(
                            e.uid == fields[1] and e.reference == fields[4] >> 16
                            for e in preview.actors[actor_id].state_ledger.entries
                        )
                    )
                if spell == 4780:
                    self.assertIn(8913, references)
                    self.assertTrue(
                        any(
                            e.reference == 8913
                            for e in preview.actors[-7].state_ledger.entries
                        )
                    )

                if spell == 4780:
                    second_before = source_snapshot(preview)
                    second = prepare_server_spell(
                        struct.pack(">qqiih", 7, (7 << 32) | spell, -7, -7, -1),
                        character,
                        {-7: monster},
                        preview,
                        3,
                        deck,
                        action_id=3,
                        line_of_sight=lambda *args: True,
                        critical=critical,
                        rng=random.Random(1),
                    )
                    self.assertEqual(source_snapshot(preview), second_before)
                    self.assertLess(second.fight.actors[-7].hp, preview.actors[-7].hp)
                    self.assertGreater(second.fight.actors[-7].hp, 0)
                    self.assertGreaterEqual(
                        next(
                            e.level
                            for e in second.fight.actors[7].state_ledger.entries
                            if e.reference == 3442
                        ),
                        20,
                    )
