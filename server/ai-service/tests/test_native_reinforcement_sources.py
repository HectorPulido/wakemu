"""Captured native serializers survive accepted ordinary wave births."""
from copy import deepcopy
import struct
import unittest
from unittest.mock import patch

from wakfu_ai.native.native_stats import NativeStats
from wakfu_server.combat_ordinary_reinforcement_sources import current_monster_sources
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_timeline_snapshot import current_wire_turn


class NativeReinforcementSourcesTests(unittest.TestCase):
    def test_old_serializer_ends_into_new_npc_with_birth_proof_and_failed_preview_retry(
        self,
    ):
        player = Actor(40, 0, (0, 0, 0), 395, 6, 3, 100, 26, 2, True, max_hp=480)
        old = Actor(-10, 1, (2, 0, 0), 10, 6, 3, 10, 10)
        fresh = Actor(-20, 1, (3, 0, 0), 70, 6, 3, 5, 10)
        fight = Fight(
            276,
            (player, old, fresh),
            {(x, 0, 0) for x in range(5)},
            {0: {player.position}, 1: {old.position, fresh.position}},
        )
        fight.ready(2)
        # Match the completed original wave: actual lethal dispatch settles its
        # native participation and timeline, rather than changing HP alone.
        fight.apply_effect_damage(player.id, old.id, old.hp)
        for actor in fight.actors.values():
            actor.effect_stats = {4: 0}
            actor.effect_maxima = {4: 0}
        fresh.native_obstacle_id = 2
        initial = {-10: dict(id=-10, ref=5, level=10, map_id=1314, instance_id=77)}
        source = dict(id=-20, ref=5, level=10, map_id=1314, instance_id=77)
        serializer = NativeStats(
            characters={40: dict(id=40, map_id=1314)},
            monsters=initial,
            fight_id=276,
            map_id=1314,
        )
        fight.rift_monsters = {**initial, -20: source}
        fight.rift_wave_state = dict(
            instance_id=77,
            wave=2,
            turn_budget=40,
            wave_actor_ids=[-20],
            current_actor_ids=[-20],
            pending_wave=None,
            staged_receipts=[
                dict(
                    completed_wave=1,
                    next_actor_ids=[-20],
                    next_species_refs=[5],
                )
            ],
        )
        # Exact minimal original birth wire; production creation_replay checks
        # opcode, actor/fight IDs and packet shape without publishing anything.
        fight.native_rift_creation_deliveries = {
            -20: [
                dict(
                    opcode=12608,
                    payload_hex=(b"\x00\x01\x01" + struct.pack(">q", -20)).hex(),
                ),
                dict(opcode=13091, payload_hex=struct.pack(">iq", 276, -20).hex()),
            ]
        }
        rebound = serializer.for_fight(fight)
        self.assertEqual(rebound.monsters, fight.rift_monsters)
        self.assertEqual(serializer.monsters, initial)
        for damage in ("receipt", "birth", "species", "old-source", "instance", "map"):
            candidate = deepcopy(fight)
            if damage == "receipt":
                candidate.rift_wave_state["staged_receipts"] = []
            elif damage == "birth":
                candidate.native_rift_creation_deliveries = {}
            elif damage == "species":
                candidate.rift_monsters[-20]["ref"] = 41
            elif damage == "old-source":
                candidate.rift_monsters[-10]["ref"] = 41
            elif damage == "instance":
                candidate.rift_monsters[-20]["instance_id"] = 78
            else:
                candidate.rift_monsters[-20]["map_id"] = 999
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                current_monster_sources(candidate, initial, map_id=1314)

        runtime = RuntimeMessages(fight, runtime_stats_serializer=serializer)
        before = (fight.current.id, fight.turn_id, deepcopy(fight.events))
        failed = deepcopy(runtime)
        failed.fight.native_rift_creation_deliveries = {}
        with self.assertRaises(ValueError):
            failed.end_turn(2, 40, current_wire_turn(failed.fight))
        self.assertEqual((fight.current.id, fight.turn_id, fight.events), before)
        encoded = []

        def encode(source, actor, fight_id, **kwargs):
            encoded.append((source, actor.id, fight_id))
            return b"\x08\x01"

        with patch(
            "wakfu_server.combat_actor.actual_monster_actor_stats", side_effect=encode
        ):
            packets = runtime.end_turn(2, 40, current_wire_turn(fight))
        self.assertEqual(runtime.fight.current.id, -20)
        self.assertIsNotNone(runtime.awaiting_ack)
        self.assertTrue(runtime.pending)
        self.assertTrue(any(opcode == 12502 for opcode, _ in packets))
        self.assertIn((source, -20, 276), encoded)
        self.assertEqual(serializer.monsters, initial)
        self.assertEqual(runtime.fight.actors[40].hp, 395)
        self.assertEqual(runtime.fight.actors[-20].hp, 70)
