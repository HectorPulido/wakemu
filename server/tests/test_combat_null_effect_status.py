import unittest
import json
import struct
from pathlib import Path
from types import SimpleNamespace as NS
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.combat_effects import _integer


class NullExecutionStatusTests(unittest.TestCase):
    def setUp(self):
        self.actor = NS(id=7, hp=20)
        self.fight = NS(
            id=8,
            phase="active",
            current=7,
            actors={7: self.actor},
            owned_stat_effects={},
        )
        self.packets = []
        self.timing = native_time_payload()
        self.handler = NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {"400": {"runner": "eXE"}}},
            action_id=1,
            allocate_uid=lambda: 100,
            context=lambda *a: StatExecutionContext(
                True, True, None, True, self.timing
            ),
        )
        self.invocation = EffectInvocation(999, 200, 7, 7, (0, 0, 0))

    def test_levelzero_status_retained_and_removal_payload_exact(self):
        self.assertTrue(
            self.handler(
                dict(effect_class=400, parameters=[7.0, 9.0, 123.0, 0.0]),
                {},
                self.invocation,
            )
        )
        entry = self.fight.owned_stat_effects[100]
        self.assertEqual((entry["actual"], entry["execution_status"]), (0, 7))
        payload = bytes.fromhex(entry["payload"])
        self.assertIn(self.timing + _integer(2, 7) + _integer(5, 1), payload)
        self.handler.remove(100)
        self.assertEqual([op for op, _ in self.packets], [12613, 13560])
        self.assertIn(payload, self.packets[1][1])
        self.assertEqual(self.actor.hp, 20)

    def test_signed_byte_and_fresh_default(self):
        self.handler(
            dict(effect_class=400, parameters=[130.0, 0.0]), {}, self.invocation
        )
        self.assertEqual(self.fight.owned_stat_effects[100]["execution_status"], -126)
        self.fight.owned_stat_effects.clear()
        self.handler(dict(effect_class=400, parameters=[]), {}, self.invocation)
        self.assertEqual(self.fight.owned_stat_effects[100]["execution_status"], -1)

    def test_malformed_parameter_pairs_reject_before_ownership(self):
        with self.assertRaises(ValueError):
            self.handler(dict(effect_class=400, parameters=[7.0]), {}, self.invocation)
        self.assertEqual((self.packets, self.fight.owned_stat_effects), ([], {}))

    def test_native_boss_appearance_eXE400_retains_and_removes_same_visible_carrier(
        self,
    ):
        from wakfu_server.combat_effect_removal import _identity_fields

        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/native_appearance_change_effects.json"
            ).read_text()
        )
        references = (272571, 272574, 272577, 292958, 380625)
        expected_actions = {
            272571: 4085,
            272574: 4089,
            272577: 4094,
            292958: 4269,
            380625: 5629,
        }
        actor = NS(id=7, hp=20)
        fight = NS(
            id=88,
            phase="active",
            current=7,
            actors={7: actor},
            owned_stat_effects={},
        )
        packets = []
        timing = native_time_payload()
        uid_next = iter(range(900, 900 + len(references)))

        for reference in references:
            effect = fixture["effects"][str(reference)]
            self.assertEqual(effect["effect_class"], 400)
            action_ids = {
                action["id"]
                for channel in ("rzc", "rze", "rzf", "rzh")
                for action in effect["native_hmi_actions"][channel]
                if action["type"] == "APPEARANCE_CHANGE"
            }
            self.assertEqual(action_ids, {expected_actions[reference]})
            next_uid = [next(uid_next)]
            handler = NativeStatHandler(
                fight,
                packets,
                {"effects": {"400": {"runner": "eXE"}}},
                action_id=4,
                allocate_uid=lambda uid=next_uid[0]: uid,
                context=lambda *args: StatExecutionContext(
                    True, True, None, True, timing
                ),
            )
            invocation = EffectInvocation(
                reference,
                1,
                7,
                7,
                (0, 0, 0),
                base_uid=reference + 100000,
                state_uid=reference + 200000,
            )
            self.assertTrue(handler(effect, {}, invocation))
            entry = fight.owned_stat_effects[next_uid[0]]
            self.assertEqual(entry["state_uid"], invocation.state_uid)
            self.assertEqual(entry["caster_id"], 7)
            self.assertEqual(entry["target_id"], 7)
            owned_payload = bytes.fromhex(entry["payload"])
            opcode, application = packets[-1]
            self.assertEqual(opcode, 12613)
            self.assertEqual(application[12], 0)  # Retain; don't replay eXE.
            self.assertEqual(struct.unpack_from(">i", application, 13)[0], 400)
            delivered = _identity_fields(application[19:])
            self.assertEqual(
                (delivered[1], delivered[2], delivered[3], delivered[6], delivered[7]),
                (next_uid[0], invocation.base_uid, reference, 7, 7),
            )
            handler.remove(next_uid[0])
            self.assertNotIn(next_uid[0], fight.owned_stat_effects)
            self.assertEqual(packets[-1][0], 13560)
            self.assertIn(owned_payload, packets[-1][1])

        self.assertEqual([opcode for opcode, _ in packets], [12613, 13560] * 5)
