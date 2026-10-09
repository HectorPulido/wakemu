import unittest
from wakfu_server.combat_normal_execution_origin import (
    normal_execution_origin,
    normal_root_context,
)


class NormalExecutionOriginTests(unittest.TestCase):
    def test_server_policy_preserves_original_constructor_bytes(self):
        origin = normal_execution_origin(
            dict(actor_id=7, spell_id=1415, evaluation_level=20)
        )
        self.assertEqual(
            origin.context_payload.hex(),
            "0800100020ffffffffffffffffff0128013000380040004800",
        )
        self.assertEqual(
            normal_root_context(origin, caster_id=7, spell_id=1415, level=20),
            origin.context_payload,
        )

    def test_existing_native_context_is_not_replaced_and_wrong_cast_rejects(self):
        origin = normal_execution_origin(
            dict(actor_id=7, spell_id=1415, evaluation_level=20)
        )
        incoming = bytes.fromhex("0801")
        self.assertIs(
            normal_root_context(
                origin, caster_id=7, spell_id=1415, level=20, existing_payload=incoming
            ),
            incoming,
        )
        with self.assertRaises(ValueError):
            normal_root_context(origin, caster_id=8, spell_id=1415, level=20)
