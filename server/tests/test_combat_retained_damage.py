"""Retain actual eXt186714 without repeating or reversing applied LIGHT damage."""
import json
import struct
import unittest
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace
import test_combat_damage_handler as fixtures
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_native_timing_context import native_time_payload
from wakfu_server.combat_state_timing import StateTimer
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_effects import direct_damage


class RetainedDamageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DamageHandlerTests()
        self.fixture.setUp()
        self.fight = self.fixture.fight
        self.handler = self.fixture.handler
        self.packets = self.fixture.packets
        self.effect = json.loads(
            (
                Path(__file__).parent / "fixtures/native_retained_damage186714.json"
            ).read_text()
        )
        self.invocation = replace(self.fixture.invocation, reference=186714, level=42)
        self.fight.actors[7].effect_stats.update({21: 0, 22: 0, 23: 0, 24: 0})
        self.fight.actors[7].effect_stats[100] = 0
        self.fight.actors[-7].effect_stats.update({97: 0, 92: 0})
        self.timer = StateTimer(-7, 2, "start")
        self.retention = NativeRetainedRuntime(
            self.fight,
            self.packets,
            plan={"native_retained_container": {"present": False}},
            state_catalog={},
            action_id=1,
            timing=SimpleNamespace(
                stat=lambda *args: StatExecutionContext(
                    True, True, None, True, native_time_payload(self.timer), self.timer
                )
            ),
            metadata={
                "states": {},
                "spells": {},
                "effects": {
                    "186714": json.loads(
                        (
                            Path(__file__).parent
                            / "fixtures/native_retained_damage186714_metadata.json"
                        ).read_text()
                    )
                },
            },
        )
        self.handler.retention = self.retention

    def test_actual_light_definition_keeps_uid_clock_wire_and_no_hp_reversal(self):
        before = self.fight.actors[-7].hp
        self.assertTrue(
            self.retention.wrap(self.handler)(self.effect, {}, self.invocation)
        )
        self.assertLess(self.fight.actors[-7].hp, before)
        after = self.fight.actors[-7].hp
        self.assertEqual(len(self.packets), 1)
        packet = self.packets[0][1]
        self.assertEqual(packet[12], 1)
        self.assertEqual(struct.unpack_from(">i", packet, 13)[0], 1083)
        messages = {}
        fields = _identity_fields(packet[19:], messages=messages)
        self.assertEqual(fields[1], 99)
        from wakfu_server.wire import proto_fields

        wire = {tag >> 3: value for tag, value in proto_fields(packet[19:])}
        self.assertEqual(wire[11], native_time_payload(self.timer))
        row = self.fight.native_owned_group_effects[99]
        self.assertEqual(row["payload"], packet[19:].hex())
        self.assertEqual(row["timer"], vars(self.timer))
        self.assertEqual([e.uid for e in self.retention.view().entries], [99])
        self.retention.remove_group(99)
        self.assertEqual(self.fight.actors[-7].hp, after)
        self.assertNotIn(99, self.fight.native_retained_records)
        self.assertEqual(self.packets[-1][0], 13560)

    def test_retained_damage_without_owner_fails_before_hp_mutation(self):
        self.handler.retention = None
        before = self.fight.actors[-7].hp
        with self.assertRaisesRegex(ValueError, "Missing retained native damage owner"):
            self.handler(self.effect, {}, self.invocation)
        self.assertEqual(self.fight.actors[-7].hp, before)
        self.assertFalse(self.packets)

    def test_central_removal_uses_registered_damage_owner_without_undo(self):
        self.retention.wrap(self.handler)(self.effect, {}, self.invocation)
        self.retention.stat_handler = SimpleNamespace(fight=self.fight)
        before = self.fight.actors[-7].hp
        self.retention.removal(self.retention.view()).remove([99])
        self.assertEqual(self.fight.actors[-7].hp, before)
        self.assertFalse(self.fight.native_owned_group_effects)
        self.assertEqual(self.packets[-1][0], 13560)

    def test_retained_wire_rejects_foreign_runner_identity(self):
        with self.assertRaisesRegex(ValueError, "identity differs"):
            direct_damage(
                77,
                1,
                uid=99,
                generic_effect=186714,
                element=1083,
                caster_id=7,
                target_id=-7,
                damage=1,
                retained_payload=b"",
            )
