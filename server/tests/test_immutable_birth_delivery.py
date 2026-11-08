import copy
import unittest
from unittest.mock import patch

from test_rift_native_wave import RiftNativeWaveTests
from wakfu_server import rift_npc_creation
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.rift_combat_adapter import creation_delivery, creation_replay


class ImmutableBirthDeliveryTests(unittest.TestCase):
    def test_native_bytes_legacy_checkpoint_and_custom_fallback(self):
        fixture = RiftNativeWaveTests()
        fight = fixture.pending_fight()
        packets = rift_npc_creation.install_native_wave(
            fight, [fixture.monster(-201, 3)], initialize_actor=lambda *args: []
        )
        delivery = fight.native_rift_creation_deliveries[-201]
        self.assertIs(type(delivery), tuple)
        self.assertTrue(
            all(
                type(row) is tuple and type(row[0]) is int and type(row[1]) is bytes
                for row in delivery
            )
        )
        self.assertIs(creation_delivery(fight, -201), delivery)
        self.assertEqual(creation_replay(fight), tuple(packets))
        self.assertEqual(creation_replay(fight, world_only=True), (packets[0],))
        copied = copy.deepcopy((fight.native_rift_creation_deliveries, delivery))
        self.assertIsNot(copied[0], fight.native_rift_creation_deliveries)
        self.assertIs(copied[0][-201], delivery)
        self.assertIs(copied[1], delivery)
        immutable_snapshot = snapshot(fight)
        legacy = [
            dict(opcode=opcode, payload_hex=payload.hex())
            for opcode, payload in packets
        ]
        fight.native_rift_creation_deliveries[-201] = legacy
        self.assertEqual(snapshot(fight), immutable_snapshot)
        self.assertEqual(creation_delivery(fight, -201), delivery)
        legacy[1]["payload_hex"] = "00"
        with self.assertRaises(ValueError):
            creation_replay(fight)
        for bad in (
            [delivery[0], delivery[1]],
            (list(delivery[0]), delivery[1]),
            ((delivery[0][0], bytearray(delivery[0][1])), delivery[1]),
        ):
            fight.native_rift_creation_deliveries[-201] = bad
            with self.assertRaises(ValueError):
                creation_delivery(fight, -201)

        class CustomBytes(bytes):
            pass

        original = rift_npc_creation.creation_packets

        def custom_packets(*args, **kwargs):
            return tuple(
                (opcode, CustomBytes(payload))
                for opcode, payload in original(*args, **kwargs)
            )

        custom = fixture.pending_fight()
        with patch.object(rift_npc_creation, "creation_packets", custom_packets):
            custom_result = rift_npc_creation.install_native_wave(
                custom, [fixture.monster(-201, 3)], initialize_actor=lambda *args: []
            )
        self.assertIs(type(custom.native_rift_creation_deliveries[-201]), list)
        self.assertEqual(creation_replay(custom), tuple(custom_result))
        self.assertEqual(
            snapshot(custom)["native_rift_creation_deliveries"],
            immutable_snapshot["native_rift_creation_deliveries"],
        )
