import struct
import unittest
from dataclasses import replace
from types import SimpleNamespace

from wakfu_server.combat_consume_resources import (
    NativeConsumeResourcesHandler,
    prepared_payment,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_event_replay import NativeEventSource


class ConsumeResourcesTests(unittest.TestCase):
    def test_original_eXm_eWf_signed_byte_oracle_rows(self):
        for row, expected in [
            ((6, 3, 1, 0), (1, 0)),
            ((6, 3, -1, -1), (6, 3)),
            ((0, 0, 1, 1), (0, 0)),
            ((6, 3, 99, 99), (6, 3)),
            ((200, 3, -1, -1), (0, 3)),
            ((-1, 3, -1, -1), (0, 3)),
            ((6, 200, -1, -1), (6, 0)),
        ]:
            with self.subTest(row=row):
                self.assertEqual(prepared_payment(*row), expected)

    def run_payment(self, ap, mp, frozen=frozenset()):
        actor = SimpleNamespace(
            id=7,
            ap=ap,
            mp=mp,
            max_ap=6,
            max_mp=3,
            max_hp=100,
            hp=100,
            effect_minima={2: 0, 3: 0},
            effect_maxima={2: 6, 3: 3},
            effect_stats={2: ap, 3: mp},
            effect_frozen=frozen,
        )
        fight = SimpleNamespace(id=1, phase="active", actors={7: actor})
        packets, calls, allocated = [], [], []

        def allocate():
            allocated.append(901)
            return 901

        handler = NativeConsumeResourcesHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=allocate,
            context=lambda *_: StatExecutionContext(True, True, None, False, None),
        )
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda effect, invocation, **kw: calls.append(
                (effect["effect_class"], invocation, kw)
            )
        )
        effect = dict(
            effect_class=923,
            parameters=[-1, 0, -1, 0],
            target_masks=[None] * 7,
            native_effect_flags=[],
        )
        handler(effect, (), EffectInvocation(397441, 200, 7, None, (8, 9, 10)))
        return actor, packets, calls, allocated

    def test_actual_consumption_and_direct_post_events_unowned_wire(self):
        actor, packets, calls, allocated = self.run_payment(6, 3)
        self.assertEqual((actor.ap, actor.mp), (0, 0))
        self.assertEqual(allocated, [901])
        self.assertEqual(
            [(family, kw["channel"], kw["uid"]) for family, _, kw in calls],
            [(30, 3, -1), (30, 4, -1), (923, 3, 901), (923, 4, 901)],
        )
        self.assertEqual(calls[0][2]["_event_ids"], (0, 55, 65))
        self.assertEqual(calls[0][1].native_retained_container, {"present": False})
        self.assertEqual(calls[0][1].cell, (0, 0, 0))
        self.assertEqual(calls[0][1].target_id, 7)
        self.assertIsNone(calls[2][1].target_id)
        self.assertTrue(calls[2][2]["_nullable_target"])
        opcode, wire = packets[0]
        self.assertEqual(opcode, 13497)
        self.assertEqual(
            struct.unpack(">iiiih", wire[:18]), (1, 2, -1, 30, len(wire) - 18)
        )
        fields = _identity_fields(wire[18:])
        self.assertEqual(
            wire[18:].hex(),
            "08ffffffffffffffffff0110ffffffffffffffffff0118ffffffffffffffffff01"
            "2086062a06080010001800300738075a2b080010ffffffffffffffffff01"
            "1a0f080010ffffffffffffffffff01180020ffffffffffffffffff012801",
        )
        self.assertEqual(fields[1], (1 << 64) - 1)
        self.assertEqual(fields[2], (1 << 64) - 1)
        self.assertEqual(fields[3], (1 << 64) - 1)
        self.assertEqual(fields[4], 6 | (3 << 8))

    def test_zero_and_frozen_cost_emit_post_events_without_application(self):
        for ap, mp, frozen in [(0, 0, frozenset()), (6, 3, frozenset({2, 3}))]:
            actor, packets, calls, _ = self.run_payment(ap, mp, frozen)
            self.assertEqual((actor.ap, actor.mp), (ap, mp))
            self.assertEqual(packets, [])
            self.assertEqual(len(calls), 4)
            self.assertEqual(calls[0][2]["value"], 0)

    def test_only_attested_synthetic_payment_can_use_native_minus_one_uid(self):
        source = NativeEventSource(
            -1,
            -1,
            1,
            7,
            7,
            (0, 0, 0),
            (0, 55),
            3,
            7,
            None,
            False,
            False,
            False,
            True,
            cost_source={
                "runner_class": "eWf",
                "action_costs": {"ap": 1, "mp": 0, "wp": 0},
                "spell_context": {"present": False},
            },
            native_container={"present": False},
            native_definition_present=False,
            native_execution_status=-1,
        )
        source.validate()
        for invalid in [
            replace(source, generic_effect=1),
            replace(source, uid=-2),
            replace(source, native_definition_present=True),
            replace(source, cost_source=None),
        ]:
            with self.assertRaises(ValueError):
                invalid.validate()
