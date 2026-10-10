"""Dragon-form Osamodas self-centered attacks preserve the cast target context."""
import os
import struct
import unittest
from random import Random
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
@patch.dict(
    os.environ,
    {"WAKFU_NATIVE_GRANTED_CAST": "1", "WAKFU_NATIVE_AREA_CALLBACKS": "1"},
)
class OsamodasDragonAoeRuntimeTests(unittest.TestCase):
    def fixture(self, *, sex=0):
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_orientation import INITIAL_PLAYER_DIRECTION
        from wakfu_server.equipment_stats import combat_resources, effective_character
        from wakfu_server.health import maximum
        from wakfu_server.monsters import owned_instance
        from wakfu_server.spells import encode_deck

        owner_cell = (-8, -7, -1)
        enemy_cell = (-7, -7, -1)
        outside_cell = (-8, -2, -1)
        character = effective_character(
            dict(
                id=7,
                account_id=3,
                breed=2,
                level=200,
                hp=maximum(2, 200),
                max_hp=maximum(2, 200),
                map_id=1134,
                instance_id=0,
                x=owner_cell[0],
                y=owner_cell[1],
                z=owner_cell[2],
                sex=sex,
                builds={},
                inventory_items=[],
            )
        )
        character["sex"] = sex
        resources = combat_resources(character)
        monster = owned_instance(
            5525,
            1,
            -7,
            map_id=1134,
            x=enemy_cell[0],
            y=enemy_cell[1],
            z=enemy_cell[2],
            team=1,
        )
        outside_monster = owned_instance(
            5525,
            1,
            -8,
            map_id=1134,
            x=outside_cell[0],
            y=outside_cell[1],
            z=outside_cell[2],
            team=1,
        )
        monsters = {-7: monster, -8: outside_monster}
        arena = local_arena(
            1134,
            7,
            owner_cell,
            [enemy_cell, outside_cell],
            relocate_monsters=False,
        )
        player = Actor(
            7,
            0,
            owner_cell,
            character["hp"],
            resources["ap"],
            resources["mp"],
            resources["initiative"],
            200,
            3,
            True,
            max_hp=character["max_hp"],
        )
        enemy = Actor(
            -7,
            1,
            enemy_cell,
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            1,
            max_hp=monster["max_hp"],
        )
        outside = Actor(
            -8,
            1,
            outside_cell,
            outside_monster["hp"],
            outside_monster["ap"],
            outside_monster["mp"],
            outside_monster["initiative"],
            1,
            max_hp=outside_monster["max_hp"],
        )
        player.direction = INITIAL_PLAYER_DIRECTION
        enemy.direction, outside.direction = 3, 3
        fight = Fight(
            78,
            [player, enemy, outside],
            arena["validated_cells"],
            {0: {owner_cell}, 1: {enemy_cell, outside_cell}},
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            name: arena[name] for name in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        freeze_terrain(fight)
        initialize_global_pv_collections(fight, tuple(fight.actors))
        deck = encode_deck([7312, 7317])
        initialize_fight_snapshots(
            fight,
            characters={7: character},
            monsters=monsters,
            wp_resources={
                7: (resources["wp"], resources["wp"]),
                -7: (monster["wp"], monster["wp"]),
                -8: (outside_monster["wp"], outside_monster["wp"]),
            },
            running_effects={7: (), -7: (), -8: ()},
            initial_effect_uid=1,
        )
        fight.native_obstacle_cells = frozenset()
        fight.ready(3)
        return character, monsters, fight, deck

    def owner_turn(self, character, monsters, fight, deck):
        from wakfu_server.combat_server_spell import prepare_server_turn_end

        while fight.current.id != 7:
            actor_id = fight.current.id
            fight, _ = prepare_server_turn_end(
                character,
                monsters,
                fight,
                deck,
                actor_id=actor_id,
                action_id=10 + fight.turn_id,
                rng=Random(7),
            )
            fight.end_server_turn(actor_id, fight.turn_id)
        return fight

    def next_owner_turn(self, character, monsters, fight, deck, *, action_id):
        from wakfu_server.combat_server_spell import prepare_server_turn_end

        self.assertEqual(fight.current.id, 7)
        owner_turn = fight.actors[7].turn_count
        fight, _ = prepare_server_turn_end(
            character,
            monsters,
            fight,
            deck,
            actor_id=7,
            action_id=action_id,
            rng=Random(7),
        )
        fight.end_turn(3, 7, owner_turn)
        fight = self.owner_turn(character, monsters, fight, deck)
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        RuntimeMessages(fight).turn_started(arm_deadline=False)
        self.assertEqual(fight.native_table_turn, fight.native_timeline_round)
        return fight

    def cast(self, character, monsters, fight, deck, uid, target, action_id):
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_server_spell import prepare_server_spell

        def line_of_sight(source, destination, preview):
            return authoritative_visible(
                character["map_id"],
                source,
                destination,
                preview,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in preview.actors.values()
                    if actor.hp > 0
                },
            )

        return prepare_server_spell(
            struct.pack(">qqiih", 7, uid, *target),
            character,
            monsters,
            fight,
            3,
            deck,
            action_id=action_id,
            line_of_sight=line_of_sight,
            critical=False,
            rng=Random(7),
        )

    def assert_dragon_centered_attack_damages_adjacent_enemy(self, spell_id):
        from wakfu_server.combat_spell_grant import granted_spells

        character, monsters, fight, deck = self.fixture()
        from wakfu_server.combat_server_spell import prepare_server_initialization

        fight, _ = prepare_server_initialization(
            character,
            monsters,
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        fight = self.owner_turn(character, monsters, fight, deck)
        self.assertIn(7349, granted_spells(fight, 7))

        transformed = self.cast(
            character,
            monsters,
            fight,
            deck,
            7349,
            fight.actors[7].position,
            2,
        )
        fight = transformed.fight
        self.assertIn(
            7123,
            {entry.reference for entry in fight.actors[7].state_ledger.entries},
        )
        self.assertEqual(
            sum(
                abs(fight.actors[-7].position[index] - fight.actors[7].position[index])
                for index in range(2)
            ),
            1,
        )
        self.assertEqual(fight.actors[-7].position[2], fight.actors[7].position[2])
        before_hp = fight.actors[-7].hp
        outside_before_hp = fight.actors[-8].hp
        self.assertEqual(fight.actors[-8].position, (-8, -2, -1))
        self.assertEqual(
            sum(
                abs(fight.actors[-8].position[index] - fight.actors[7].position[index])
                for index in range(2)
            ),
            5,
        )

        attack = self.cast(
            character,
            monsters,
            fight,
            deck,
            (7 << 32) | spell_id,
            fight.actors[7].position,
            3,
        )
        self.assertEqual(attack.plan["spell_id"], spell_id)
        self.assertLess(
            attack.fight.actors[-7].hp,
            before_hp,
            f"Dragon-form self-centered spell {spell_id} did not damage its adjacent enemy",
        )
        self.assertEqual(
            attack.fight.actors[-8].hp,
            outside_before_hp,
            f"Dragon-form spell {spell_id} damaged an actor outside its native area",
        )

    def test_dragon_latigo_self_center_damages_adjacent_enemy(self):
        self.assert_dragon_centered_attack_damages_adjacent_enemy(7317)

    def test_dragon_tormenta_de_arena_self_center_damages_adjacent_enemy(self):
        self.assert_dragon_centered_attack_damages_adjacent_enemy(7312)

    def test_self_cast_without_dragon_state_is_rejected_without_damage(self):
        from wakfu_server.combat_server_spell import prepare_server_initialization

        character, monsters, fight, deck = self.fixture()
        fight, _ = prepare_server_initialization(
            character,
            monsters,
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        fight = self.owner_turn(character, monsters, fight, deck)
        self.assertNotIn(
            7123,
            {entry.reference for entry in fight.actors[7].state_ledger.entries},
        )
        before = {actor.id: actor.hp for actor in fight.actors.values()}
        with self.assertRaises(ValueError):
            self.cast(
                character,
                monsters,
                fight,
                deck,
                (7 << 32) | 7317,
                fight.actors[7].position,
                2,
            )
        self.assertEqual(
            {actor.id: actor.hp for actor in fight.actors.values()}, before
        )

    def test_three_dragon_round_trips_preserve_visual_uid_for_both_sexes(self):
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_effect_removal import running_effect_removal
        from wakfu_server.combat_stat_effects import owned_effect_delivery
        from wakfu_server.fight_checkpoint_store import snapshot

        for sex, expected_visual in ((0, 326546), (1, 326547)):
            with self.subTest(sex=sex):
                character, monsters, fight, deck = self.fixture(sex=sex)
                fight, _ = prepare_server_initialization(
                    character,
                    monsters,
                    fight,
                    3,
                    deck,
                    action_id=1,
                    rng=Random(7),
                    fight_start=True,
                )
                fight = self.owner_turn(character, monsters, fight, deck)
                from wakfu_server.combat_runtime_messages import RuntimeMessages

                RuntimeMessages(fight).turn_started(arm_deadline=False)
                self.assertEqual(fight.native_table_turn, fight.native_timeline_round)
                self.assertIn(7349, granted_spells(fight, 7))
                self.assertNotIn(
                    7123,
                    {entry.reference for entry in fight.actors[7].state_ledger.entries},
                )
                initial_hp = {
                    identity: actor.hp for identity, actor in fight.actors.items()
                }
                with self.assertRaises(ValueError):
                    self.cast(
                        character,
                        monsters,
                        fight,
                        deck,
                        (7 << 32) | 7317,
                        fight.actors[7].position,
                        20,
                    )
                self.assertEqual(
                    {identity: actor.hp for identity, actor in fight.actors.items()},
                    initial_hp,
                )

                for cycle in range(3):
                    on_action = 100 + cycle * 20
                    on = self.cast(
                        character,
                        monsters,
                        fight,
                        deck,
                        7349,
                        fight.actors[7].position,
                        on_action,
                    )
                    fight = on.fight
                    dragon_states = [
                        entry
                        for entry in fight.actors[7].state_ledger.entries
                        if entry.reference == 7123
                    ]
                    self.assertEqual(len(dragon_states), 1)
                    dragon_state = dragon_states[0]
                    visuals = [
                        row
                        for row in fight.native_retained_records.values()
                        if row.get("generic_effect") in (326546, 326547)
                        and row.get("target_id") == 7
                    ]
                    self.assertEqual(len(visuals), 1)
                    visual = visuals[0]
                    self.assertEqual(visual["generic_effect"], expected_visual)
                    self.assertEqual(visual["effect_class"], 400)
                    self.assertEqual(visual["owner_uid"], dragon_state.uid)
                    visual_uid = visual["uid"]
                    visual_runner = fight.owned_stat_effects[visual_uid]
                    self.assertEqual(visual_runner["state_uid"], dragon_state.uid)
                    self.assertIn(
                        owned_effect_delivery(
                            fight.id,
                            on_action,
                            native_opcode=12613,
                            effect_class=400,
                            target_id=7,
                            uid=visual_uid,
                            running_effect_payload=bytes.fromhex(
                                visual_runner["payload"]
                            ),
                        ),
                        on.packets,
                    )
                    on_snapshot = snapshot(fight)
                    self.assertEqual(
                        on_snapshot["native_retained_records"][str(visual_uid)][
                            "generic_effect"
                        ],
                        expected_visual,
                    )

                    if cycle == 0:
                        before_hp = fight.actors[-7].hp
                        attack = self.cast(
                            character,
                            monsters,
                            fight,
                            deck,
                            (7 << 32) | 7317,
                            fight.actors[7].position,
                            on_action + 1,
                        )
                        fight = attack.fight
                        self.assertLess(fight.actors[-7].hp, before_hp)

                    # The native spell limit gives transformation spell7349
                    # an interval of two table turns. Advance through two
                    # real runtime round boundaries before the opposite cast.
                    for turn_offset in (2, 3):
                        fight = self.next_owner_turn(
                            character,
                            monsters,
                            fight,
                            deck,
                            action_id=on_action + turn_offset,
                        )
                    off_action = on_action + 4
                    off = self.cast(
                        character,
                        monsters,
                        fight,
                        deck,
                        7349,
                        fight.actors[7].position,
                        off_action,
                    )
                    fight = off.fight
                    self.assertNotIn(
                        7123,
                        {
                            entry.reference
                            for entry in fight.actors[7].state_ledger.entries
                        },
                    )
                    self.assertIn(
                        (
                            13560,
                            running_effect_removal(
                                fight.id,
                                off_action,
                                effect_class=400,
                                target_id=7,
                                uid=visual_uid,
                                running_effect_payload=bytes.fromhex(
                                    visual_runner["payload"]
                                ),
                            ),
                        ),
                        off.packets,
                    )
                    self.assertNotIn(visual_uid, fight.native_retained_records)
                    self.assertNotIn(visual_uid, fight.owned_stat_effects)
                    self.assertNotIn(
                        dragon_state.uid, fight.native_owned_state_containers
                    )
                    self.assertNotIn(dragon_state.uid, fight.state_wire_payloads)
                    off_snapshot = snapshot(fight)
                    self.assertNotIn(
                        str(visual_uid), off_snapshot["native_retained_records"]
                    )
                    self.assertNotIn(
                        str(visual_uid), off_snapshot["owned_stat_effects"]
                    )
                    self.assertNotIn(
                        str(dragon_state.uid),
                        off_snapshot["native_owned_state_containers"],
                    )
                    self.assertNotIn(
                        str(dragon_state.uid), off_snapshot["state_wire_payloads"]
                    )

                    self_target_hp = {i: actor.hp for i, actor in fight.actors.items()}
                    with self.assertRaises(ValueError):
                        self.cast(
                            character,
                            monsters,
                            fight,
                            deck,
                            (7 << 32) | 7317,
                            fight.actors[7].position,
                            off_action + 1,
                        )
                    self.assertEqual(
                        {i: actor.hp for i, actor in fight.actors.items()},
                        self_target_hp,
                    )
                    if cycle < 2:
                        for turn_offset in (6, 7):
                            fight = self.next_owner_turn(
                                character,
                                monsters,
                                fight,
                                deck,
                                action_id=on_action + turn_offset,
                            )


if __name__ == "__main__":
    unittest.main()
