"""Complete active reconnect effects, independent of player stat encoding."""
import unittest
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_remote_effects import (
    active_actor_effects,
    decode_remote_effects,
)
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import remove_owned_group
from wakfu_server.combat_stat_effects import owned_effect_payload
from wakfu_server.combat_state_ledger import RunningState, StateLedger
from test_combat_retained_cell_groups import RetainedCellGroupTests


class ActiveRemoteEffectTests(unittest.TestCase):
    def test_runtime_state_carrier_parent_pl_matches_retained_snapshot(self):
        from wakfu_server.combat_running_container import running_container_scope
        from wakfu_server.combat_state_carrier import state_carrier_payload

        fight = self.fixture()
        container_id = (4807 << 16) | 200
        with running_container_scope(
            {"container_present": True, "container_type": 11}, container_id
        ):
            payload = state_carrier_payload(
                uid=700,
                base_uid=700,
                caster_id=7,
                target_id=7,
                state_id=1234,
                level=1,
                native_turn_clock=-1,
                native_realtime_remaining=0,
            )
        fight.state_wire_payloads[700] = payload.hex()
        fight.native_retained_records[700].update(
            generic_effect=-1,
            container_present=True,
            container_type=11,
            container_id=container_id,
            container_is_spell=True,
            spell_protected=False,
        )
        records = decode_remote_effects(active_actor_effects(fight, 7))
        self.assertEqual(records[0].payload, payload)
        fight.native_retained_records[700]["container_id"] += 1
        with self.assertRaisesRegex(ValueError, "container differs from ownership"):
            active_actor_effects(fight, 7)

    def fixture(self):
        fight, _ = RetainedCellGroupTests().fixture()
        fight.phase = "active"
        actor = fight.actors[7]
        actor.controlled, actor.owner_id = True, 3
        actor.state_ledger = StateLedger(7)
        actor.state_ledger._entries = (
            RunningState(700, 1234, 1, 7, 7, -1, "target", False, (), -1, True, None),
        )
        for uid, family in ((903, 1066), (902, 1066), (701, 500), (700, 310)):
            payload = owned_effect_payload(
                uid=uid,
                base_uid=None,
                generic_effect=12000 + uid,
                caster_id=7,
                target_id=7,
                value=2,
                timing_payload=b"\x08\x00",
            )
            if family == 310:
                fight.state_wire_payloads[uid] = payload.hex()
            else:
                fight.owned_stat_effects[uid] = dict(
                    target_id=7,
                    effect_class=family,
                    state_uid=None,
                    payload=payload.hex(),
                )
            fight.native_retained_records[uid] = asdict(
                RetainedEffect(
                    uid, 7, family, 12000 + uid, manager_id=7, container_present=False
                )
            )
            fight.native_retained_order.append(uid)
        return fight

    def test_four_families_and_stacked_category_preserve_exact_population(self):
        fight = self.fixture()
        before = deepcopy(fight.__dict__)
        body = active_actor_effects(fight, 7)
        records = decode_remote_effects(body)
        self.assertEqual(
            [row.effect_class for row in records], [310, 949, 1066, 1066, 500]
        )
        self.assertEqual(
            [_identity_fields(row.payload)[1] for row in records],
            [700, 901, 903, 902, 701],
        )
        for row in records:
            uid = _identity_fields(row.payload)[1]
            original = (
                fight.state_wire_payloads.get(uid)
                or fight.owned_stat_effects.get(uid, {}).get("payload")
                or fight.native_owned_group_effects[uid]["payload"]
            )
            self.assertEqual(row.payload.hex(), original)
            self.assertEqual(row.remaining_milliseconds, 0)
        self.assertEqual(active_actor_effects(fight, 7), body)
        # Compare plain data and ledger entries without assuming object equality.
        self.assertEqual(
            fight.native_retained_records, before["native_retained_records"]
        )
        self.assertEqual(fight.native_retained_order, before["native_retained_order"])
        self.assertEqual(
            fight.actors[7].state_ledger.entries,
            before["actors"][7].state_ledger.entries,
        )

    def test_actual_group_removal_disappears_from_complete_snapshot(self):
        fight = self.fixture()
        packets = []
        remove_owned_group(fight, packets, action_id=3, uid=901)
        self.assertEqual(packets[0][0], 13560)
        self.assertEqual(
            [
                _identity_fields(row.payload)[1]
                for row in decode_remote_effects(active_actor_effects(fight, 7))
            ],
            [700, 903, 902, 701],
        )

    def test_missing_or_foreign_payload_identity_rejects_instead_of_partial_snapshot(
        self,
    ):
        for failure in ("missing", "uid"):
            fight = self.fixture()
            if failure == "missing":
                del fight.native_retained_records[903]
            else:
                fight.owned_stat_effects[903]["payload"] = fight.owned_stat_effects[
                    902
                ]["payload"]
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                active_actor_effects(fight, 7)

    def test_adapter_active_boundary_returns_complete_effects_not_empty_snapshot(self):
        from wakfu_server.combat_session_adapter import CombatSessionAdapter

        fight = self.fixture()
        adapter = object.__new__(CombatSessionAdapter)
        adapter.store = SimpleNamespace(
            character=lambda owner, identity: {"id": identity}
        )
        with patch(
            "wakfu_server.combat_actor.actual_actor_stats", return_value=b"stats"
        ), patch("wakfu_server.breed_resources.live_wp", return_value=(6, 6)):
            stats, effects = adapter.actor_payload(fight, fight.actors[7], None)
        self.assertEqual(stats, b"stats")
        self.assertEqual(effects, active_actor_effects(fight, 7))
        self.assertEqual(len(decode_remote_effects(effects)), 5)
