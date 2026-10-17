import unittest
from wakfu_server.combat_additional_turn import additional_turn_insertion


class NativeAdditionalTurnTests(unittest.TestCase):
    def case(self, mode, offset, caster_id=7):
        return additional_turn_insertion(
            [7, -7, 8], 1, mode=mode, offset=offset, caster_id=caster_id, target_id=7
        )

    def test_current_turn_insertion_preserves_cursor_and_duplicate(self):
        result = self.case(0, 1)
        self.assertTrue(result["applied"])
        self.assertEqual(result["order"], [7, -7, 7, 8])
        self.assertEqual(result["current_index"], 1)

    def test_raw_gate_and_modulo_slot_gate_are_distinct(self):
        result = self.case(1, -1)
        self.assertFalse(result["applied"])
        self.assertEqual(result["reason"], "eWl-position-not-after-current")
        result = self.case(1, 4)
        self.assertFalse(result["applied"])
        self.assertEqual(result["raw_position"], 4)
        self.assertEqual(result["insertion"], 0)
        self.assertEqual(result["reason"], "Tc-slot-not-after-current")

    def test_other_modes_use_first_caster_or_native_minus_one(self):
        for mode in (-2147483648, -1, 2, 99, 2147483647):
            self.assertEqual(self.case(mode, 3)["order"], [7, -7, 8, 7])
            self.assertEqual(self.case(mode, 3, 999)["order"], [7, -7, 7, 8])

    def test_signed_int_overflow_and_unknown_cursor_reject(self):
        self.assertFalse(self.case(0, 2147483647)["applied"])
        with self.assertRaises(ValueError):
            additional_turn_insertion(
                [7], 1, mode=0, offset=1, caster_id=7, target_id=7
            )

    def test_double_turn_does_not_advance_or_expire_a_round(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        actors = [
            Actor(7, 0, (0, 0, 0), 20, 6, 3, 10, 1, 3, True),
            Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1),
        ]
        fight = Fight(
            1, actors, {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        fight.ready(3)
        fight.native_base_turn_order = list(fight.order)
        fight.order.insert(1, 7)
        runtime = RuntimeMessages(fight)
        expired = []
        runtime._expire_owned = lambda **k: expired.append(k) or []
        runtime.turn_started()
        self.assertEqual(fight.native_timeline_round, 1)
        fight._advance()
        self.assertEqual(fight.current.id, 7)
        self.assertEqual(fight.current.turn_count, 2)  # Distinct ACK/activation count.
        runtime.turn_started()
        self.assertEqual(fight.native_table_turn, 1)
        self.assertEqual(sum(row.get("round_cleanup", False) for row in expired), 1)
        fight._advance()
        runtime.turn_started()
        self.assertEqual(fight.native_timeline_round, 1)
        fight._advance()
        runtime.turn_started()
        self.assertEqual(fight.native_timeline_round, 2)
        self.assertEqual(fight.native_table_turn, 2)
        self.assertEqual(fight.order, [7, -7])
        self.assertEqual(sum(row.get("round_cleanup", False) for row in expired), 2)

    def test_actual_runner_retained_removal_keeps_inserted_turn(self):
        from types import SimpleNamespace
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_additional_turn import (
            NativeAdditionalTurnHandler,
            remove_additional_turn,
        )
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        actor = SimpleNamespace(id=7)
        other = SimpleNamespace(id=-7)
        fight = SimpleNamespace(
            id=1,
            actors={7: actor, -7: other},
            owned_stat_effects={},
            phase="active",
            order=[7, -7],
            turn_index=0,
            native_timeline_policy="feq",
            native_timeline_round=1,
            native_base_turn_order=None,
        )
        initialize_global_pv_collections(fight, (7, -7))
        packets = []
        handler = NativeAdditionalTurnHandler(
            fight,
            packets,
            allocate_uid=lambda: 1,
            action_id=2,
            context=lambda e, i: StatExecutionContext(True, True, None, True, b""),
            authority=lambda f, a: SimpleNamespace(targeting={"is_eGj": True}),
            rng=lambda: 0.5,
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
                dict(effect_class=666, parameters=[0, 0, 1, 0], target_masks=[[]] * 7),
                {},
                invocation,
            )
        )
        self.assertEqual(fight.order, [7, 7, -7])
        self.assertEqual(fight.native_base_turn_order, [7, -7])
        self.assertEqual(packets[0][0], 12613)
        remove_additional_turn(
            SimpleNamespace(fight=fight, packets=packets, action_id=2), 1
        )
        self.assertEqual(fight.order, [7, 7, -7])
        self.assertEqual(fight.owned_stat_effects, {})
        self.assertEqual(packets[-1][0], 13560)

    def test_original_java_timeline_differential_45_cases(self):
        import json
        from pathlib import Path

        rows = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "server/tests/fixtures/native_combat_oracles/additional-turn.json"
            ).read_text()
        )
        self.assertEqual(len(rows), 45)
        for row in rows:
            with self.subTest(mode=row["mode"], offset=row["offset"]):
                result = self.case(row["mode"], row["offset"])
                self.assertEqual(result["order"], row["order"])
                self.assertEqual(result["current_index"], row["cursor"])
