import unittest
from wakfu_server.combat_xelor_passive import unlock_packet, initial_spell_unlocks


class XelorPassiveTests(unittest.TestCase):
    def test_additional_payload_matches_native_builder(self):
        packet = unlock_packet(
            1, 2, uid=7, actor_id=9, generic_effect=313107, spell_id=5345, slot=0
        )
        # Offline ij.MR().ek(5345).en(-1).ep(2).eq(0).MX().toByteArray().
        self.assertTrue(
            packet.endswith(bytes.fromhex("50e12970ffffffffffffffffff01980102a00100"))
        )

    def test_unlocks_use_native_reference_uids_and_conditions(self):
        args = dict(
            effect_uid=100, has_action933=False, instance_id=0, passive6755_applied=True
        )
        result = initial_spell_unlocks(dict(id=7, breed=5, level=19), 1, 2, **args)
        self.assertEqual(
            [s["uid"] for s in result["special_spells"]], [5345, 3909, 7794]
        )
        self.assertEqual(len(result["packets"]), 3)
        result = initial_spell_unlocks(
            dict(id=7, breed=5, level=19), 1, 2, **dict(args, instance_id=862)
        )
        self.assertEqual(result["packets"], [])
        with self.assertRaises(ValueError):
            initial_spell_unlocks(
                dict(id=7, breed=5, level=19),
                1,
                2,
                **dict(args, passive6755_applied=False)
            )
