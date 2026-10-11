"""Typed departure finality remains separate from damage KO authority."""
import struct
import unittest
from unittest.mock import patch

import test_combat_pve_departure as departure_fixture
from wakfu_server.combat_death import death_messages
from wakfu_server.combat_pve_departure import retired_pve_actor_ids
from wakfu_server.combat_pve_withdraw import plan
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Session
from wakfu_server.combat_qi_fight import current_registry
from wakfu_server.fight_checkpoint_store import snapshot


class NativeDepartureFinalDeliveryTests(unittest.TestCase):
    def test_real_withdrawal_delivers_final2_with_single_certified_retirement(self):
        original = departure_fixture.PvEDepartureTests().fixture()
        runtime = RuntimeMessages(original)
        old_slot = original.actors[10].native_obstacle_id
        result = plan(Session(1, 10, "owner", 527, 0), original, runtime)
        states = [
            struct.unpack(">qB", body[-9:])
            for opcode, body in result.public_packets
            if opcode == 12727
        ]
        self.assertEqual(states, [(10, 2)])
        self.assertEqual(retired_pve_actor_ids(result.fight), frozenset((10,)))
        self.assertIsNone(current_registry(result.fight).slots[old_slot])
        self.assertFalse(getattr(result.fight, "native_ordinary_qi_retirements", {}))
        self.assertEqual(
            result.fight.actors[10].native_death_status["last_writer"],
            "owned.aTS.F.type2",
        )
        self.assertEqual(original.actors[10].hp, 45)
        for sender in (result.runtime, RuntimeMessages(result.fight)):
            with self.assertRaisesRegex(ValueError, "already reported"):
                death_messages(sender, 10, fighter_state=2)
        self.assertEqual(result.fight.actors[20].hp, 55)
        self.assertEqual(result.fight.phase, "active")

    def test_uncertified_withdrawn_flag_cannot_authorize_final_delivery(self):
        fight = departure_fixture.PvEDepartureTests().fixture()
        # Deliberately malformed input, not a gameplay death preparation.
        fight.actors[10].hp = 0
        fight.actors[10].pve_withdrawn = True
        runtime = RuntimeMessages(fight)
        before = snapshot(fight)
        with self.assertRaises(ValueError):
            death_messages(runtime, 10, fighter_state=2)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(runtime.action_id, 0)

    def test_interrupted_withdrawal_encoding_keeps_original_qi_and_population(self):
        fight = departure_fixture.PvEDepartureTests().fixture()
        runtime = RuntimeMessages(fight)
        before = snapshot(fight)
        with patch.object(
            RuntimeMessages, "_flush", side_effect=ValueError("wire interrupted")
        ):
            with self.assertRaisesRegex(ValueError, "wire interrupted"):
                plan(Session(1, 10, "owner", 527, 0), fight, runtime)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(runtime.action_id, 0)
        self.assertFalse(getattr(runtime, "_reported_deaths", set()))

    def test_actual_ko_player_withdrawal_completes_existing_lifecycle(self):
        import test_native_player_death_runtime_qualified as death_fixture

        helper, data, fight = death_fixture.NativePlayerDeathRuntimeTests().corpse()
        runtime = RuntimeMessages(fight)
        runtime.prepare_delivery(death_messages(runtime, 8))
        self.assertEqual(
            fight.actors[8].native_death_status["last_writer"], "owned.aTS.F.type0"
        )
        old_slot = fight.actors[8].native_obstacle_id
        result = plan(
            Session(fight.actors[8].owner_id, 8, "owner", 1134, 0), fight, runtime
        )
        states = [
            struct.unpack(">qB", body[-9:])
            for opcode, body in result.public_packets
            if opcode == 12727
        ]
        self.assertEqual(states, [(8, 2)])
        self.assertIn(8, retired_pve_actor_ids(result.fight))
        self.assertIsNone(current_registry(result.fight).slots[old_slot])
        self.assertEqual(
            result.fight.actors[8].native_death_status["last_writer"],
            "owned.aTS.F.type2",
        )
        self.assertEqual(result.fight.phase, "active")
        self.assertEqual(
            fight.actors[8].native_death_status["last_writer"], "owned.aTS.F.type0"
        )
        self.assertIsNotNone(current_registry(fight).slots[old_slot])
