"""Reuse the validated manager projection without a second historical scan."""
import struct
import unittest
from unittest.mock import patch
from copy import deepcopy

from wakfu_server import combat_remote_effects as current
from wakfu_server.combat_retained_runtime import native_retained_condition_effects
from wakfu_server.combat_effect_removal import _identity_fields
from test_combat_remote_effects_active import ActiveRemoteEffectTests


class RemoteEffectsLocalityTests(unittest.TestCase):
    def test_bytes_order_mutations_malformed_and_no_postvalidation_history_scan(self):
        fixture = ActiveRemoteEffectTests()
        fight = fixture.fixture()
        expected_order = (700, 901, 903, 902, 701)
        for change in ("initial", "reorder", "payload", "remove"):
            if change == "reorder":
                fight.native_retained_order.reverse()
                expected_order = (700, 701, 902, 903, 901)
            elif change == "payload":
                # Same UID, changed current payload; no cached serialized bytes.
                from wakfu_server.combat_stat_effects import owned_effect_payload

                fight.owned_stat_effects[903]["payload"] = owned_effect_payload(
                    uid=903,
                    base_uid=None,
                    generic_effect=12903,
                    caster_id=7,
                    target_id=7,
                    value=8,
                    timing_payload=b"\x08\x00",
                ).hex()
            elif change == "remove":
                from wakfu_server.combat_retained_runtime import remove_owned_group

                remove_owned_group(fight, [], action_id=3, uid=901)
                expected_order = (700, 701, 902, 903)
            expected = struct.pack(">h", len(expected_order))
            for uid in expected_order:
                metadata = fight.native_retained_records[uid]
                payload = bytes.fromhex(
                    fight.state_wire_payloads.get(uid)
                    or fight.owned_stat_effects.get(uid, {}).get("payload")
                    or fight.native_owned_group_effects[uid]["payload"]
                )
                expected += (
                    struct.pack(">ih", metadata["effect_class"], len(payload))
                    + payload
                    + bytes(4)
                )
            actual = current.active_actor_effects(fight, 7)
            self.assertEqual(actual, expected, change)
            self.assertEqual(
                tuple(
                    _identity_fields(row.payload)[1]
                    for row in current.decode_remote_effects(actual)
                ),
                expected_order,
            )

        expected = current.active_actor_effects(fight, 7)
        original_order = fight.native_retained_order

        class NoSecondIteration(list):
            def __iter__(self):
                raise AssertionError(
                    "remote serializer rescanned history after validation"
                )

        def validate_then_guard(actual, actor_id):
            result = native_retained_condition_effects(actual, actor_id)
            actual.native_retained_order = NoSecondIteration(original_order)
            return result

        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_condition_effects",
            side_effect=validate_then_guard,
        ):
            self.assertEqual(current.active_actor_effects(fight, 7), expected)
        fight.native_retained_order = original_order
        for corruption in ("missing", "foreign_payload", "container"):
            broken = deepcopy(fight)
            if corruption == "missing":
                del broken.native_retained_records[903]
            elif corruption == "foreign_payload":
                broken.owned_stat_effects[903]["payload"] = broken.owned_stat_effects[
                    902
                ]["payload"]
            else:
                broken.native_retained_records[903]["container_present"] = None
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                current.active_actor_effects(broken, 7)
