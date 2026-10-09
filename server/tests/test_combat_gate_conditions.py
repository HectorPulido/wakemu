import unittest
from wakfu_server.combat_gate_conditions import has_valid_gate_for_tp


class GateConditionTests(unittest.TestCase):
    def query(self, rows, **kwargs):
        args = dict(
            caster_id=7,
            caster_affiliation=1,
            center=(0, 0, 0),
            minimum=1,
            maximum=3,
            cell_affiliations=lambda x, y: frozenset(),
        )
        args.update(kwargs)
        return has_valid_gate_for_tp(rows, **args)

    def gate(self, **kwargs):
        row = dict(
            uid=100,
            native_type_id=19,
            native_fight_affiliation=1,
            owner_id=99,
            cell=(2, 0, 0),
        )
        row.update(kwargs)
        return row

    def test_complete_empty_population_does_not_need_occupancy(self):
        self.assertFalse(self.query((), cell_affiliations=None))

    def test_captured_affiliation_independent_from_owner_identity(self):
        self.assertTrue(self.query((self.gate(owner_id=99),)))
        self.assertFalse(self.query((self.gate(native_fight_affiliation=2),)))

    def test_any_native_occupant_rejects_gate(self):
        self.assertFalse(
            self.query((self.gate(),), cell_affiliations=lambda x, y: frozenset({-1}))
        )

    def test_negative_maximum_ignores_minimum(self):
        self.assertTrue(self.query((self.gate(),), minimum=999, maximum=-1))

    def test_missing_occupancy_or_captured_affiliation_stays_unknown(self):
        with self.assertRaises(ValueError):
            self.query((self.gate(),), cell_affiliations=None)
        with self.assertRaises(ValueError):
            self.query((self.gate(native_fight_affiliation=None),))

    def test_all_candidates_validated_after_first_match(self):
        with self.assertRaises(ValueError):
            self.query((self.gate(), self.gate(uid=101, native_fight_affiliation=None)))

    def test_caster_identity_and_non_gate_types_excluded(self):
        self.assertFalse(self.query((self.gate(uid=7), self.gate(native_type_id=4))))


class GatePredicateCallbackTests(unittest.TestCase):
    def test_complete_empty_gate_result_remains_false(self):
        from wakfu_server.combat_conditions import ConditionContext, evaluate_condition

        calls = []

        def query(*arguments):
            calls.append(arguments)
            return False

        context = ConditionContext({}, valid_gate_for_tp_query=query)
        self.assertFalse(
            evaluate_condition('HasValidGateForTp("target", 0, 6)', context)
        )
        self.assertEqual(calls, [("target", 0, 6)])

    def test_missing_callback_and_wrong_signature_remain_unknown(self):
        from wakfu_server.combat_conditions import (
            ConditionContext,
            UnknownCondition,
            evaluate_condition,
        )

        for criteria in (
            'HasValidGateForTp("target",0,6)',
            'HasValidGateForTp("target",0)',
        ):
            with self.subTest(criteria=criteria), self.assertRaises(UnknownCondition):
                evaluate_condition(criteria, ConditionContext({}))
