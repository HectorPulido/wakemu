import unittest, struct
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_npc_attack import ability, execute


class NativeNpcAttackTests(unittest.TestCase):
    def setUp(self):
        self.pc = Actor(7, 0, (0, 0, 0), 60, 6, 3, 0, 1, owner_id=9, controlled=True)
        self.npc = Actor(-200, 1, (1, 0, 0), 20, 3, 3, 10, 1)
        self.fight = Fight(
            1,
            [self.pc, self.npc],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        self.monster = dict(id=-200, ref=5525, level=1, map_id=1134, wp=6)
        self.character = dict(id=7, account_id=9, breed=15, level=1, map_id=1134)
        from wakfu_server.combat_actor_snapshot import (
            build_player_snapshot,
            build_npc_snapshot,
        )

        self.character.update(
            hp=60, max_hp=self.pc.max_hp, builds={}, inventory_items=[]
        )
        self.pc.direction = 0
        self.npc.direction = 3
        build_player_snapshot(
            self.character, self.pc, wp_current=6, wp_maximum=6, running_effects=()
        ).install(self.pc)
        build_npc_snapshot(
            self.monster, self.npc, wp_current=6, wp_maximum=6, running_effects=()
        ).install(self.npc)
        from wakfu_server.combat_qi_fight import (
            install_fresh_actor_slots,
            prepare_fresh_actor_slots,
        )

        # Explicit serialized QI arena matching this two-cell unit fixture.
        self.fight.native_qi_snapshot = dict(
            x=0, y=0, width=7, height=1, cell_masks=[0] * 7
        )
        install_fresh_actor_slots(
            self.fight,
            prepare_fresh_actor_slots(
                self.fight,
                physical_radii={
                    actor.id: actor.physical_radius for actor in (self.pc, self.npc)
                },
            ),
        )
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        initialize_global_pv_collections(self.fight, tuple(self.fight.actors))
        self.fight.ready(9)
        self.fight.native_effect_uid_next = 1
        self.fight.native_obstacle_cells = frozenset()

    def run_attack(self, **changes):
        kwargs = dict(
            action_id=1,
            effect_uid=1,
            player_wp_current=6,
            player_wp_maximum=6,
            critical_chance=0,
            caster_running_effects=[],
            target_running_effects=[],
            caster_bonuses={},
            target_bonuses={},
            mitigate=lambda damage, *args: damage,
        )
        kwargs.update(changes)
        with patch("wakfu_server.combat_npc_attack.static_visible", return_value=True):
            return execute(self.monster, self.character, self.fight, 7, **kwargs)

    def test_native_wonejo_reference_and_transacted_attack(self):
        rule = ability(self.monster)
        self.assertEqual((rule["spell_id"], rule["ap"], rule["damage"]), (7962, 0, 5))
        result = self.run_attack()
        self.assertEqual((self.pc.hp, self.npc.ap), (55, 3))
        wire = result["packets"][0][1]
        self.assertEqual(struct.unpack_from(">qih", wire, 20), (7962, 7962, 1))
        self.assertEqual(struct.unpack_from(">i", result["packets"][1][1], 20)[0], 7962)
        self.assertEqual(result["snapshots"][-200][19], 3)
        with self.assertRaises(ValueError):
            self.run_attack()

    def test_codec_failure_no_mutation(self):
        before = len(self.fight.events)
        with self.assertRaises(ValueError):
            self.run_attack(action_id=0)
        self.assertEqual(
            (self.pc.hp, self.npc.ap, len(self.fight.events)), (60, 3, before)
        )

    def test_unknown_actor_effects_rejected(self):
        with self.assertRaises(ValueError):
            self.run_attack(target_running_effects=None)
        with self.assertRaises(ValueError):
            ability(dict(ref=2, level=4))

    def test_native_armor_absorption_precedes_hp_and_updates_packets(self):
        self.pc.effect_stats[97] = 7
        hp = self.pc.hp
        result = self.run_attack()
        self.assertEqual(self.pc.hp, hp)
        self.assertEqual(self.pc.effect_stats[97], 2)
        self.assertEqual(result["damage"], 0)
        self.assertTrue(any(opcode == 12613 for opcode, payload in result["packets"]))
        self.assertIn(struct.pack(">Bi", 97, 2), result["snapshots"][7])

    def test_exhausted_armor_spills_to_hp_without_changing_attack_costs(self):
        self.pc.effect_stats[97] = 2
        hp, ap, mp = self.pc.hp, self.npc.ap, self.npc.mp
        result = self.run_attack()
        self.assertEqual((self.pc.hp, self.pc.effect_stats[97]), (hp - 3, 0))
        self.assertEqual((self.npc.ap, self.npc.mp), (ap, mp))
        self.assertEqual(result["damage"], 3)
        self.assertTrue(any(e["kind"] == "damage" for e in result["events"]))

    def test_late_animation_failure_rolls_back_native_resources_and_uid(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        before = snapshot(self.fight)
        with patch(
            "wakfu_server.combat_npc_attack.attack_packets",
            side_effect=ValueError("codec failure"),
        ):
            with self.assertRaisesRegex(ValueError, "codec failure"):
                self.run_attack()
        self.assertEqual(snapshot(self.fight), before)
