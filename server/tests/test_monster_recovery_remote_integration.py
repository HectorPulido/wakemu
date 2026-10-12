"""Private patched serializer through actual retained-population validation."""
from pathlib import Path
import importlib.util
import sys
from dataclasses import replace, asdict
import pickle
from copy import deepcopy
import unittest
from test_combat_remote_effects_active import ActiveRemoteEffectTests
from wakfu_server.combat_state_carrier import state_carrier_payload
from wakfu_server.combat_native_timing_context import native_time_payload

import wakfu_server.combat_remote_effects as remote


class PrivateRemoteIntegrationTests(unittest.TestCase):
    def fixture(self):
        fight = ActiveRemoteEffectTests().fixture()
        actor = fight.actors[7]
        row = actor.state_ledger.entries[0]
        actor.state_ledger._entries = (
            replace(
                row,
                realtime_duration=600000,
                realtime_deadline_ms=601000,
                realtime_in_combat=True,
            ),
        )
        fight.state_wire_payloads[700] = state_carrier_payload(
            uid=700,
            base_uid=700,
            caster_id=7,
            target_id=7,
            state_id=1234,
            level=1,
            native_turn_clock=-1,
            native_realtime_remaining=600000,
            timing_payload=native_time_payload(realtime_remaining=600000),
        ).hex()
        fight.native_retained_records[700]["generic_effect"] = -1
        return fight

    def test_actual_retained_validation_serializer_emits_remaining_without_mutation(
        self,
    ):
        fight = self.fixture()
        before = pickle.dumps(fight)
        records = remote.decode_remote_effects(
            remote.active_actor_effects(fight, 7, now_milliseconds=1001)
        )
        self.assertEqual(records[0].effect_class, 310)
        self.assertEqual(records[0].remaining_milliseconds, 599999)
        self.assertEqual(records[0].payload.hex(), fight.state_wire_payloads[700])
        records = remote.decode_remote_effects(
            remote.active_actor_effects(fight, 7, now_milliseconds=601001)
        )
        self.assertEqual(records[0].remaining_milliseconds, 0)
        self.assertEqual(pickle.dumps(fight), before)

    def test_unproven_clock_or_carrier_rejects_actual_serializer_atomically(self):
        fight = self.fixture()
        before = pickle.dumps(fight)
        with self.assertRaises(ValueError):
            remote.active_actor_effects(fight, 7)
        self.assertEqual(pickle.dumps(fight), before)
        fight.actors[7].state_ledger._entries = (
            replace(fight.actors[7].state_ledger.entries[0], realtime_deadline_ms=None),
        )
        before = pickle.dumps(fight)
        with self.assertRaises(ValueError):
            remote.active_actor_effects(fight, 7, now_milliseconds=1001)
        self.assertEqual(pickle.dumps(fight), before)
