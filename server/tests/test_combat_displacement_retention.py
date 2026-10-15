"""Focused eXD/eXJ retained push and pull lifecycle regression."""

import unittest
from copy import deepcopy

import test_combat_displacement as displacement_fixture
from wakfu_server.combat_displacement import NativeDisplacementHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext


class RecordingPackets(list):
    def __init__(self, fight):
        super().__init__()
        self.fight = fight
        self.record_existed_at_append = []

    def append(self, packet):
        self.record_existed_at_append.append(bool(self.fight.owned_stat_effects))
        super().append(packet)


class RecordingLifecycle:
    def __init__(self, fight):
        self.fight = fight
        self.phases = []
        self.registered = []
        self.completed = []

    def phase(self, effect, invocation, *, uid, value, channel):
        self.phases.append((uid, value, channel))

    def register_applied(self, effect, invocation, uid):
        self.registered.append((uid, invocation.native_running_uid))
        assert uid in self.fight.owned_stat_effects

    def displacement_completed(self, effect, invocation, *, uid, value, moved):
        self.completed.append((uid, value, tuple(moved)))


class RetainedDisplacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        displacement_fixture.NativeDisplacementTests.setUpClass()

    def setUp(self):
        base = displacement_fixture.NativeDisplacementTests()
        base.setUp()
        self.base = base
        self.fight = base.preview
        self.fight.native_effect_uid_next = 900
        self.packets = RecordingPackets(self.fight)
        self.lifecycle = RecordingLifecycle(self.fight)
        self.context = lambda effect, invocation: StatExecutionContext(
            True, True, None, True, b""
        )
        self.handler = NativeDisplacementHandler(
            self.fight,
            self.packets,
            action_id=77,
            allocate_uid=self.fight.allocate_effect_uid,
            authority=base.authority,
            selected_surface=base.selected_surface,
            context=self.context,
        )
        self.handler.event_lifecycle = self.lifecycle
        self.effect = deepcopy(base.effects["358000"])
        self.effect["native_execution_mode"] = 0
        self.effect["effect_class"] = 300
        self.effect["parameters"] = [1, 0]
        self.effect["parameter_count"] = 1

    def invocation(self):
        return EffectInvocation(
            93624,
            1,
            7,
            -7,
            (4, 0, 0),
            native_context_hex="0800100020ffffffffffffffffff0128013000380040004800",
        )

    def test_mode_zero_push_is_owned_before_delivery_and_removal_keeps_position(self):
        invocation = self.invocation()
        original_position = self.fight.actors[-7].position

        self.assertTrue(self.handler(self.effect, None, invocation))
        self.assertEqual(self.fight.actors[-7].position, (5, 0, 0))
        self.assertEqual(self.packets.record_existed_at_append, [True])
        self.assertEqual(self.packets[0][0], 12613)
        self.assertEqual(self.packets[0][1][12], 0)  # eIK=false: retain, do not replay.
        self.assertEqual(len(self.fight.owned_stat_effects), 1)
        uid, row = next(iter(self.fight.owned_stat_effects.items()))
        self.assertEqual(row["family"], "eXD")
        self.assertEqual(row["effect_class"], 300)
        self.assertEqual(row["actual"], 1)
        from wakfu_server.combat_displacement import displacement_additional
        from wakfu_server.combat_effect_removal import _identity_fields

        original_messages = {}
        original_fields = _identity_fields(
            bytes.fromhex(row["payload"]),
            integer_fields=(1, 2, 3, 4, 6, 7),
            messages=original_messages,
        )
        self.assertEqual(
            (
                original_fields[1],
                original_fields[2],
                original_fields[3],
                original_fields[4],
            ),
            (uid, uid, 93624, 1),
        )
        self.assertEqual(
            original_messages[8],
            displacement_additional(300, path=[(5, 0, 0)]),
        )
        from wakfu_server.combat_effects import _varint

        context_blob = bytes.fromhex(invocation.native_context_hex)
        context_field = b"\x6a" + _varint(len(context_blob)) + context_blob
        self.assertIn(context_field, bytes.fromhex(row["payload"]))
        self.assertEqual(self.lifecycle.registered, [(uid, uid)])
        self.assertEqual(self.lifecycle.completed[0][0:2], (uid, 1))
        self.assertEqual([phase[2] for phase in self.lifecycle.phases], [1, 2, 3, 4])

        stat_handler = NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {}},
            action_id=77,
            allocate_uid=self.fight.allocate_effect_uid,
            context=self.context,
        )
        payload_before_removal = row["payload"]
        stat_handler.remove(uid)
        self.assertEqual(self.fight.actors[-7].position, (5, 0, 0))
        self.assertNotIn(uid, self.fight.owned_stat_effects)
        self.assertEqual(self.packets[-1][0], 13560)
        removal_body = self.packets[-1][1]
        payload_size = int.from_bytes(removal_body[16:18], "big", signed=True)
        removed_messages = {}
        removed_fields = _identity_fields(
            removal_body[18 : 18 + payload_size],
            integer_fields=(1, 2, 3, 4, 6, 7),
            messages=removed_messages,
        )
        self.assertEqual(removed_fields, original_fields)
        for message_field in (5, 8):
            self.assertEqual(
                removed_messages[message_field], original_messages[message_field]
            )
        self.assertIn(context_field, removal_body[18 : 18 + payload_size])
        self.assertEqual(original_position, (4, 0, 0))

    def test_zero_duration_mode_two_remains_immediate_and_unowned(self):
        self.effect["native_execution_mode"] = 2
        self.effect["native_timing_definition"] = {
            "ryE": 0,
            "ryF": 0.0,
            "ryH": 0,
            "ryI": 0.0,
        }
        self.handler.context = lambda *_: self.fail(
            "Immediate effect requested retention context"
        )
        self.handler.event_lifecycle = None

        self.assertTrue(self.handler(self.effect, None, self.invocation()))
        self.assertEqual(self.fight.actors[-7].position, (5, 0, 0))
        self.assertEqual(self.fight.owned_stat_effects, {})
        self.assertEqual(self.packets[0][0], 12613)

    def test_retained_mode_rejects_unverified_context(self):
        self.handler.context = lambda *_: object()
        with self.assertRaisesRegex(ValueError, "Unverified retained"):
            self.handler(self.effect, None, self.invocation())
        self.assertEqual(self.fight.actors[-7].position, (4, 0, 0))
        self.assertEqual(self.packets, [])


if __name__ == "__main__":
    unittest.main()
