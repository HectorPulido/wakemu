import unittest
from types import SimpleNamespace
from wakfu_server.combat_turn_suppression import (
    suppression_flags,
    suppression_payload,
    mutate_suppression,
    turn_phase_suppressed,
    NativeTurnSuppressionHandler,
    remove_turn_suppression,
)


class NativeTurnSuppressionTests(unittest.TestCase):
    def test_exact_parameter_arity_and_modes(self):
        for values, expected in (
            ([], (True, True)),
            ([0], (True, True)),
            ([1], (True, False)),
            ([2], (False, True)),
            ([-1], (True, True)),
            ([1, 99], (True, True)),
        ):
            self.assertEqual(suppression_flags(values), expected)
        with self.assertRaises(ValueError):
            suppression_flags([True])

    def test_wire_fields_are_actual_iN8_ij17_18(self):
        self.assertEqual(
            suppression_payload(True, False), b"\x42\x06\x88\x01\x01\x90\x01\x00"
        )

    def test_literal_native_clear_does_not_reference_count_overlaps(self):
        actor = SimpleNamespace(native_turn_suppression_bits=1)
        mutate_suppression(actor, True, True)
        mutate_suppression(actor, True, False)
        self.assertTrue(turn_phase_suppressed(actor, "start"))
        self.assertTrue(turn_phase_suppressed(actor, "end"))
        mutate_suppression(actor, True, False, remove=True)
        self.assertFalse(turn_phase_suppressed(actor, "start"))
        self.assertTrue(turn_phase_suppressed(actor, "end"))
        self.assertEqual(actor.native_turn_suppression_bits, 5)

    def test_missing_snapshot_rejects_without_zero_fallback(self):
        with self.assertRaises(ValueError):
            turn_phase_suppressed(SimpleNamespace(), "start")
        with self.assertRaises(ValueError):
            turn_phase_suppressed(
                SimpleNamespace(native_turn_suppression_bits=True), "end"
            )

    def test_owned_boundary_records_suppression_without_emitting_events(self):
        from test_combat_turn_events import OwnedTurnEndTests
        from wakfu_server.combat_turn_events import deliver_turn_start, deliver_turn_end

        fight, dispatcher, seen = OwnedTurnEndTests().fixture()
        mutate_suppression(fight.current, True, False)
        self.assertEqual(deliver_turn_start(dispatcher, actor_id=7), ())
        self.assertEqual(seen, [])
        self.assertTrue(fight.native_turn_event_deliveries["1:7:start"]["suppressed"])
        deliver_turn_end(dispatcher, actor_id=7)
        self.assertEqual(len(seen), 4)

    def test_runtime_retained_apply_then_removal_and_phase_order(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        actor = SimpleNamespace(id=7, native_turn_suppression_bits=0)
        fight = SimpleNamespace(id=1, actors={7: actor}, owned_stat_effects={})
        initialize_global_pv_collections(fight, participant_order=(7,))
        packets, phases = [], []
        handler = NativeTurnSuppressionHandler(
            fight,
            packets,
            allocate_uid=lambda: 1,
            action_id=2,
            context=lambda e, i: StatExecutionContext(True, True, None, True, b""),
            authority=lambda f, a: SimpleNamespace(targeting={"is_eGj": True}),
            rng=lambda: 0.5,
        )
        handler.event_lifecycle = SimpleNamespace(
            phase=lambda e, i, **k: phases.append(k["channel"]),
            register_applied=lambda *args: phases.append("retained"),
        )
        invocation = EffectInvocation(
            22,
            1,
            7,
            7,
            (0, 0, 0),
            native_context_hex="0800100020ffffffffffffffffff0128013000380040004800",
        )
        self.assertTrue(
            handler(
                dict(effect_class=667, parameters=[1, 0], target_masks=[[]] * 7),
                {},
                invocation,
            )
        )
        self.assertEqual(phases, [1, 2, "retained", 3, 4])
        self.assertEqual(actor.native_turn_suppression_bits, 2)
        self.assertEqual(packets[0][0], 12613)
        remove_turn_suppression(
            SimpleNamespace(fight=fight, packets=packets, action_id=2), 1
        )
        self.assertEqual(actor.native_turn_suppression_bits, 0)
        self.assertEqual(packets[-1][0], 13560)
        self.assertEqual(fight.owned_stat_effects, {})
