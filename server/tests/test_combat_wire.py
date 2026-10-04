import struct
import unittest
from wakfu_server.combat_wire import (
    actor_state,
    decode_actor_state,
    bootstrap,
    decode_bootstrap,
)


class CombatWireTests(unittest.TestCase):
    def test_owned_bootstrap_roundtrip(self):
        value = dict(
            fight_id=7,
            kind=70,
            bqh=1134,
            myo=0,
            myp=-200,
            myD=b"local terrain",
            myG=b"",
            myI=-200,
            myJ=100,
            compact=False,
            participants=[
                dict(
                    actor_id=100,
                    myB=0,
                    myn=1,
                    myC=1,
                    myE=b"own actor",
                    myF=b"own effects",
                ),
                dict(
                    actor_id=-200,
                    myB=1,
                    myn=0,
                    myC=1,
                    myE=b"own monster",
                    myF=b"own effects",
                ),
            ],
            myH=[(1, -200)],
            myM=[0],
            myN=[1],
            myK=[],
        )
        self.assertEqual(decode_bootstrap(bootstrap(value)), value)
        with self.assertRaises(ValueError):
            decode_bootstrap(bootstrap(value) + b"\x00")
        with self.assertRaises(ValueError):
            decode_bootstrap(bootstrap(value)[:-1])

    def test_actor_envelopes_signed_lengths(self):
        for opcode in (13912, 12873):
            blob = actor_state(opcode, 7, 100, b"owned data")
            self.assertEqual(
                decode_actor_state(opcode, blob),
                dict(fight_id=7, actor_id=100, state=b"owned data"),
            )
            with self.assertRaises(ValueError):
                decode_actor_state(opcode, blob + b"\x00")
        with self.assertRaises(ValueError):
            actor_state(12873, 7, 100, b"x" * 32768)
        with self.assertRaises(ValueError):
            decode_actor_state(12873, struct.pack(">iqh", 7, 100, -1))
        with self.assertRaises(ValueError):
            actor_state(12, 7, 100, b"")

    def test_owned_arena_respects_selected_cells_and_placement(self):
        from wakfu_server.combat_wire import arena, topology, decode_topology

        value = arena(
            1134,
            1,
            [(7, 14, -1), (8, 14, -1), (7, 15, 0)],
            {0: (7, 14, -1), 1: (7, 15, 0)},
        )
        self.assertEqual(value["cell_masks"], [0, 0, 0, 256])
        self.assertEqual(value["cell_flags"], bytes([0, 255, 1, 255]))
        self.assertEqual(decode_topology(topology(value)), value)
        with self.assertRaises(ValueError):
            arena(1134, 1, [(7, 14, -1)], {0: (7, 14, -1), 1: (7, 14, -1)})
        with self.assertRaises(ValueError):
            arena(1134, 1, [(7, 14, -1), (8, 14, -1)], {0: (7, 14, -1), 1: (8, 14, 0)})
