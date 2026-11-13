import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_lesson_state
from wakfu_server.combat_running_container import (
    running_container_payload,
    running_container_scope,
)


class LessonStateCarrierTests(unittest.TestCase):
    def test_remove_clears_real_state_entry_wire_payload_and_retained_carrier(self):
        from wakfu_server.combat_state_carrier import state_carrier_payload

        entry = SimpleNamespace(uid=42, reference=8016)

        class Ledger:
            entries = [entry]

            def remove(self, uid):
                self.entries = [row for row in self.entries if row.uid != uid]

        target = SimpleNamespace(state_ledger=Ledger())
        payload = state_carrier_payload(
            uid=42,
            base_uid=None,
            caster_id=1,
            target_id=-3,
            state_id=8016,
            level=1,
            native_turn_clock=-1,
            native_realtime_remaining=0,
        )
        fight = SimpleNamespace(
            id=7,
            actors={-3: target},
            state_wire_payloads={42: payload.hex()},
            native_retained_records={42: {"target_id": -3, "effect_class": 310}},
            native_retained_order=[42],
        )
        packets = []

        rii_lesson_state.remove(
            fight, target_id=-3, uid=42, action_id=9, packets=packets
        )

        self.assertEqual(target.state_ledger.entries, [])
        self.assertEqual(fight.state_wire_payloads, {})
        self.assertEqual(fight.native_retained_records, {})
        self.assertEqual(fight.native_retained_order, [])
        self.assertEqual([opcode for opcode, _ in packets], [13560])

    def test_reconstructed_carrier_does_not_inherit_active_spell_container(self):
        target = SimpleNamespace(state_ledger=SimpleNamespace(entries=[]))
        fight = SimpleNamespace(
            phase="active",
            id=7,
            actors={1: object(), -3: target},
            allocate_effect_uid=lambda: 42,
            state_wire_payloads={},
            native_retained_records={},
            native_retained_order=[],
            apply_state=Mock(
                return_value=SimpleNamespace(
                    applied=SimpleNamespace(retained=True), removed=[]
                )
            ),
        )
        catalog = {
            "states": {
                "8015": {
                    "maximum_level": 1,
                    "duration_base": -1,
                    "effect_ids": [367316],
                }
            },
            "effects": {"367316": {"effect_class": 400}},
        }
        metadata = {"states": {"8015": {"unremovable": False, "dispellable": True}}}

        def payload(**_kwargs):
            self.assertEqual(running_container_payload(), b"")
            return b"native"

        packets = []
        with patch(
            "wakfu_server.spell_audit.states_catalog", return_value=catalog
        ), patch(
            "wakfu_server.combat_retained_runtime.native_retained_metadata",
            return_value=metadata,
        ), patch(
            "wakfu_server.combat_state_carrier.state_carrier_payload",
            side_effect=payload,
        ), patch(
            "wakfu_server.combat_state_carrier.state_carrier_application",
            return_value=b"packet",
        ), running_container_scope(
            {"container_present": True, "container_type": 7}, 7967
        ):
            self.assertNotEqual(running_container_payload(), b"")
            uid = rii_lesson_state.install(
                fight,
                owner_id=1,
                target_id=-3,
                reference=8015,
                level=1,
                action_id=5,
                packets=packets,
            )
            self.assertNotEqual(running_container_payload(), b"")
        self.assertEqual(uid, 42)
        self.assertFalse(fight.native_retained_records[42]["container_present"])
        self.assertEqual(packets, [(12613, b"packet")])

    def test_terminal_cleanup_removes_state_and_spell_only_for_owner(self):
        from wakfu_server import rii_lesson_grants

        target = SimpleNamespace(
            state_ledger=SimpleNamespace(entries=[SimpleNamespace(uid=42)])
        )
        contract = {
            "owner": 1,
            "target": -3,
            "initialized": True,
            "state_uid": 42,
            "visible_state": 8016,
            "grant_uids": [51],
        }
        fight = SimpleNamespace(
            actors={-3: target},
            rii_states_lesson_contract=contract,
            state_wire_payloads={},
            native_retained_records={},
            native_retained_order=[],
        )
        with patch.object(rii_lesson_state, "remove") as state_remove, patch.object(
            rii_lesson_grants, "remove"
        ) as grant_remove:
            self.assertFalse(
                rii_lesson_grants.remove_states_if_present(
                    fight, [], action_id=7, owner_ids={2}
                )
            )
            state_remove.assert_not_called()
            packets = []
            self.assertTrue(
                rii_lesson_grants.remove_states_if_present(
                    fight, packets, action_id=7, owner_ids={1}
                )
            )
        state_remove.assert_called_once_with(
            fight, target_id=-3, uid=42, action_id=7, packets=packets
        )
        grant_remove.assert_called_once_with(
            fight, 1, [51], packets, action_id=7, lesson="states"
        )
        self.assertNotIn("state_uid", contract)


if __name__ == "__main__":
    unittest.main()
