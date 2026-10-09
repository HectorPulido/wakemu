import struct
import unittest
from types import SimpleNamespace

from wakfu_server.combat_entity_creation_delivery import immediate_entity_creation
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effects import _integer
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime


class ImmediateEntityCreationTests(unittest.TestCase):
    def test_immediate_creation_executes_exact_descriptor_without_retention(self):
        for family in (307, 324, 1002):
            payload = _integer(1, 81) + _integer(3, 123) + _integer(6, 7)
            opcode, body = immediate_entity_creation(47, 9, family, payload)
            self.assertEqual(opcode, 12613)
            self.assertEqual(
                struct.unpack(">iiiBih", body[:19]),
                (47, 9, -1, 1, family, len(payload)),
            )
            self.assertEqual(body[19:], payload)

    def test_normalizer_does_not_convert_immediate_uid_without_qf_record(self):
        payload = _integer(1, 81) + _integer(3, 123) + _integer(6, 7)
        observation = (
            13497,
            struct.pack(">iiiih", 47, 9, -1, 307, len(payload)) + payload,
        )
        runtime = object.__new__(NativeRetainedRuntime)
        runtime.fight = SimpleNamespace(native_retained_records={})
        runtime.packets = [observation]
        runtime.definition = lambda effect, invocation: {}
        invocation = EffectInvocation(123, 1, 7, None, (0, 0, 0))
        runtime.normalize_owned_delivery({"effect_class": 307}, invocation, 0)
        self.assertEqual(runtime.packets, [observation])
        self.assertEqual(runtime.fight.native_retained_records, {})
        runtime.packets = [immediate_entity_creation(47, 9, 307, payload)]
        before = tuple(runtime.packets)
        runtime.normalize_owned_delivery({"effect_class": 307}, invocation, 0)
        self.assertEqual(tuple(runtime.packets), before)
        self.assertEqual(runtime.fight.native_retained_records, {})

    def test_invalid_action_or_oversized_descriptor_rejects(self):
        for arguments in (
            (0, 9, 307, b"x"),
            (47, True, 307, b"x"),
            (47, 9, 307, b""),
            (47, 9, 307, bytes(32768)),
        ):
            with self.subTest(arguments=arguments[:3]), self.assertRaises(ValueError):
                immediate_entity_creation(*arguments)
